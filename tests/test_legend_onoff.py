import io
import logging

import pytest

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsProject,
    QgsRasterLayer,
    QgsRendererCategory,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.server import QgsBufferServerResponse

from lizmap_server.legend_onoff_filter import LegendOnOffAccessControl, LegendOnOffFilter

from tests.utils import _build_query_string

from PIL import Image

LOGGER = logging.getLogger("server")

PROJECT = "legend.qgs"

BASE_QUERY = {
    "MAP": PROJECT,
    "SERVICE": "WMS",
    "REQUEST": "GetMap",
    "VERSION": "1.3.0",
    "EXCEPTIONS": "application%2Fvnd.ogc.se_inimage",
    "FORMAT": "image%2Fpng",
    "DPI": "96",
    "TRANSPARENT": "TRUE",
    "CRS": "EPSG%3A4326",
    "BBOX": "47.51884820641368,-1.660771898670815,48.49033140295455,-0.35117445235345235",
    "WIDTH": "550",
    "HEIGHT": "408",
}


def test_unique_symbol(client):
    """Test unique symbol for layer."""
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "unique_symbol"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0


def test_categorized_symbol(client):
    """Test categorized symbol for layer."""
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "categorized"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_categorized-1.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    default_color_numbers = len(colors)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "categorized"
    qs["LEGEND_ON"] = "categorized:1"
    qs["LEGEND_OFF"] = "categorized:0,2,3,4"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_categorized_onoff.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # less colors because 1 feature displayed
    assert len(colors) < default_color_numbers, f"not {len(colors)} < {default_color_numbers}"

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "categorized"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_categorized-2.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # same colors as the first request - the legend has been well reset
    assert len(colors) == default_color_numbers, f"{len(colors)} != {default_color_numbers}"

    # REQUEST with new loaded project (no cache)
    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "categorized"
    qs["LEGEND_ON"] = "categorized:1"
    qs["LEGEND_OFF"] = "categorized:0,2,3,4"
    rv = client.get(_build_query_string(qs), PROJECT)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_categorized_onoff.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # less colors because 1 feature displayed
    assert len(colors) < default_color_numbers, f"not {len(colors)} < {default_color_numbers}"


def test_simple_rule_based(client):
    """Test rule based layer, simple conversion from categorized."""
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "rule_based"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_rule_based-1.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    default_color_numbers = len(colors)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "rule_based"
    qs["LEGEND_ON"] = "rule_based:{49db22fd-3aed-495d-9140-4b82f50fdcfd}"
    qs["LEGEND_OFF"] = (
        "rule_based:{1e75ef9b-1c18-46c1-b7f7-b16efc5bb791},{37b9b766-5309-4617-b0a4-1122168cbfd0},{bd0ace82-eee5-46c3-ad70-f8ecb7d50bb3},{77b34ffc-2198-4450-8e4d-270df282a81b}"
    )
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_rule_based_onoff.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # less colors because 1 feature displayed
    assert len(colors) < default_color_numbers, f"not {len(colors)} < {default_color_numbers}"

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "categorized"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_rule_based-2.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # same colors as the first request - the legend has been well reset
    assert len(colors) == default_color_numbers, f"{len(colors)} != {default_color_numbers}"

    # REQUEST with new loaded project (no cache)
    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "rule_based"
    qs["LEGEND_ON"] = "rule_based:{49db22fd-3aed-495d-9140-4b82f50fdcfd}"
    qs["LEGEND_OFF"] = (
        "rule_based:{1e75ef9b-1c18-46c1-b7f7-b16efc5bb791},{37b9b766-5309-4617-b0a4-1122168cbfd0},{bd0ace82-eee5-46c3-ad70-f8ecb7d50bb3},{77b34ffc-2198-4450-8e4d-270df282a81b}"
    )
    rv = client.get(_build_query_string(qs), PROJECT)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0

    img = Image.open(io.BytesIO(rv.content))
    # save image for debugging
    # img.save(client.datapath.join('legend_rule_based_onoff.png').strpath)
    assert img.format == "PNG"
    assert img.width == 550
    assert img.height == 408
    # remove transparency to reduce the number of colors
    img = img.convert("RGB")
    colors = img.getcolors(1024)
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # less colors because 1 feature displayed
    assert len(colors) < default_color_numbers, f"not {len(colors)} < {default_color_numbers}"


def test_valid_raster_layer(client):
    """Test valid raster layer."""
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "raster"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0


def test_invalid_layer_symbol_layer(client):
    """Test unique symbol for layer."""
    PROJECT_INVALID = "legend_invalid.qgs"
    project = client.get_project(PROJECT_INVALID)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "unique_symbol"
    rv = client.get_with_project(_build_query_string(qs), project)
    if Qgis.versionInt() < 40000:
        assert rv.status_code == 200
        assert rv.headers.get("Content-Type", "").find("image/png") == 0
    else:
        assert rv.status_code == 500


def test_no_geom_layer(client):
    """Test no geometry for layer."""
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs["LAYERS"] = "no_geom"
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("image/png") == 0


#
# Fakes
#


class FakeRequestHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, params=None, headers=None):
        self._params = params if params is not None else {}
        self._headers = headers if headers is not None else {}

    def parameterMap(self):
        return self._params

    def requestHeaders(self):
        return self._headers


