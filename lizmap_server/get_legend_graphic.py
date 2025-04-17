__author__ = 'elpaso@itopen.it'
__date__ = '2022-10-27'
__license__ = "GPL version 3"
__copyright__ = 'Copyright 2022, Gis3w'

# File adapted by @rldhont and @Gustry, 3Liz

import json
import re

from collections import namedtuple
from typing import Optional

from qgis.core import QgsMapLayer, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QBuffer, QIODevice
from qgis.PyQt.QtGui import QImage
from qgis.server import QgsServerFilter

from lizmap_server.core import find_layer
from lizmap_server.logger import Logger, exception_handler
from lizmap_server.tools import to_bool

Category = namedtuple(
    'Category',
    ['ruleKey', 'checked', 'parentRuleKey', 'scaleMaxDenom', 'scaleMinDenom', 'expression', 'title'])


class GetLegendGraphicFilter(QgsServerFilter):
    """ Add "ruleKey" to GetLegendGraphic for categorized and rule-based
    only works for single LAYER and STYLE(S) and JSON format.
    """

    FEATURE_COUNT_REGEXP = r"(.*) \[≈?(?:\d+|N/A)\]"

    @classmethod
    def match_label_feature_count(cls, symbol_label: str) -> Optional[re.Match]:
        """Regexp for extracting the feature count from the label. """
        return re.match(cls.FEATURE_COUNT_REGEXP, symbol_label)

    @classmethod
    def warning_icon(cls) -> str:
        """ Warning icon as base 64. """
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        qp = QImage(":/images/themes/default/mIconWarning.svg")
        qp.save(buffer, "PNG")
        return bytes(buffer.data().toBase64().data()).decode()

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
        layer_name = params.get('LAYER', '')
        if layer_name == '':
            return

        if ',' in layer_name:
            # The PHP must split the request per layer
            return

        # noinspection PyArgumentList
        project: QgsProject = QgsProject.instance()

        style = params.get('STYLES', '')

        if not style:
            style = params.get('STYLE', '')

        show_feature_count = to_bool(params.get('SHOWFEATURECOUNT'))

        current_style = ''
        layer = find_layer(layer_name, project)
        if not layer:
            return

        layer: QgsMapLayer
        if not layer.isValid():
            logger.warning(
                f"Layer '{layer_name}' is not valid, returning a warning icon in the legend for project "
                f"'{project.homePath()}'",
            )
            json_data = {
                'title': '',
                'nodes': [{
                    'type': 'layer',
                    'title': layer_name,
                    'icon': self.warning_icon(),
                    'valid': False,
                }],
            }
            handler.clearBody()
            handler.appendBody(json.dumps(json_data).encode('utf8'))
            return

        if layer.type() != QgsMapLayer.LayerType.VectorLayer:
            logger.info(f"Skipping the layer '{layer_name}' because it's not a vector layer")
            return

        layer: QgsVectorLayer

        try:
            current_style = layer.styleManager().currentStyle()

            if current_style and style and style != current_style:
                layer.styleManager().setCurrentStyle(style)

            # Force count symbol features
            # It seems that in QGIS Server 3.22 countSymbolFeatures is not used for JSON
            if show_feature_count:
                counter = layer.countSymbolFeatures()
                if counter:
                    counter.waitForFinished()

            # From QGIS source code :
            # https://github.com/qgis/QGIS/blob/71499aacf431d3ac244c9b75c3d345bdc53572fb/src/core/symbology/qgsrendererregistry.cpp#L33
            if layer.renderer().type() in ("categorizedSymbol", "RuleRenderer", "graduatedSymbol"):
                body = handler.body()
                # noinspection PyTypeChecker
                json_data = json.loads(bytes(body))

                symbols = json_data['nodes'][0].get('symbols')
                if not symbols:
                    symbols = json_data['nodes']

                new_symbols = []

                categories = self._extract_categories(layer, show_feature_count, project.homePath())

                for idx in range(len(symbols)):
                    symbol = symbols[idx]
                    symbol_label = symbol['title']
                    if show_feature_count:
                        match_label = self.match_label_feature_count(symbol_label)
                        if match_label:
                            symbol_label = match_label.group(1)
                        else:
                            logger.info(
                                "GetLegendGraphic JSON: symbol label does not match '{}' '{}'".format(
                                    self.FEATURE_COUNT_REGEXP, symbol['title']))
                    try:
                        category = categories[symbol_label]
                        symbol['ruleKey'] = category.ruleKey
                        symbol['checked'] = category.checked
                        symbol['parentRuleKey'] = category.parentRuleKey

                        # TODO remove when QGIS 3.28 will be the minimum version
                        # https://github.com/qgis/QGIS/pull/53738 3.34, 3.32.1, 3.28.10
                        if 'scaleMaxDenom' not in symbol and category.scaleMaxDenom > 0:
                            symbol['scaleMaxDenom'] = category.scaleMaxDenom
                        if 'scaleMinDenom' not in symbol and category.scaleMinDenom > 0:
                            symbol['scaleMinDenom'] = category.scaleMinDenom

                        symbol['expression'] = category.expression
                        if symbol['title'] != category.title:
                            symbol['title'] = category.title
                    except (IndexError, KeyError):
                        pass

                    new_symbols.append(symbol)

                if 'symbols' in json_data['nodes'][0]:
                    json_data['nodes'][0]['symbols'] = new_symbols
                else:
                    json_data['nodes'] = new_symbols

                handler.clearBody()
                handler.appendBody(json.dumps(json_data).encode('utf8'))
        except Exception as ex:
            logger.critical(
                'Error getting layer "{}" when setting up legend graphic for json output when configuring '
                'OWS call: {}'.format(layer_name, str(ex)))
        finally:
            if layer and style and current_style and style != current_style:
                layer.styleManager().setCurrentStyle(current_style)

    @classmethod
    def _extract_categories(
            cls, layer: QgsVectorLayer, show_feature_count: bool = False, project_path: str = "",
    ) -> dict:
        """ Extract categories from the layer legend. """
        # TODO Annotations QGIS 3.22 [str, Category]
        renderer = layer.renderer()
        categories = {}
        for item in renderer.legendSymbolItems():

            # Calculate title if show_feature_count is activated
            # It seems that in QGIS Server 3.22 countSymbolFeatures is not used for JSON
            title = item.label()
            if show_feature_count:
                estimated_count = layer.dataProvider().uri().useEstimatedMetadata()
                count = layer.featureCount(item.ruleKey())
                title += ' [{}{}]'.format(
                    "≈" if estimated_count else "",
                    count if count != -1 else "N/A",
                )

            expression, result = renderer.legendKeyToExpression(item.ruleKey(), layer)
            if not result:
                Logger.warning(
                    f"The expression in the project '{project_path}', layer '{layer.name()}' has not "
                    f"been generated correctly, setting the expression to an empty string",
                )
                expression = ''

            if item.label() in categories.keys():
                Logger.warning(
                    f"The label key '{item.label()}' is not unique, expect the legend to be broken in the project "
                    f"'{project_path}', layer '{layer.name()}'.",
                )

            categories[item.label()] = Category(
                ruleKey=item.ruleKey(),
                checked=renderer.legendSymbolItemChecked(item.ruleKey()),
                parentRuleKey=item.parentRuleKey(),
                scaleMaxDenom=item.scaleMaxDenom(),
                scaleMinDenom=item.scaleMinDenom(),
                expression=expression,
                title=title,
            )
        return categories
