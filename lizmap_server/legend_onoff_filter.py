"""
@author: elpaso@itopen.it
@date: 2022-10-27
"""

# File adapted by @rldhont, 3Liz

import traceback

from typing import (
    Optional,
)

from qgis.core import (
    Qgis,
    QgsMapLayer,
    QgsProject,
)
from qgis.server import (
    QgsAccessControlFilter,
    QgsServerFilter,
    QgsServerInterface,
)

from .core import find_vector_layer
from .tools import unwrap

from . import logger


class LegendOnOffAccessControl(QgsAccessControlFilter):
    def __init__(self, server_interface: QgsServerInterface):
        super().__init__(server_interface)

        self.iface = server_interface

    @staticmethod
    def _setup_legend(layer: QgsMapLayer, qs: str, onoff: bool):

        if Qgis.versionInt() < 33800:
            layer_short_name = layer.shortName()
        else:
            layer_short_name = unwrap(layer.serverProperties()).shortName()

        for legend_layer in qs.split(";"):
            layer_name, key_list = legend_layer.split(":")
            # not empty
            if layer_name == "" or key_list == "":
                continue
            # for the layer
            if layer_name not in (layer_short_name, layer.name(), layer.id()):
                continue

            # TODO: check that layer is a vector layer
            for key in key_list.split(","):
                layer.renderer().checkLegendSymbolItem(key, onoff)  # ty: ignore[unresolved-attribute]

    def layerPermissions(self, layer: Optional[QgsMapLayer]) -> QgsAccessControlFilter.LayerPermissions:

        layer = unwrap(layer)

        rights = super().layerPermissions(layer)

        handler = unwrap(self.iface.requestHandler())
        params = handler.parameterMap()

        styles = params.get("STYLES", "").split(",")

        if len(styles) == 0:
            # TODO: check return type
            styles = params.get("STYLE", [])

        layers = params.get("LAYERS", "").split(",")

        if len(layers) == 0:
            # TODO: check return type
            layers = params.get("LAYER", [])

        # noinspection PyBroadException
        try:
            style_map = dict(zip(layers, styles))
        except Exception:
            style_map = {}

        sm = unwrap(layer.styleManager())
        style = sm.currentStyle()

        # check short name
        if Qgis.versionInt() < 33800:
            layer_short_name = layer.shortName()
        else:
            layer_short_name = unwrap(layer.serverProperties()).shortName()
        if layer_short_name in style_map:
            style = style_map[layer_short_name]

        # check layer name
        elif layer.name() in style_map:
            style = style_map[layer.name()]
        # check layer id
        elif layer.id() in style_map:
            style = style_map[layer.id()]

        sm.setCurrentStyle(style)

        if "LEGEND_ON" in params:
            self._setup_legend(layer, params["LEGEND_ON"], True)
        if "LEGEND_OFF" in params:
            self._setup_legend(layer, params["LEGEND_OFF"], False)

        if (
            "LEGEND_ON" not in params
            and "LEGEND_OFF" not in params
            and layer.type() == Qgis.LayerType.Vector
            and layer.renderer()  # ty: ignore[unresolved-attribute]
            and layer.renderer().type()  # ty: ignore[unresolved-attribute]
            in (
                "categorizedSymbol",
                "RuleRenderer",
                "graduatedSymbol",
            )
        ):
            renderer = layer.renderer()  # ty: ignore[unresolved-attribute]
            for item in renderer.legendSymbolItems():
                renderer.checkLegendSymbolItem(item.ruleKey(), True)

        return rights


class LegendOnOffFilter(QgsServerFilter):
    """Legend ON/OFF filter

    LEGEND_ON=<layer_id>:<rule_key>,<rule_key>;<layer_id>:<rule_key>,<rule_key>
    LEGEND_OFF=<layer_id>:<rule_key>,<rule_key>;<layer_id>:<rule_key>,<rule_key>

    """

    def __init__(self, server_interface: QgsServerInterface):
        super().__init__(server_interface)

    @staticmethod
    def _reset_legend(qs: str, project: QgsProject):
        if not qs or ":" not in qs:
            return

        for legend_layer in qs.split(";"):
            layer_name, key_list = legend_layer.split(":")
            if layer_name == "" or key_list == "":
                continue

            keys = key_list.split(",")
            if len(keys) == 0:
                continue

            layer = find_vector_layer(layer_name, project)
            if layer is None:
                logger.warning(
                    f"LegendOnOFF::RequestReady : Skipping the layer '{layer_name}'"
                    " because it's not a vector layer"
                )
                continue

            for key in keys:
                unwrap(layer.renderer()).checkLegendSymbolItem(key, True)

    def responseComplete(self) -> None:
        """Restore legend customized renderers"""
        try:
            handler = unwrap(self.serverInterface()).requestHandler()
            if not handler:
                logger.critical("LegendOnOffFilter plugin cannot be run in multithreading mode, skipping.")
                return

            params = handler.parameterMap()

            if "LEGEND_ON" not in params and "LEGEND_OFF" not in params:
                return

            project: QgsProject = unwrap(QgsProject.instance())

            if "LEGEND_ON" in params:
                self._reset_legend(params["LEGEND_ON"], project)
            if "LEGEND_OFF" in params:
                self._reset_legend(params["LEGEND_OFF"], project)
        except Exception:
            logger.critical(traceback.format_exc())
            # Let server handle error 500
            raise
