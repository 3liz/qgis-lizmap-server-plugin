from datetime import datetime
from typing import (
    Annotated,
    Sequence,
)

from annotated_types import Len
from pydantic_extra_types.color import Color

from .crs import CrsModel
from .layers import LayerDescription
from .layertree import (
    LayerTreeRoot,
    LayerVisibilityPreset,
)
from .models import (
    JsonModel,
    OneOf,
    Option,
)

Extent2D = Annotated[Sequence[float], Len(min_length=4, max_length=4)]
Extent3D = Annotated[Sequence[float], Len(min_length=6, max_length=6)]

Extent = OneOf[Extent2D | Extent3D]

ProjectCrs = CrsModel


class OWSProperties(JsonModel):
    """Ows properties"""

    ows_service_title: str
    ows_service_abstract: str
    ows_service_keywords: Sequence[str]
    ows_online_resource: str
    ows_service_contact_mail: str
    ows_service_contact_organization: str
    ows_service_contact_person: str
    ows_service_contact_phone: str
    wws_max_height: int
    wms_max_width: int
    wms_extent: Option[Extent]
    wms_restricted_layers: Sequence[str]
    wms_max_atlas_features: int
    wms_restricted_composers: Sequence[str]
    wms_use_layer_ids: bool
    wms_feature_info_add_wkt_geometry: bool
    wfs_layers_ids: Sequence[str]


class GuiProperties(JsonModel):
    """Gui properties"""

    background_color: Option[Color]
    selection_color: Option[Color]


class ProjectSummary(JsonModel):
    """Project summary"""

    title: str
    version: str
    save_date_time: Option[datetime]


class ProjectDescription(ProjectSummary):
    """Project description"""

    project_crs: Option[ProjectCrs]
    ows_properties: Option[OWSProperties] = None
    gui_properties: Option[GuiProperties] = None

    layer_tree_root: LayerTreeRoot
    visibility_presets: Sequence[LayerVisibilityPreset]

    custom_variables: dict[str, str]

    layers: dict[str, LayerDescription]
