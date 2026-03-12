from .models import Field, JsonModel


class Relation(JsonModel):
    id_: str = Field(alias="id")
    name: str
    referencing_layer: str
    referencing_field: str
    referenced_field: str
    strength: str
