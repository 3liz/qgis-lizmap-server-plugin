"""Layer fields description"""

from .models import Field, JsonModel, JsonMap, Option


class EditWidget(JsonModel):
    type_: str = Field(alias="type")
    config: JsonMap


class FieldDefault(JsonModel):
    expression: str
    apply_on_update: bool


class FieldConstraint(JsonModel):
    constraints: int
    notnull_strength: int
    unique_strength: int
    expression_strength: int


class FieldConstraintExpression(JsonModel):
    expression: str
    description: str


class FieldConfiguration(JsonModel):
    flags: Option[str] = None
    hide_from_wms: bool
    hide_from_wfs: bool
    edit_widget: Option[EditWidget] = None
