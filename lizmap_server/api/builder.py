from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import (
    Iterator,
    Optional,
    Sequence,
)

from pydantic_extra_types.color import Color
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsLayerTree,
    QgsLayerTreeNode,
    QgsMapThemeCollection,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.server import QgsServerProjectUtils

from .builders.crs import to_crs
from .builders.layers import layer_description
from .builders.layouts import (
    layout_description,
    layout_summary,
)
from .schemas import (
    Extent,
    GuiProperties,
    LayerDescription,
    LayerDetails,
    LayerTreeGroup,
    LayerTreeItem,
    LayerTreeLayer,
    LayerTreeRoot,
    LayerVisibility,
    LayerVisibilityPreset,
    LayoutDescription,
    LayoutSummary,
    OWSProperties,
    ProjectDescription,
)

#
# Project
#


def project_last_save_datetime(project: QgsProject) -> Optional[datetime]:
    dt = project.lastSaveDateTime()
    return dt.toPyDateTime() if dt.isValid() else None


def project_description(
    project: QgsProject,
    layers: Optional[dict[str, LayerDescription]] = None,
) -> ProjectDescription:
    """Returns project description"""
    if layers is None:
        # Layer descriptions
        layers = {
            id_: layer_description(
                layer,
                project,
            )
            for id_, layer in project.mapLayers().items()
        }

    return ProjectDescription(
        # Summary
        title=project.title(),
        version=project.lastSaveVersion().text(),
        save_date_time=project_last_save_datetime(project),
        # CRS
        project_crs=to_crs(project.crs()),
        # OWS properties
        ows_properties=project_ows_properties(project),
        # Layer tree
        layer_tree_root=project_layer_tree_root(project),
        # Visibility presets
        visibility_presets=list(layers_visibility_presets(project)),
        # custom variables Variables,
        custom_variables={
            k: v
            for k, v in project.customVariables().items()
            if v is not None and not (isinstance(v, QVariant) and v.isNull())
        },
        # Layer descriptions
        layers=layers,
    )


def to_extent(r: QgsRectangle) -> Optional[Extent]:
    """Get extent"""
    return (
        (
            r.xMinimum(),
            r.yMinimum(),
            r.xMaximum(),
            r.yMaximum(),
        )
        if not r.isNull()
        else None
    )


def project_ows_properties(project: QgsProject) -> OWSProperties:
    """Returns OWS properties"""
    pu = QgsServerProjectUtils

    return OWSProperties(
        ows_service_title=pu.owsServiceTitle(project),
        ows_service_abstract=pu.owsServiceAbstract(project),
        ows_service_keywords=pu.owsServiceKeywords(project),
        ows_online_resource=pu.owsServiceOnlineResource(project),
        ows_service_contact_mail=pu.owsServiceContactMail(project),
        ows_service_contact_organization=pu.owsServiceContactOrganization(project),
        ows_service_contact_person=pu.owsServiceContactPerson(project),
        ows_service_contact_phone=pu.owsServiceContactPhone(project),
        wws_max_height=pu.wmsMaxHeight(project),
        wms_max_width=pu.wmsMaxWidth(project),
        wms_extent=to_extent(pu.wmsExtent(project)),
        wms_restricted_layers=pu.wmsRestrictedLayers(project),
        wms_max_atlas_features=pu.wmsMaxAtlasFeatures(project),
        wms_restricted_composers=pu.wmsRestrictedComposers(project),
        wms_use_layer_ids=pu.wmsUseLayerIds(project),
        wms_feature_info_add_wkt_geometry=pu.wmsFeatureInfoAddWktGeometry(project),
        wfs_layers_ids=pu.wfsLayerIds(project),
    )


def to_css3_color(color: QColor) -> Optional[Color]:
    # XXX: QColor has not not the same color hex representation as
    # CSS3 spec (i.e QColor: '#aarrggbb', CSS3: '#rrggbbaa')
    # Use non ambiguous representation
    return (
        Color(
            f"rgb({color.red()},{color.green()},{color.blue()},{color.alphaF()})",
        )
        if color.isValid()
        else None
    )


def project_gui_properties(project: QgsProject) -> GuiProperties:
    """Returns GUI properties"""
    return GuiProperties(
        background_color=to_css3_color(project.backgroundColor()),
        selection_color=to_css3_color(project.selectionColor()),
    )


#
# Layer tree
#


