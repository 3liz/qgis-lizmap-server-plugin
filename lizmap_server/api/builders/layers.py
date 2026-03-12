from typing import (
    Iterator,
    Optional,
    Sequence,
    cast,
)

from qgis.core import (
    Qgis,
    QgsAttributeTableConfig,
    QgsCategorizedSymbolRenderer,
    QgsFeatureRenderer,
    QgsMapLayer,
    QgsMapLayerStyleManager,
    QgsProject,
    QgsVectorLayerJoinInfo,
)

from ..schemas.layers import (
    AttributeTableColumn,
    AttributeTableConfig,
    FeatureRenderer,
    LayerDescription,
    LayerDetails,
    StyleManager,
    VectorLayerDetails,
    VectorLayerJoinInfo,
)
from .crs import to_crs


def layer_feature_renderer(renderer: Optional[QgsFeatureRenderer]) -> Optional[FeatureRenderer]:
    if renderer and isinstance(renderer, QgsCategorizedSymbolRenderer):
        return FeatureRenderer(
            type_=renderer.type(),
            categories={cat.value(): cat.label() for cat in renderer.categories()},
        )

    return None


def layer_style_manager(mngr: QgsMapLayerStyleManager) -> StyleManager:
    """Build style manager description"""
    return StyleManager(
        current=mngr.currentStyle(),
        styles=mngr.styles(),
    )


def _attribut_config_type(t: QgsAttributeTableConfig.Type) -> str:
    if t == QgsAttributeTableConfig.Type.Field:
        return "field"
    if t == QgsAttributeTableConfig.Type.Action:
        return "action"
    return ""


def attribute_table_config(table_conf: QgsAttributeTableConfig) -> AttributeTableConfig:
    """Build attribute table config"""

    def columns() -> Iterator[AttributeTableColumn]:
        for col in table_conf.columns():
            yield AttributeTableColumn(
                hidden=col.hidden,
                name=col.name,
                type_=_attribut_config_type(col.type),
            )

    return AttributeTableConfig(
        columns=tuple(columns()),
    )


def vectorjoin(join: QgsVectorLayerJoinInfo) -> VectorLayerJoinInfo:
    """Build vector layer join info"""
    return VectorLayerJoinInfo(
        join_field_name=join.joinFieldName(),
        target_field_name=join.targetFieldName(),
        join_layer_id=join.joinLayerId(),
    )


def layer_description(
    layer: QgsMapLayer,
    project: Optional[QgsProject] = None,
    layer_details: Optional[dict[str, LayerDetails]] = None,
) -> LayerDescription:
    """Build layer description"""
    # Qgis 3.38+
    properties = layer.serverProperties()
    project = project or layer.project()

    layer_type = layer.type()

    exclude_attribute_wfs: Sequence[str] = ()
    exclude_attribute_wms: Sequence[str] = ()
    provider_name = ""

    details = layer_details.get(layer.id()) if layer_details else None

    if details:
        provider_name = details.provider
    else:
        # Use QGIS Api
        provider = layer.dataProvider()
        if provider:
            provider_name = provider.name()

    if layer_type == Qgis.LayerType.Vector:
        attribute_aliases = layer.attributeAliases()
        feature_renderer = layer_feature_renderer(layer.renderer())
        display_expression = layer.displayExpression()
        vector_joins = tuple(map(vectorjoin, layer.vectorJoins()))

        if details:
            vector_details = cast("VectorLayerDetails", details)
            exclude_attribute_wms = vector_details.exclude_attribute_wms()
            exclude_attribute_wfs = vector_details.exclude_attribute_wfs()
        else:
            # Use QGIS Api
            fields = layer.fields()

            def pred(flag: Qgis.FieldConfigurationFlags) -> Iterator[str]:
                for field in fields:
                    if field.configurationFlags() & flag:
                        yield field.name()

            exclude_attribute_wms = list(pred(Qgis.FieldConfigurationFlag.HideFromWms))
            exclude_attribute_wfs = list(pred(Qgis.FieldConfigurationFlag.HideFromWfs))
    else:
        vector_joins = ()
        attribute_aliases = {}
        feature_renderer = None
        display_expression = None

    return LayerDescription(
        id_=layer.id(),
        name=layer.name(),
        type_=layer.type().name.lower(),
        abstract=properties.abstract(),
        embedded=project.layerIsEmbedded(layer.id()) != "" if project else False,
        provider=provider_name,
        datasource=properties.dataUrl(),
        opacity=layer.opacity(),
        srs=to_crs(layer.crs()),
        style_manager=layer_style_manager(layer.styleManager()),
        keywords=properties.keywordList(),
        # Vector properties
        feature_renderer=feature_renderer,
        display_expression=display_expression,
        attribute_aliases=attribute_aliases,
        vector_joins=vector_joins,
        exclude_attribute_wfs=exclude_attribute_wfs,
        exclude_attribute_wms=exclude_attribute_wms,
    )
