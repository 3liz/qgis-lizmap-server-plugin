"""
@author: elpaso@itopen.it
@date: 2022-10-27
"""

# File adapted by @rldhont and @Gustry, 3Liz

import json
import re

from typing import (
    List,
    NamedTuple,
    Optional,
    cast,
)

from qgis.core import Qgis, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QBuffer, QIODevice
from qgis.PyQt.QtGui import QImage
from qgis.server import QgsServerFilter

from lizmap_server import logger
from lizmap_server.core import find_layer
from lizmap_server.tools import to_bool

from .tools import unwrap


class Category(NamedTuple):
    """A legend symbol item from the layer renderer."""

    label: str
    ruleKey: str
    checked: bool
    parentRuleKey: str
    scaleMaxDenom: float
    scaleMinDenom: float
    expression: str
    title: str


class GetLegendGraphicFilter(QgsServerFilter):
    """Add "ruleKey" to GetLegendGraphic for categorized and rule-based
    only works for single LAYER and STYLE(S) and JSON format.
    """

    FEATURE_COUNT_REGEXP = r"(.*) \[≈?(?:\d+|N/A)\]"

    @classmethod
    def match_label_feature_count(cls, symbol_label: str) -> Optional[re.Match]:
        """Regexp for extracting the feature count from the label."""
        return re.match(cls.FEATURE_COUNT_REGEXP, symbol_label)

    @classmethod
    def warning_icon(cls) -> str:
        """Warning icon as base 64."""
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        qp = QImage(":/images/themes/default/mIconWarning.svg")
        qp.save(buffer, "PNG")
        return bytes(buffer.data().toBase64().data()).decode()

    def responseComplete(self) -> None:
        handler = unwrap(self.serverInterface()).requestHandler()
        if not handler:
            logger.critical("GetLegendGraphicFilter plugin cannot be run in multithreading mode, skipping.")
            return

        params = handler.parameterMap()

        if params.get("SERVICE", "").upper() != "WMS":
            return

        if params.get("REQUEST", "").upper() not in ("GETLEGENDGRAPHIC", "GETLEGENDGRAPHICS"):
            return

        if params.get("FORMAT", "").upper() != "APPLICATION/JSON":
            return

        # Only support request for simple layer
        layer_name = params.get("LAYER", "")
        if layer_name == "":
            return

        if "," in layer_name:
            # The PHP must split the request per layer
            return

        # noinspection PyArgumentList
        project = unwrap(QgsProject.instance())

        style = params.get("STYLES", "")

        if not style:
            style = params.get("STYLE", "")

        show_feature_count = to_bool(params.get("SHOWFEATURECOUNT"))

        current_style = ""
        layer = find_layer(layer_name, project)
        if not layer:
            return

        if not layer.isValid():
            logger.warning(
                f"Layer '{layer_name}' is not valid, returning a warning icon in the legend for project "
                f"'{project.homePath()}'",
            )
            json_data = {
                "title": "",
                "nodes": [
                    {
                        "type": "layer",
                        "title": layer_name,
                        "icon": self.warning_icon(),
                        "valid": False,
                    }
                ],
            }
            handler.clearBody()
            handler.appendBody(json.dumps(json_data).encode("utf8"))
            return

        if layer.type() != Qgis.LayerType.Vector:
            logger.info(f"Skipping the layer '{layer_name}' because it's not a vector layer")
            return

        try:
            layer = cast("QgsVectorLayer", layer)
            current_style = unwrap(layer.styleManager()).currentStyle()

            if current_style and style and style != current_style:
                unwrap(layer.styleManager()).setCurrentStyle(style)

            # Force count symbol features
            # It seems that in QGIS Server 3.22 countSymbolFeatures is not used for JSON
            if show_feature_count:
                counter = layer.countSymbolFeatures()
                if counter:
                    counter.waitForFinished()

            # From QGIS source code :
            # https://github.com/qgis/QGIS/blob/71499aacf431d3ac244c9b75c3d345bdc53572fb/src/core/symbology/qgsrendererregistry.cpp#L33
            renderer = layer.renderer()
            if renderer is not None and renderer.type() in (
                "categorizedSymbol",
                "RuleRenderer",
                "graduatedSymbol",
            ):
                body = handler.body()
                json_data = json.loads(bytes(body))  # ty: ignore[invalid-argument-type]

                symbols = json_data["nodes"][0].get("symbols")
                if not symbols:
                    symbols = json_data["nodes"]

                new_symbols = []

                categories = self._extract_categories(
                    layer,
                    show_feature_count,
                    project.homePath(),
                )

                labels = []
                for symbol in symbols:
                    symbol_label = symbol["title"]
                    if show_feature_count:
                        match_label = self.match_label_feature_count(symbol_label)
                        if match_label:
                            symbol_label = match_label.group(1)
                        else:
                            logger.info(
                                "GetLegendGraphic JSON: symbol label does not match '{}' '{}'".format(
                                    self.FEATURE_COUNT_REGEXP, symbol["title"]
                                )
                            )
                    labels.append(symbol_label)

                for symbol, category in zip(symbols, self._match_categories(labels, categories)):
                    if category is not None:
                        symbol["ruleKey"] = category.ruleKey
                        symbol["checked"] = category.checked
                        symbol["parentRuleKey"] = category.parentRuleKey
                        symbol["expression"] = category.expression
                        if symbol["title"] != category.title:
                            symbol["title"] = category.title

                    new_symbols.append(symbol)

                if "symbols" in json_data["nodes"][0]:
                    json_data["nodes"][0]["symbols"] = new_symbols
                else:
                    json_data["nodes"] = new_symbols

                handler.clearBody()
                handler.appendBody(json.dumps(json_data).encode("utf8"))
        except Exception:
            logger.critical(
                f"Error getting layer '{layer_name}' when setting up legend graphic for "
                "json output when configuring "
                "OWS call: {traceback.format_exc()}",
            )
            # Let QGIS server handle error 500
            raise
        finally:
            if layer is not None and style and current_style and style != current_style:
                unwrap(layer.styleManager()).setCurrentStyle(current_style)

    @classmethod
    def _match_categories(
        cls,
        labels: List[str],
        categories: List[Category],
    ) -> List[Optional[Category]]:
        """Match the JSON legend symbols with the renderer legend items.

        Labels are not unique, a rule based renderer can reuse one in several
        branches, so both lists being in the renderer order, each category is
        consumed once. The JSON can hold fewer symbols than the renderer has
        items, hence a forward search instead of an index match.
        """
        matches: List[Optional[Category]] = []
        cursor = 0
        for label in labels:
            match = None
            for index in range(cursor, len(categories)):
                if categories[index].label == label:
                    match = categories[index]
                    cursor = index + 1
                    break

            if match is None:
                # Legend nodes reordered or relabelled in the project
                match = next((item for item in categories if item.label == label), None)

            matches.append(match)

        return matches

    @classmethod
    def _extract_categories(
        cls,
        layer: QgsVectorLayer,
        show_feature_count: bool = False,
        project_path: str = "",
    ) -> List[Category]:
        """Extract categories from the layer legend, in the renderer order."""
        renderer = unwrap(layer.renderer())
        categories: List[Category] = []
        for item in renderer.legendSymbolItems():
            # Calculate title if show_feature_count is activated
            # It seems that in QGIS Server 3.22 countSymbolFeatures is not used for JSON
            title = item.label()
            if show_feature_count:
                estimated_count = unwrap(layer.dataProvider()).uri().useEstimatedMetadata()
                count = layer.featureCount(item.ruleKey())
                title += " [{}{}]".format(
                    "≈" if estimated_count else "",
                    count if count != -1 else "N/A",
                )

            expression, result = renderer.legendKeyToExpression(item.ruleKey(), layer)
            if not result:
                logger.warning(
                    f"The expression in the project '{project_path}', layer '{layer.name()}' has not "
                    f"been generated correctly, setting the expression to an empty string",
                )
                expression = ""

            categories.append(
                Category(
                    label=item.label(),
                    ruleKey=item.ruleKey(),
                    checked=renderer.legendSymbolItemChecked(item.ruleKey()),
                    parentRuleKey=item.parentRuleKey(),
                    scaleMaxDenom=item.scaleMaxDenom(),
                    scaleMinDenom=item.scaleMinDenom(),
                    expression=expression,
                    title=title,
                )
            )
        return categories
