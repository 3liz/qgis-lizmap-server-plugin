__author__ = 'elpaso@itopen.it'
__date__ = '2022-10-27'
__license__ = "GPL version 3"
__copyright__ = 'Copyright 2022, Gis3w'

# File adapted by @rldhont, 3Liz

import json

from qgis.core import QgsProject
from qgis.server import QgsServerFilter, QgsServerProjectUtils

from lizmap_server.logger import Logger, exception_handler


class GetLegendGraphicFilter(QgsServerFilter):
    """add ruleKey to GetLegendGraphic for categorized and rule-based
    only works for single LAYER and STYLE(S) and json format.
    """

    @exception_handler
    def responseComplete(self):

        handler = self.serverInterface().requestHandler()
        logger = Logger()
        if not handler:
            logger.critical(
                'GetLegendGraphicFilter plugin cannot be run in multithreading mode, skipping.')
            return

        params = handler.parameterMap()

        if params.get('SERVICE', '').upper() != 'WMS':
            return

        if params.get('REQUEST', '').upper() not in ('GETLEGENDGRAPHIC', 'GETLEGENDGRAPHICS'):
            return

        if params.get('FORMAT', '').upper() != 'APPLICATION/JSON':
            return

        # Only support request for simple layer
        layer_id = params.get('LAYER', '')
        if layer_id == '':
            return
        if ',' in layer_id:
            return

        # noinspection PyArgumentList
        qgs_project: QgsProject = QgsProject.instance()
        # noinspection PyArgumentList
        use_ids = QgsServerProjectUtils.wmsUseLayerIds(qgs_project)

        style = params.get('STYLES', '')

        if not style:
            style = params.get('STYLE', '')

        current_style = ''
        layer = None

        try:
            if use_ids:
                layer = qgs_project.mapLayer(layer_id)
            else:
                layers = qgs_project.mapLayersByName(layer_id)
                if layers:
                    layer = layers[0]
                else:
                    return

            current_style = layer.styleManager().currentStyle()

            if current_style and style and style != current_style:
                layer.styleManager().setCurrentStyle(style)

            renderer = layer.renderer()

            if renderer.type() in ("categorizedSymbol", "ruleBased", "graduatedSymbol"):
                body = handler.body()
                # noinspection PyTypeChecker
                json_data = json.loads(bytes(body))
                categories = {item.label(): {'ruleKey': item.ruleKey(), 'checked': renderer.legendSymbolItemChecked(
                    item.ruleKey())} for item in renderer.legendSymbolItems()}

                symbols = json_data['nodes'][0]['symbols'] if 'symbols' in json_data['nodes'][0] else json_data['nodes']

                new_symbols = []

                for idx in range(len(symbols)):
                    symbol = symbols[idx]
                    try:
                        category = categories[symbol['title']]
                        symbol['ruleKey'] = category['ruleKey']
                        symbol['checked'] = category['checked']
                    except (IndexError, KeyError):
                        pass

                    new_symbols.append(symbol)

                if 'symbols' in json_data['nodes'][0]:
                    json_data['nodes'][0]['symbols'] = new_symbols
                else:
                    json_data['nodes'] = new_symbols

                handler.clearBody()
                handler.appendBody(json.dumps(
                    json_data).encode('utf8'))
        except Exception as ex:
            logger.critical(
                'Error getting layer "{}" when setting up legend graphic for json output when configuring '
                'OWS call: {}'.format(layer_id, str(ex)))
        finally:
            if layer and style and current_style and style != current_style:
                layer.styleManager().setCurrentStyle(current_style)
