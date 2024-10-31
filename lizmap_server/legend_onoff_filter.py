__author__ = 'elpaso@itopen.it'
__date__ = '2022-10-27'
__license__ = "GPL version 3"
__copyright__ = 'Copyright 2022, Gis3w'

# File adapted by @rldhont, 3Liz

from qgis.core import Qgis, QgsMapLayer, QgsProject
from qgis.server import (
    QgsAccessControlFilter,
    QgsServerFilter,
    QgsServerInterface,
)

from lizmap_server.core import find_vector_layer
from lizmap_server.logger import Logger, exception_handler


class LegendOnOffAccessControl(QgsAccessControlFilter):

    def __init__(self, server_interface: QgsServerInterface):
        super().__init__(server_interface)

        self.iface = server_interface

    @staticmethod
    def _setup_legend(layer: QgsMapLayer, qs: str, onoff: bool):

        if Qgis.versionInt() < 33800:
            layer_short_name = layer.shortName()
        else:
            layer_short_name = layer.serverProperties().shortName()

        for legend_layer in qs.split(';'):
            layer_name, key_list = legend_layer.split(':')
            # not empty
            if layer_name == '' or key_list == '':
                continue
            # for the layer
            if layer_name not in (layer_short_name, layer.name(), layer.id()):
                continue

            for key in key_list.split(','):
                layer.renderer().checkLegendSymbolItem(key, onoff)

    def layerPermissions(self, layer: QgsMapLayer) -> QgsAccessControlFilter.LayerPermissions:
        rights = super().layerPermissions(layer)

        handler = self.iface.requestHandler()
        params = handler.parameterMap()

        if 'LEGEND_ON' not in params and 'LEGEND_OFF' not in params:
            return rights

        styles = params.get('STYLES', '').split(',')

        if len(styles) == 0:
            styles = params.get('STYLE', [])

        layers = params.get('LAYERS', '').split(',')

        if len(layers) == 0:
            layers = params.get('LAYER', [])

        # noinspection PyBroadException
        try:
            style_map = dict(zip(layers, styles))
        except Exception:
            style_map = {}

        sm = layer.styleManager()
        style = sm.currentStyle()

        # check short name
        if Qgis.versionInt() < 33800:
            layer_short_name = layer.shortName()
        else:
            layer_short_name = layer.serverProperties().shortName()
        if layer_short_name in style_map:
            style = style_map[layer_short_name]

        # check layer name
        elif layer.name() in style_map:
            style = style_map[layer.name()]
        # check layer id
        elif layer.id() in style_map:
            style = style_map[layer.id()]

        sm.setCurrentStyle(style)

        if 'LEGEND_ON' in params:
            self._setup_legend(layer, params['LEGEND_ON'], True)
        if 'LEGEND_OFF' in params:
            self._setup_legend(layer, params['LEGEND_OFF'], False)

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
        if not qs or ':' not in qs:
            return

        logger = Logger()

        for legend_layer in qs.split(';'):
            layer_name, key_list = legend_layer.split(':')
            if layer_name == '' or key_list == '':
                continue

            keys = key_list.split(',')
            if len(keys) == 0:
                continue

            layer = find_vector_layer(layer_name, project)
            if not layer:
                logger.warning(
                    "LegendOnOFF::RequestReady : Skipping the layer '{}' because it's not a vector layer".format(
                        layer_name))
                continue

            for key in keys:
                layer.renderer().checkLegendSymbolItem(key, True)

    @exception_handler
    def responseComplete(self):
        """Restore legend customized renderers"""

        handler = self.serverInterface().requestHandler()
        logger = Logger()
        if not handler:
            logger.critical('LegendOnOffFilter plugin cannot be run in multithreading mode, skipping.')
            return

        params = handler.parameterMap()

        if 'LEGEND_ON' not in params and 'LEGEND_OFF' not in params:
            return

        # noinspection PyArgumentList
        project: QgsProject = QgsProject.instance()

        if 'LEGEND_ON' in params:
            self._reset_legend(params['LEGEND_ON'], project)
        if 'LEGEND_OFF' in params:
            self._reset_legend(params['LEGEND_OFF'], project)
