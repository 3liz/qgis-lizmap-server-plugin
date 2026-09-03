"""Tests for the GetLegendGraphic and the legend ON/OFF filters."""

import json

import pytest

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsProject,
    QgsRendererCategory,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)

from lizmap_server.get_legend_graphic import GetLegendGraphicFilter
from lizmap_server.legend_onoff_filter import LegendOnOffAccessControl, LegendOnOffFilter


class FakeRequestHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, params=None, body=b""):
        self._params = params if params is not None else {}
        self._body = body

    def parameterMap(self):
        return self._params

    def body(self):
        return self._body

    def clearBody(self):
        self._body = b""

    def appendBody(self, body):
        self._body += body

    def json(self):
        return json.loads(self._body.decode())


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, handler):
        self._handler = handler

    def requestHandler(self):
        return self._handler


@pytest.fixture
def project():
    """A clean QGIS project."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


def _categorized_layer(name="categorized"):
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer&field=cat:string", name, "memory")
    assert layer.isValid()

    def symbol():
        return QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.PointGeometry)

    categories = [
        QgsRendererCategory("a", symbol(), "A"),
        QgsRendererCategory("b", symbol(), "B"),
    ]
    layer.setRenderer(QgsCategorizedSymbolRenderer("cat", categories))
    return layer


def _legend_filter(client, handler):
    legend = GetLegendGraphicFilter(client.server.serverInterface())
    legend.serverInterface = lambda: FakeServerInterface(handler)
    return legend


BASE_PARAMS = {
    "SERVICE": "WMS",
    "REQUEST": "GETLEGENDGRAPHIC",
    "FORMAT": "APPLICATION/JSON",
}


def _params(**kwargs):
    params = dict(BASE_PARAMS)
    params.update(kwargs)
    return params


#
# GetLegendGraphic filter
#


def test_legend_without_handler(client):
    """Without any request handler, the filter is skipped."""
    legend = GetLegendGraphicFilter(client.server.serverInterface())
    legend.serverInterface = lambda: FakeServerInterface(None)

    assert legend.responseComplete() is None


@pytest.mark.parametrize(
    "params",
    [
        {"SERVICE": "WFS"},
        {"REQUEST": "GETCAPABILITIES"},
        {"FORMAT": "IMAGE/PNG"},
        {"LAYER": ""},
        {"LAYER": "a,b"},
        {"LAYER": "does_not_exist"},
    ],
)
def test_legend_skipped_requests(client, project, params):
    """The filter only handles a single layer JSON GetLegendGraphic."""
    handler = FakeRequestHandler(_params(**{"LAYER": "categorized", **params}), body=b"{}")
    legend = _legend_filter(client, handler)

    assert legend.responseComplete() is None
    assert handler.body() == b"{}"


def test_legend_not_a_vector_layer(client, project, rootdir):
    """A raster layer is skipped."""
    from qgis.core import QgsRasterLayer

    layer = QgsRasterLayer(str(rootdir.joinpath("data/raster.asc")), "raster", "gdal")
    assert layer.isValid()
    project.addMapLayer(layer)

    handler = FakeRequestHandler(_params(LAYER="raster"), body=b"{}")
    legend = _legend_filter(client, handler)

    assert legend.responseComplete() is None
    assert handler.body() == b"{}"


def test_legend_invalid_layer(client, project):
    """An invalid layer returns a warning icon."""
    layer = QgsVectorLayer("Point?crs=epsg:4326", "invalid", "unknown_provider")
    assert not layer.isValid()
    project.addMapLayer(layer)

    handler = FakeRequestHandler(_params(LAYER="invalid"), body=b"{}")
    legend = _legend_filter(client, handler)
    legend.responseComplete()

    content = handler.json()
    assert content["nodes"][0]["valid"] is False
    assert content["nodes"][0]["icon"]


def test_legend_nodes_without_symbols(client, project):
    """A legend without any 'symbols' entry uses the nodes."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    body = json.dumps(
        {
            "title": "",
            "nodes": [
                {"type": "symbol", "title": "A"},
                {"type": "symbol", "title": "B"},
            ],
        }
    ).encode()

    handler = FakeRequestHandler(_params(LAYER="categorized"), body=body)
    legend = _legend_filter(client, handler)
    legend.responseComplete()

    nodes = handler.json()["nodes"]
    assert nodes[0]["ruleKey"]
    assert nodes[0]["expression"] == "\"cat\" = 'a'"
    assert nodes[1]["expression"] == "\"cat\" = 'b'"


