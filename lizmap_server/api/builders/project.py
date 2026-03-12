import traceback

from typing import (
    Iterator,
    Optional,
)

from qgis.core import (
    Qgis,
    QgsMapLayer,
    QgsProject,
    QgsXmlUtils,
)
from qgis.PyQt.QtXml import (
    QDomElement,
)

from .. import logger
from ..schemas.fields import (
    EditWidget,
    FieldConfiguration,
    FieldConstraint,
    FieldConstraintExpression,
    FieldDefault,
)
from ..schemas.layers import (
    LayerDetails,
    RasterLayerDetails,
    VectorLayerDetails,
)
from .layers import attribute_table_config


def edit_widget(elem: QDomElement) -> Optional[EditWidget]:
    """Read EditWidget out of Dom element"""
    if elem.isNull():
        return None

    cfgElem = elem.firstChildElement("config")
    optElem = cfgElem.childNodes().at(0).toElement()

    optionsMap = QgsXmlUtils.readVariant(optElem) or {}

    return EditWidget(
        type_=elem.attribute("type"),
        config=optionsMap,
    )


#
# field configuration
#
def read_layer_field_configuration(
    layerElem: QDomElement,
) -> Iterator[tuple[str, FieldConfiguration]]:
    """Read field configurations"""
    node = layerElem.namedItem("fieldConfiguration")
    node_list = node.toElement().elementsByTagName("field")
    for i in range(node_list.size()):
        elem = node_list.at(i).toElement()

        flags = elem.attribute("configurationFlags")

        hide_from_wms = False
        hide_from_wfs = False

        head, _, tail = flags.partition("|")
        while head:
            if head == "HideFromWms":
                hide_from_wms = True
            elif head == "HideFromWfs":
                hide_from_wfs = True

            head, _, tail = tail.partition("|")

        yield (
            elem.attribute("name"),
            FieldConfiguration(
                hide_from_wms=hide_from_wms,
                hide_from_wfs=hide_from_wfs,
                flags=elem.attribute("configurationFlags"),
                edit_widget=edit_widget(elem.firstChildElement("editWidget")),
            ),
        )


#
# field defaults
#
def read_layer_field_defaults(layerElem: QDomElement) -> Iterator[tuple[str, FieldDefault]]:
    """Read field defaults"""
    node = layerElem.namedItem("defaults")
    node_list = node.toElement().elementsByTagName("default")
    for i in range(node_list.size()):
        elem = node_list.at(i).toElement()
        field = elem.attribute("field")
        expression = elem.attribute("expression")
        if not (field and expression):
            continue
        yield (
            field,
            FieldDefault(
                expression=expression,
                apply_on_update=elem.attribute("applyOnUpdate", "0") == "1",
            ),
        )


#
# field constraints
#
def read_layer_field_constraints(layerElem: QDomElement) -> Iterator[tuple[str, FieldConstraint]]:
    """Read field constraints"""
    node = layerElem.namedItem("constraints")
    node_list = node.toElement().elementsByTagName("constraint")
    for i in range(node_list.size()):
        elem = node_list.at(i).toElement()
        field = elem.attribute("field")
        constraints = int(elem.attribute("constraints", "0"))
        if not field or constraints == 0:
            continue
        yield (
            field,
            FieldConstraint(
                constraints=constraints,
                notnull_strength=int(elem.attribute("notnull_strength", "1")),
                unique_strength=int(elem.attribute("unique_strength", "1")),
                expression_strength=int(elem.attribute("exp_strength", "1")),
            ),
        )


#
# field constraint expressions
#
def read_layer_field_constraint_expr(
    layerElem: QDomElement,
) -> Iterator[tuple[str, FieldConstraintExpression]]:
    """Read field constraint expressions"""
    node = layerElem.namedItem("constraintExpressions")
    node_list = node.toElement().elementsByTagName("constraint")
    for i in range(node_list.size()):
        elem = node_list.at(i).toElement()
        field = elem.attribute("field")
        expression = elem.attribute("exp")
        if not (field and expression):
            continue
        yield (
            field,
            FieldConstraintExpression(
                expression=expression,
                description=elem.attribute("desc"),
            ),
        )


#
# field constraint expressions
#
def read_layer_editable_fields(
    layerElem: QDomElement,
) -> Iterator[tuple[str, bool]]:
    """Read field constraint expressions"""
    node = layerElem.namedItem("editable")
    node_list = node.toElement().elementsByTagName("field")
    for i in range(node_list.size()):
        elem = node_list.at(i).toElement()
        field = elem.attribute("name")
        if not field:
            continue
        yield field, elem.attribute("editable") == "1"


#
# Provider
#
def read_layer_provider(layerElem: QDomElement) -> str:
    """Read layer provider"""
    return layerElem.namedItem("provider").toElement().text()


#
# Read project (No data)
#
def read_project(
    project: QgsProject,
    uri: str,
    with_details: bool = False,
    with_layouts: bool = True,
) -> tuple[bool, dict[str, LayerDetails]]:

    layer_details: dict[str, LayerDetails] = {}

    readflags = Qgis.ProjectReadFlags()
    # Activate all optimisation flags
    readflags |= Qgis.ProjectReadFlag.TrustLayerMetadata
    readflags |= Qgis.ProjectReadFlag.ForceReadOnlyLayers
    readflags |= Qgis.ProjectReadFlag.DontResolveLayers

    if not with_layouts:
        readflags |= Qgis.ProjectReadFlag.DontLoadLayouts

    def read_layer_details(layer: QgsMapLayer, layerElem: QDomElement):
        # Extract field configuration since we cannot do it from API
        # without loading layers
        try:
            if layer.type() == Qgis.LayerType.Vector:
                layer_details[layer.id()] = VectorLayerDetails(
                    provider=read_layer_provider(layerElem),
                    editable_fields=dict(read_layer_editable_fields(layerElem)),
                    attribute_table_config=attribute_table_config(layer.attributeTableConfig()),
                    fields=dict(read_layer_field_configuration(layerElem)),
                    defaults=dict(read_layer_field_defaults(layerElem)),
                    constraints=dict(read_layer_field_constraints(layerElem)),
                    constraint_expressions=dict(read_layer_field_constraint_expr(layerElem)),
                )
            elif layer.type() == Qgis.LayerType.Raster:
                layer_details[layer.id()] = RasterLayerDetails(
                    provider=read_layer_provider(layerElem),
                )

        # Do not raise exception while in signal
        except Exception:
            logger.error(traceback.format_exc())

    try:
        if with_details:
            project.readMapLayer.connect(read_layer_details)
        ok = project.read(uri, readflags)
        return ok, layer_details
    finally:
        if with_details:
            project.readMapLayer.disconnect(read_layer_details)

    return False, {}
