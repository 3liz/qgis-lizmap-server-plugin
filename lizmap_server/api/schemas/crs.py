from .models import Field, JsonModel


class CrsModel(JsonModel):
    """CRS"""

    auth_id: str = Field(description="The authority Id of the projection")
    proj: str = Field(description="The proj string for the crs")
    srid: int = Field(description="The Postgis SRID")
    description: str