def test_legend_with_feature_count(client, project):
    """The feature count is stripped from the symbol titles."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    body = json.dumps(
        {
            "title": "",
            "nodes": [
                {
                    "type": "layer",
                    "title": "categorized",
                    "symbols": [
                        {"title": "A [2]"},
                        # Does not match the feature count pattern
                        {"title": "B"},
                    ],
                },
            ],
        }
    ).encode()

    handler = FakeRequestHandler(_params(LAYER="categorized", SHOWFEATURECOUNT="TRUE"), body=body)
    legend = _legend_filter(client, handler)
    legend.responseComplete()

    symbols = handler.json()["nodes"][0]["symbols"]
    # The feature count has been recomputed from the layer
    assert symbols[0]["title"] == "A [0]"
    assert symbols[0]["ruleKey"]
    # The label did not match the feature count pattern but is still resolved
    assert symbols[1]["title"] == "B [0]"
    assert symbols[1]["ruleKey"]


def test_legend_with_style(client, project):
    """The requested style is restored at the end of the request."""
    layer = _categorized_layer()
    style_manager = layer.styleManager()
    assert style_manager.addStyleFromLayer("other")
    project.addMapLayer(layer)

    body = json.dumps({"title": "", "nodes": [{"title": "A"}]}).encode()

    handler = FakeRequestHandler(_params(LAYER="categorized", STYLES="other"), body=body)
    legend = _legend_filter(client, handler)
    legend.responseComplete()

    # The current style has been restored
    assert style_manager.currentStyle() == "default"


def test_legend_invalid_body(client, project):
    """A response body which is not json must raise."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    handler = FakeRequestHandler(_params(LAYER="categorized"), body=b"not json")
    legend = _legend_filter(client, handler)

    with pytest.raises(Exception):
        legend.responseComplete()


def test_legend_expression_error(client):
    """A legend key which cannot be converted to an expression is skipped."""

    class FakeItem:
        def label(self):
            return "A label"

        def ruleKey(self):
            return "a-rule-key"

        def parentRuleKey(self):
            return ""

        def scaleMaxDenom(self):
            return 0

        def scaleMinDenom(self):
            return 0

    class FakeRenderer:
        def legendSymbolItems(self):
            return [FakeItem(), FakeItem()]

        def legendKeyToExpression(self, key, layer):
            return "an expression", False

        def legendSymbolItemChecked(self, key):
            return True

    class FakeLayer:
        def renderer(self):
            return FakeRenderer()

        def name(self):
            return "a layer"

    categories = GetLegendGraphicFilter._extract_categories(FakeLayer())
    assert categories["A label"].expression == ""


#
# Legend ON/OFF
#


def test_legend_onoff_setup_legend(project):
    """The legend keys are only applied on the matching layer."""
    layer = _categorized_layer()
    layer.serverProperties().setShortName("short_name")
    project.addMapLayer(layer)

    keys = [item.ruleKey() for item in layer.renderer().legendSymbolItems()]

    # An empty layer name or key list is skipped
    LegendOnOffAccessControl._setup_legend(layer, f":{keys[0]};categorized:", False)
    assert layer.renderer().legendSymbolItemChecked(keys[0])

    # Another layer is skipped
    LegendOnOffAccessControl._setup_legend(layer, f"another_layer:{keys[0]}", False)
    assert layer.renderer().legendSymbolItemChecked(keys[0])

    # The layer short name matches
    LegendOnOffAccessControl._setup_legend(layer, f"short_name:{keys[0]}", False)
    assert not layer.renderer().legendSymbolItemChecked(keys[0])

    # The layer id matches
    LegendOnOffAccessControl._setup_legend(layer, f"{layer.id()}:{keys[0]}", True)
    assert layer.renderer().legendSymbolItemChecked(keys[0])