class FakeAccessControls:
    """Minimal duck typing of a QgsAccessControlFilter chain."""

    def __init__(self, subset_string):
        self._subset_string = subset_string

    def extraSubsetString(self, layer):
        return self._subset_string


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, handler=None, subset_string=""):
        self._handler = handler
        self._access_controls = FakeAccessControls(subset_string)

    def requestHandler(self):
        return self._handler

    def accessControls(self):
        return self._access_controls


@pytest.fixture
def project():
    """A clean QGIS project instance."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


#
# Shared project state mutated per-request and not always restored
#


@pytest.fixture
def france_parts(rootdir, project):
    """The 'france_parts' layer, added to the project instance."""
    layer = QgsVectorLayer(
        str(rootdir.joinpath("data/france_parts/france_parts.shp")),
        "france_parts",
        "ogr",
    )
    assert layer.isValid()
    project.addMapLayer(layer)
    return layer


ACL_SUBSET = "\"NAME_1\" = 'Bretagne'"


def test_virtual_fields_restores_the_subset_string(project, france_parts, monkeypatch):
    """An exception in the feature loop must not leave the ACL filter installed."""
    from lizmap_server.expression_service import request_virtualfields as module

    def boom(*args, **kwargs):
        raise RuntimeError("Failure inside the feature loop")

    monkeypatch.setattr(module, "get_server_fid", boom)

    params = {"LAYER": "france_parts", "VIRTUALS": '{"a": "1"}'}
    with pytest.raises(RuntimeError):
        module.virtual_fields(
            params,
            QgsBufferServerResponse(),
            project,
            FakeServerInterface(subset_string=ACL_SUBSET),
        )

    assert france_parts.subsetString() == ""


def test_replace_expression_text_restores_the_subset_string(
    project,
    france_parts,
    monkeypatch,
):
    """The same, for the REPLACEEXPRESSIONTEXT request."""
    from lizmap_server.expression_service import request_replaceexpressiontext as module

    class Boom:
        @staticmethod
        def encodeValue(value):
            raise RuntimeError("Failure inside the feature loop")

    monkeypatch.setattr(module, "QgsJsonUtils", Boom)

    params = {
        "LAYER": "france_parts",
        "STRINGS": '["[% 1 + 1 %]"]',
        "FEATURE": '{"type": "Feature", "geometry": null, "properties": {"NAME_1": "Bretagne"}}',
    }
    with pytest.raises(RuntimeError):
        module.replace_expression_text(
            params,
            QgsBufferServerResponse(),
            project,
            FakeServerInterface(subset_string=ACL_SUBSET),
        )

    assert france_parts.subsetString() == ""


def _categorized_layer(name: str = "categorized") -> QgsVectorLayer:
    """A categorized vector layer, with two rule keys."""
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


@pytest.mark.xfail(reason="TODO: fix style restoration in LegendOnOffAccessControl")
def test_legend_onoff_restores_the_current_style(client, project):
    """The client supplied style must not stay on the shared project layer."""
    layer = _categorized_layer()
    assert layer.styleManager().addStyleFromLayer("other")
    layer.styleManager().setCurrentStyle("default")
    project.addMapLayer(layer)

    params = {"LAYERS": "categorized", "STYLES": "other"}

    access_control = LegendOnOffAccessControl(client.server.serverInterface())
    access_control.iface = FakeServerInterface(FakeRequestHandler(params))
    access_control.layerPermissions(layer)

    legend_filter = LegendOnOffFilter(client.server.serverInterface())
    legend_filter.serverInterface = lambda: FakeServerInterface(FakeRequestHandler(params))
    legend_filter.responseComplete()

    # The next request must not inherit the style of this one
    assert layer.styleManager().currentStyle() == "default"


@pytest.mark.parametrize("value", ("a", "a:b:c", "", ";", "a:b;c", ":", "a:"))
def test_malformed_legend_on_is_not_an_error(project, value):
    """A malformed LEGEND_ON must not raise: the request is unauthenticated."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    LegendOnOffAccessControl._setup_legend(layer, value, True)
    LegendOnOffFilter._reset_legend(value, project)


@pytest.mark.parametrize("parameter", ("LEGEND_ON", "LEGEND_OFF"))
def test_malformed_legend_parameter_in_permissions(client, project, parameter):
    """`layerPermissions` is called on every WMS request: it must not raise."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    access_control = LegendOnOffAccessControl(client.server.serverInterface())
    access_control.iface = FakeServerInterface(
        FakeRequestHandler({"LAYERS": "categorized", parameter: "categorized"}),
    )

    access_control.layerPermissions(layer)


def test_legend_on_a_raster_layer(client, project, rootdir):
    """A raster renderer has no 'checkLegendSymbolItem': it must be skipped."""
    raster = QgsRasterLayer(str(rootdir.joinpath("data/raster.asc")), "raster")
    assert raster.isValid()
    project.addMapLayer(raster)

    LegendOnOffAccessControl._setup_legend(raster, "raster:0", True)

    access_control = LegendOnOffAccessControl(client.server.serverInterface())
    access_control.iface = FakeServerInterface(
        FakeRequestHandler({"LAYERS": "raster", "LEGEND_ON": "raster:0"}),
    )

    access_control.layerPermissions(raster)
