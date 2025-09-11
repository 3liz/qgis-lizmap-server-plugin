import io
import logging

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
    """ Test unique symbol for layer. """
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs['LAYERS'] = 'unique_symbol'
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('image/png') == 0


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
    assert len(colors) < default_color_numbers, f'not {len(colors)} < {default_color_numbers}'


def test_valid_raster_layer(client):
    """ Test valid raster layer. """
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs['LAYERS'] = 'raster'
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('image/png') == 0


def test_invalid_layer_symbol_layer(client):
    """ Test unique symbol for layer. """
    PROJECT_INVALID = "legend_invalid.qgs"
    project = client.get_project(PROJECT_INVALID)

    qs = dict(BASE_QUERY)
    qs['LAYERS'] = 'unique_symbol'
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('image/png') == 0


def test_no_geom_layer(client):
    """ Test no geometry for layer. """
    project = client.get_project(PROJECT)

    qs = dict(BASE_QUERY)
    qs['LAYERS'] = 'no_geom'
    rv = client.get_with_project(_build_query_string(qs), project)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('image/png') == 0