def test_legend_onoff_permissions(client, project):
    """The style is chosen from the request parameters."""
    layer = _categorized_layer()
    layer.serverProperties().setShortName("short_name")
    assert layer.styleManager().addStyleFromLayer("other")
    project.addMapLayer(layer)

    keys = [item.ruleKey() for item in layer.renderer().legendSymbolItems()]

    def _permissions(params):
        acl = LegendOnOffAccessControl(client.server.serverInterface())
        acl.iface = FakeServerInterface(FakeRequestHandler(params))
        return acl.layerPermissions(layer)

    # By the layer short name
    _permissions({"LAYERS": "short_name", "STYLES": "other"})
    assert layer.styleManager().currentStyle() == "other"

    # By the layer name
    _permissions({"LAYERS": "categorized", "STYLES": "default"})
    assert layer.styleManager().currentStyle() == "default"

    # By the layer id
    _permissions({"LAYERS": layer.id(), "STYLES": "other"})
    assert layer.styleManager().currentStyle() == "other"

    # Restore the default style, and switch the legend off
    _permissions(
        {
            "LAYERS": "categorized",
            "STYLES": "default",
            "LEGEND_OFF": f"categorized:{keys[0]}",
        }
    )
    assert not layer.renderer().legendSymbolItemChecked(keys[0])

    _permissions(
        {
            "LAYERS": "categorized",
            "STYLES": "default",
            "LEGEND_ON": f"categorized:{keys[0]}",
        }
    )
    assert layer.renderer().legendSymbolItemChecked(keys[0])


def test_legend_onoff_reset(project):
    """The legend is restored at the end of the request."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    keys = [item.ruleKey() for item in layer.renderer().legendSymbolItems()]
    layer.renderer().checkLegendSymbolItem(keys[0], False)

    # Not a legend definition
    LegendOnOffFilter._reset_legend("", project)
    LegendOnOffFilter._reset_legend("no_colon", project)

    # Empty layer name or key list
    LegendOnOffFilter._reset_legend(f":{keys[0]};categorized:", project)

    # Unknown layer
    LegendOnOffFilter._reset_legend(f"unknown_layer:{keys[0]}", project)
    assert not layer.renderer().legendSymbolItemChecked(keys[0])

    # The layer is found
    LegendOnOffFilter._reset_legend(f"categorized:{keys[0]}", project)
    assert layer.renderer().legendSymbolItemChecked(keys[0])


def test_legend_onoff_response_complete(client, project):
    """The filter restores the legend from the request parameters."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    keys = [item.ruleKey() for item in layer.renderer().legendSymbolItems()]
    layer.renderer().checkLegendSymbolItem(keys[0], False)

    def _complete(params):
        legend_filter = LegendOnOffFilter(client.server.serverInterface())
        legend_filter.serverInterface = lambda: FakeServerInterface(FakeRequestHandler(params))
        return legend_filter.responseComplete()

    # No legend parameter
    _complete({})
    assert not layer.renderer().legendSymbolItemChecked(keys[0])

    _complete({"LEGEND_OFF": f"categorized:{keys[0]}"})
    assert layer.renderer().legendSymbolItemChecked(keys[0])

    layer.renderer().checkLegendSymbolItem(keys[0], False)
    _complete({"LEGEND_ON": f"categorized:{keys[0]}"})
    assert layer.renderer().legendSymbolItemChecked(keys[0])


def test_legend_onoff_without_handler(client):
    """Without any request handler, the filter is skipped."""
    legend_filter = LegendOnOffFilter(client.server.serverInterface())
    legend_filter.serverInterface = lambda: FakeServerInterface(None)

    assert legend_filter.responseComplete() is None


def test_legend_onoff_error(client):
    """An error must be logged and re-raised."""

    class BrokenHandler:
        def parameterMap(self):
            raise RuntimeError("Broken")

    legend_filter = LegendOnOffFilter(client.server.serverInterface())
    legend_filter.serverInterface = lambda: FakeServerInterface(BrokenHandler())

    with pytest.raises(RuntimeError, match="Broken"):
        legend_filter.responseComplete()


def test_legend_unknown_symbol(client, project):
    """A symbol which does not match any category is left untouched."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    body = json.dumps(
        {
            "title": "",
            "nodes": [
                {
                    "type": "layer",
                    "title": "categorized",
                    "symbols": [{"title": "Not a category"}],
                },
            ],
        }
    ).encode()

    handler = FakeRequestHandler(_params(LAYER="categorized"), body=body)
    legend = _legend_filter(client, handler)
    legend.responseComplete()

    symbols = handler.json()["nodes"][0]["symbols"]
    assert symbols == [{"title": "Not a category"}]
