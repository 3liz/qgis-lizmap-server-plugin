from typing import Sequence

from .models import Field, JsonModel, Option


class LayoutMap(JsonModel):
    id_: str = Field(alias="id")
    width: float
    heigth: float
    uuid: str
    page: int
    overview_map: Option[str]
    grid: bool


class LayoutLabel(JsonModel):
    id_: str = Field(alias="id")
    html_state: bool
    text: str


class LayoutPage(JsonModel):
    width: float
    heigth: float
    units: str


class LayoutSummary(JsonModel):
    name: str
    atlas_enabled: bool
    atlas_coverage_layer: Option[str] = None


class LayoutDescription(LayoutSummary):
    pages: Sequence[LayoutPage]
    maps: Sequence[LayoutMap]
    labels: Sequence[LayoutLabel]
