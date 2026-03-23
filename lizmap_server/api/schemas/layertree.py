from typing import Sequence, Union

from .models import Field, JsonModel

#
#  Layer Tree
#


class LayerTreeLayer(JsonModel):
    name: str
    id_: str = Field(alias="id")
    custom_properties: Sequence[str]


class LayerTreeGroup(JsonModel):
    name: str
    custom_properties: Sequence[str]
    mutually_exclusive: bool
    items: Sequence[Union[LayerTreeLayer, "LayerTreeGroup"]]


LayerTreeItem = Union[LayerTreeLayer, LayerTreeGroup]


class LayerTreeRoot(JsonModel):
    custom_properties: Sequence[str]
    custom_order_enabled: bool
    custom_order_items: Sequence[str]
    items: Sequence[LayerTreeItem]


#
# Visibility presets (aka Themes)
#


class LayerVisibility(JsonModel):
    id_: str = Field(alias="id")
    visible: bool
    style: str
    expanded: bool


class LayerVisibilityPreset(JsonModel):
    name: str
    layers: Sequence[LayerVisibility]
    checked_group_nodes: set[str]
    expanded_group_nodes: set[str]
