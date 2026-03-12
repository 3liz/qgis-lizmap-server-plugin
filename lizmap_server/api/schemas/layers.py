"""Layers description"""

from typing import (
    Annotated,
    Literal,
    Sequence,
    Union,
)

from .crs import CrsModel
from .fields import (
    FieldConfiguration,
    FieldConstraint,
    FieldConstraintExpression,
    FieldDefault,
)
from .models import Field, JsonModel, Option


class StyleManager(JsonModel):
    current: str
    styles: Sequence[str]


class AttributeTableColumn(JsonModel):
    type_: str = Field(alias="type")
    hidden: bool
    name: str


class AttributeTableConfig(JsonModel):
    columns: Sequence[AttributeTableColumn] = ()


class FeatureRenderer(JsonModel):
    type_: str = Field(alias="type")
    categories: dict[str, str]


class VectorLayerJoinInfo(JsonModel):
    join_layer_id: str
    join_field_name: str
    target_field_name: str


class LayerDetailsBase(JsonModel):
    """Layer fields description"""

    provider: str


class RasterLayerDetails(LayerDetailsBase):
    type_: Literal["raster"] = Field("raster", alias="type")


class VectorLayerDetails(LayerDetailsBase):
    type_: Literal["vector"] = Field("vector", alias="type")
    attribute_table_config: AttributeTableConfig = AttributeTableConfig()
    editable_fields: dict[str, bool]
    fields: dict[str, FieldConfiguration]
    defaults: dict[str, FieldDefault]
    constraints: dict[str, FieldConstraint]
    constraint_expressions: dict[str, FieldConstraintExpression]

    def exclude_attribute_wms(self) -> Sequence[str]:
        """List of attributes hidden from WMS"""
        return tuple(name for name, conf in self.fields.items() if conf.hide_from_wms)

    def exclude_attribute_wfs(self) -> Sequence[str]:
        """List of attributes hidden from WFS"""
        return tuple(name for name, conf in self.fields.items() if conf.hide_from_wfs)


LayerDetails = Annotated[
    Union[
        VectorLayerDetails,
        RasterLayerDetails,
    ],
    "LayerDetails",
]


class LayerDescription(JsonModel):
    """Layer description"""

    id_: str = Field(alias="id")
    name: str
    type_: str = Field(alias="type")
    abstract: str
    embedded: bool
    provider: str
    datasource: str
    opacity: float
    srs: Option[CrsModel]
    style_manager: StyleManager
    keywords: str
    attribute_aliases: dict[str, str]
    exclude_attribute_wfs: Sequence[str]
    exclude_attribute_wms: Sequence[str]
    display_expression: Option[str]
    vector_joins: Sequence[VectorLayerJoinInfo]
    feature_renderer: Option[FeatureRenderer]