def project_layer_tree_root(project: QgsProject) -> LayerTreeRoot:
    """Build the layer tree root"""
    root = project.layerTreeRoot()

    return LayerTreeRoot(
        custom_properties=root.customProperties(),
        custom_order_enabled=root.hasCustomLayerOrder(),
        custom_order_items=[item.id() for item in root.customLayerOrder()],
        items=list(layer_tree_items(root)),
    )


def layer_tree_items(g: QgsLayerTreeNode) -> Iterator[LayerTreeItem]:
    """Recursively build the layer tree"""
    for item in g.children():
        if QgsLayerTree.isLayer(item):
            yield LayerTreeLayer(
                name=item.name(),
                id_=item.layerId(),
                custom_properties=item.customProperties(),
            )
        elif QgsLayerTree.isGroup(item):
            yield LayerTreeGroup(
                name=item.name(),
                custom_properties=item.customProperties(),
                mutually_exclusive=item.isMutuallyExclusive(),
                items=list(layer_tree_items(item)),
            )


#
#  Layer visibility presets
#


def layer_visibility(r: QgsMapThemeCollection.MapThemeLayerRecord) -> Optional[LayerVisibility]:
    layer = r.layer()
    return (
        LayerVisibility(
            id_=layer.id(),
            visible=r.isVisible,
            expanded=r.expandedLayerNode,
            style=r.currentStyle,
        )
        if layer
        else None
    )


def layers_visibility_presets(project: QgsProject) -> Iterator[LayerVisibilityPreset]:
    """Returns visibility presets"""
    MapThemeLayerRecord: type = QgsMapThemeCollection.MapThemeLayerRecord

    def layers(coll: Sequence[MapThemeLayerRecord]) -> Iterator[LayerVisibility]:  # type: ignore [valid-type]
        for record in coll:
            layer_vis = layer_visibility(record)
            if layer_vis:
                yield layer_vis

    collection = project.mapThemeCollection()
    for name in collection.mapThemes():
        state = collection.mapThemeState(name)
        yield LayerVisibilityPreset(
            name=name,
            checked_group_nodes=state.checkedGroupNodes(),
            expanded_group_nodes=state.expandedGroupNodes(),
            layers=list(layers(state.layerRecords())),
        )


#
# Layouts
#
def project_layouts(project: QgsProject, include_restricted: bool = False) -> Iterator[LayoutSummary]:
    """Return layout summaryies"""
    if not include_restricted:
        restricted = set(QgsServerProjectUtils.wmsRestrictedComposers(project))

    for layout in project.layoutManager().printLayouts():
        if not include_restricted and layout.name() in restricted:
            continue
        yield layout_summary(layout)


def project_layout(project: QgsProject, name: str) -> Optional[LayoutDescription]:

    layout = project.layoutManager().layoutByName(name)
    return (
        layout_description(
            layout,
        )
        if layout and isinstance(layout, QgsPrintLayout)
        else None
    )


#
# Open project definition (no data)
#


def open_project_def(
    uri: str,
    with_details: bool = False,
    with_layouts: bool = True,
) -> tuple[Optional[QgsProject], dict[str, LayerDetails]]:
    """Open a project definition without loading any layers"""
    from .builders.project import read_project

    project = QgsProject(capabilities=Qgis.ProjectCapabilities())
    ok, layer_details = read_project(
        project,
        uri,
        with_details=with_details,
        with_layouts=with_layouts,
    )
    if ok:
        return project, layer_details

    return None, {}


#
#  Get project metadata
#


@dataclass
class StorageMetadata:
    uri: str
    name: str
    storage: Optional[str]
    last_modified: int


def project_storage_metadata(uri: str) -> StorageMetadata:
    """Read metadata about project"""
    reg = QgsApplication.projectStorageRegistry()
    storage = reg.projectStorageFromUri(uri)
    if not storage:
        # Check as file
        p = Path(uri)
        if not p.exists():
            raise FileNotFoundError(uri)
        return StorageMetadata(
            uri=str(p),
            name=p.stem,
            storage="file",
            last_modified=int(p.stat().st_mtime),
        )
    else:  # noqa: RET505
        res, md = storage.readProjectStorageMetadata(uri)
        if not res:
            raise FileNotFoundError(uri)

        last_modified = md.lastModified.toPyDateTime()
        return StorageMetadata(
            uri=uri,
            name=md.name,
            storage=storage.type(),
            last_modified=int(datetime.timestamp(last_modified)),
        )
