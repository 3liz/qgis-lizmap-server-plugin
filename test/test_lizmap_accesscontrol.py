__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import logging
import os

from pathlib import Path
from test.utils import _build_query_string, _check_request, OWSResponse
from test.conftest import client as cl

from qgis.core import QgsVectorLayer

from lizmap_server.tos_definitions import (
    BING_KEY,
    GOOGLE_KEY,
    strict_tos_check_key,
)

LOGGER = logging.getLogger('server')
PROJECT_FILE = "france_parts.qgs"
PROJECT_LIZ_FILE = "france_parts_liz.qgs"
PROJECT_FILE_GROUP_V = "france_parts_liz_grp_v.qgs"
PROJECT_TOS_PROVIDERS = "external_providers_tos.qgs"


def test_no_lizmap_config(client):
    """
    Test Access Control response with a project without
    lizmap config
    """
    # Make a request without LIZMAP_USER_GROUPS
    qs = {
        "SERVICE": "WMS",
        "REQUEST": "GetCapabilities",
        "MAP": PROJECT_FILE,
    }
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with 1 group
    # With some different cases in the group
    qs["Lizma_User_grOUPS"] = "test1"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with 2 groups
    qs["LIZMAP_USER_GROUPS"] = "test1,test2"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2


def test_invalid_layer(client):
    """ Test WMS has some invalid layer but WFS has not. """
    project_invalid = "legend_invalid.qgs"
    qs = {
        "SERVICE": "WMS",
        "REQUEST": "GetCapabilities",
        "MAP": project_invalid,
    }
    rv = client.get(_build_query_string(qs), project_invalid)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 5, len(layers)

    # Layer is WMS
    layer = "unique_symbol"
    assert layer in rv.content.decode('utf-8')

    assert 'raster' in rv.content.decode('utf-8')

    qs['SERVICE'] = "WFS"
    rv = client.get(_build_query_string(qs), project_invalid)
    _check_request(rv, 'text/xml')

    # Layer is not in WFS
    assert layer not in rv.content.decode('utf-8')


def test_no_group_visibility(client):
    """
    Test Access Control response with a project with
    lizmap config without a group visibility
    """
    # Make a request with LIZMAP_USER_GROUPS
    qs = {
        "SERVICE": "WMS",
        "REQUEST": "GetCapabilities",
        "MAP": PROJECT_FILE,
    }
    rv = client.get(_build_query_string(qs), PROJECT_LIZ_FILE)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with 1 group
    qs['LIZMAP_USER_GROUPS'] = 'test1'
    rv = client.get(_build_query_string(qs), PROJECT_LIZ_FILE)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request without LIZMAP_USER_GROUPS with 2 groups
    qs['LIZMAP_USER_GROUPS'] = 'test1,test2'
    rv = client.get(_build_query_string(qs), PROJECT_LIZ_FILE)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2


def test_group_visibility(client):
    """
    Test Access Control response with a project with
    lizmap config with a group visibility
    """
    # Make a request with LIZMAP_USER_GROUPS
    qs = {
        "SERVICE": "WMS",
        "REQUEST": "GetCapabilities",
        "MAP": PROJECT_FILE_GROUP_V,
    }
    rv = client.get(_build_query_string(qs), PROJECT_FILE_GROUP_V)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with 1 group not authorized
    qs["LIZMAP_USER_GROUPS"] = "test1"
    rv = client.get(_build_query_string(qs), PROJECT_FILE_GROUP_V)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 1

    # Make a request with LIZMAP_USER_GROUPS with 2 group authorized
    qs["LIZMAP_USER_GROUPS"] = "test2"
    rv = client.get(_build_query_string(qs), PROJECT_FILE_GROUP_V)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request without LIZMAP_USER_GROUPS with 2 groups which 1 is authorized
    qs["LIZMAP_USER_GROUPS"] = "test1,test2"
    rv = client.get(_build_query_string(qs), PROJECT_FILE_GROUP_V)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with anonymous group not authorized
    qs["LIZMAP_USER_GROUPS"] = ""
    rv = client.get(_build_query_string(qs), PROJECT_FILE_GROUP_V)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 1


def test_filter_by_polygon_wfs_getfeature(client):
    """ Test the filter by polygon access right with WFS GetFeature. """
    # Check the layer itself about the number of features
    file_path = Path(__file__).parent.joinpath(
        'data', 'test_filter_layer_data_by_polygon_for_groups', 'bakeries.shp')
    layer = QgsVectorLayer(str(file_path), 'test', 'ogr')
    expected_source = 178
    assert expected_source == layer.featureCount()

    # Check now with the project and the Lizmap config and no groups
    project = "test_filter_layer_data_by_polygon_for_groups.qgs"
    qs = f"?SERVICE=WFS&REQUEST=GetFeature&MAP={project}&TYPENAME=shop_bakery"
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == expected_source

    # Filter the layer with montferrier-sur-lez with a single bakery
    # display_and_editing
    qs += "&LIZMAP_USER_GROUPS=montferrier-sur-lez"
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 1

    # Filter the layer with montferrier-sur-lez with a single town hall
    file_path = Path(__file__).parent.joinpath(
        'data', 'test_filter_layer_data_by_polygon_for_groups', 'townhalls_EPSG2154.shp')
    layer = QgsVectorLayer(str(file_path), 'test', 'ogr')
    expected_source = 27
    assert expected_source == layer.featureCount()

    # editing only
    qs = f"?SERVICE=WFS&REQUEST=GetFeature&MAP={project}&TYPENAME=townhalls_EPSG2154"
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == expected_source

    # with groups, still all features because editing only
    qs += "&LIZMAP_USER_GROUPS=montferrier-sur-lez"
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == expected_source

    # with groups and edition
    rv = client.get(qs, project, headers={'X-Lizmap-Edition-Context': 'TRUE'})
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 1


def test_filter_by_polygon_wms(client):
    project = "test_filter_layer_data_by_polygon_for_groups.qgs"

    # Transparent GetMap
    qs = '?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=shop_bakery&STYLES=d%C3%A9faut'
    qs += '&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&FORMAT=image%2Fpng&DPI=96&TRANSPARENT=TRUE'
    qs += '&CRS=EPSG%3A3857&BBOX=429949.78991818504,5413886.938768325,432661.7745088209,5416400.485462084&WIDTH=410&HEIGHT=380'
    rv = client.get(qs, project)
    img = _check_request(rv, 'image/png')

    # save image for debugging
    # img.save(client.datapath.join('transparent.png').strpath)
    assert img.format == 'PNG'
    assert img.width == 410
    assert img.height == 380
    # getcolors returns None if the image contains more than maxcolors
    # so with maxcolors = 1, getcolors returns None if the image is not
    # a single color image
    colors = img.getcolors(1)
    assert colors is not None
    assert len(colors) == 1
    # single color, every pixel are the same
    assert colors[0][0] == 410 * 380
    assert colors[0][1][0] == 0
    assert colors[0][1][1] == 0
    assert colors[0][1][2] == 0
    assert colors[0][1][3] == 0

    # WMS GetMap with 2 points (Montferrier-sur-Lez and Castries)
    qs = '?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=shop_bakery&STYLES=d%C3%A9faut'
    qs += '&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&FORMAT=image%2Fpng&DPI=96&TRANSPARENT=TRUE'
    qs += '&CRS=EPSG%3A3857&BBOX=429287.80910808814,5411955.107681999,431999.793698724,5414468.654375758&WIDTH=410&HEIGHT=380'
    rv = client.get(qs, project)
    img = _check_request(rv, 'image/png')

    # save image for debugging
    # img.save(client.datapath.join('Montferrier-Castries.png').strpath)
    assert img.format == 'PNG'
    assert img.width == 410
    assert img.height == 380
    # remove transparency to reduce the number of colors
    # img = img.convert('RGB')
    colors = img.getcolors()
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # more colors than for the transparency
    assert len(colors) == 21
    # less than 99,899% for the most important color
    assert colors[0][0] < 410 * 380 * 0.99899
    # more than 99,799% for the most important color
    assert colors[0][0] > 410 * 380 * 0.99799
    assert colors[0][1][0] == 0
    assert colors[0][1][1] == 0
    assert colors[0][1][2] == 0
    assert colors[0][1][3] == 0

    # Filter
    qs += "&LIZMAP_USER_GROUPS=montferrier-sur-lez"
    rv = client.get(qs, project)
    img = _check_request(rv, 'image/png')

    # save image for debugging
    # img.save(client.datapath.join('Montferrier.png').strpath)
    assert img.format == 'PNG'
    assert img.width == 410
    assert img.height == 380
    # remove transparency to reduce the number of colors
    # img = img.convert('RGB')
    colors = img.getcolors()
    assert colors is not None
    colors.sort(key=lambda color: color[0], reverse=True)
    # more colors than for the transparency
    assert len(colors) == 21
    # more than 99,899% for the most important color
    assert colors[0][0] > 410 * 380 * 0.99899
    assert colors[0][1][0] == 0
    assert colors[0][1][1] == 0
    assert colors[0][1][2] == 0
    assert colors[0][1][3] == 0

    # Montferrier sur Lez
    qs = '?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&LAYERS=shop_bakery&QUERY_LAYERS=shop_bakery&STYLES=d%C3%A9faut'
    qs += '&FEATURE_COUNT=10&BBOX=429287.80910808814,5411955.107681999,431999.793698724,5414468.654375758&WIDTH=410&HEIGHT=380'
    qs += '&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&FORMAT=image%2Fpng&INFO_FORMAT=text%2Fxml&CRS=EPSG%3A3857&I=95&J=12'
    qs += '&FI_POINT_TOLERANCE=25&FI_LINE_TOLERANCE=10&FI_POLYGON_TOLERANCE=5'
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    assert rv.xml.tag == 'GetFeatureInfoResponse'

    features = rv.xpath('//Feature')
    assert features is not None
    assert len(features) == 1

    # Filter
    qs += "&LIZMAP_USER_GROUPS=montferrier-sur-lez"
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')
    assert rv.xml.tag == 'GetFeatureInfoResponse'

    features = rv.xpath('//Feature')
    assert features is not None
    assert len(features) == 1

    # Castries
    qs = '?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&LAYERS=shop_bakery&QUERY_LAYERS=shop_bakery&STYLES=d%C3%A9faut'
    qs += '&FEATURE_COUNT=10&BBOX=429287.80910808814,5411955.107681999,431999.793698724,5414468.654375758&WIDTH=410&HEIGHT=380'
    qs += '&EXCEPTIONS=application%2Fvnd.ogc.se_inimage&FORMAT=image%2Fpng&INFO_FORMAT=text%2Fxml&CRS=EPSG%3A3857&I=372&J=338'
    qs += '&FI_POINT_TOLERANCE=25&FI_LINE_TOLERANCE=10&FI_POLYGON_TOLERANCE=5'
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    assert rv.xml.tag == 'GetFeatureInfoResponse'

    features = rv.xpath('//Feature')
    assert features is not None
    assert len(features) == 1

    # Filter
    qs += "&LIZMAP_USER_GROUPS=montferrier-sur-lez"
    rv = client.get(qs, project)
    _check_request(rv, 'text/xml')

    assert rv.xml.tag == 'GetFeatureInfoResponse'

    features = rv.xpath('//Feature')
    assert features is not None
    assert len(features) == 0


def test_group_visibility_headers(client):
    """
    Test Access Control response with a project with
    lizmap config with a group visibility
    and groups provided in headers
    """
    projectfile = "france_parts_liz_grp_v.qgs"

    # Make a request without LIZMAP_USER_GROUPS
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts_liz_grp_v.qgs"
    rv = client.get(qs, projectfile)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with 1 group not authorized
    headers = {'X-Lizmap-User-Groups': 'test1'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 1

    # Make a request with LIZMAP_USER_GROUPS with 1 group authorized
    headers = {'X-Lizmap-User-Groups': 'test2'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with 2 groups which 1 is authorized
    headers = {'X-Lizmap-User-Groups': 'test1,test2'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 2

    # Make a request with LIZMAP_USER_GROUPS with anonymous group not authorized
    headers = {'X-Lizmap-User-Groups': ''}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//wms:Layer')
    assert layers is not None
    assert len(layers) == 1


def test_layer_filter_login(client):

    # Project without config
    projectfile = "france_parts.qgs"

    qs = "?SERVICE=WFS&REQUEST=GetCapabilities&MAP=france_parts.qgs"
    rv = client.get(qs, projectfile)
    _check_request(rv, 'text/xml')

    qs = "?SERVICE=WFS&REQUEST=GetFeature&MAP=france_parts.qgs&TYPENAME=france_parts"
    rv = client.get(qs, projectfile)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    headers = {'X-Lizmap-User-Groups': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    # Project with config but without login filter
    projectfile = "france_parts_liz.qgs"

    qs = "?SERVICE=WFS&REQUEST=GetFeature&MAP=france_parts_liz.qgs&TYPENAME=france_parts"
    rv = client.get(qs, projectfile)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    headers = {'X-Lizmap-User-Groups': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    # Project with config with group filter
    projectfile = "france_parts_liz_filter_group.qgs"

    qs = "?SERVICE=WFS&REQUEST=GetFeature&MAP=france_parts_liz_filter_group.qgs&TYPENAME=france_parts"
    rv = client.get(qs, projectfile)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    headers = {'X-Lizmap-User-Groups': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 1

    headers = {'X-Lizmap-User-Groups': 'Bretagne, Centre, test1'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 2

    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 0

    # Project with config with login filter
    projectfile = "france_parts_liz_filter_login.qgs"

    qs = "?SERVICE=WFS&REQUEST=GetFeature&MAP=france_parts_liz_filter_login.qgs&TYPENAME=france_parts"
    rv = client.get(qs, projectfile)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 4

    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 1

    headers = {'X-Lizmap-User-Groups': 'Bretagne, Centre, test1', 'X-Lizmap-User': 'test'}
    rv = client.get(qs, projectfile, headers)
    _check_request(rv, 'text/xml')

    layers = rv.xpath('//gml:featureMember')
    assert layers is not None
    assert len(layers) == 0


def _make_get_capabilities_tos_layers(client: cl, strict: bool) -> OWSResponse:
    """ Make the GetCapabilities request for TOS layers. """
    os.environ[strict_tos_check_key(GOOGLE_KEY)] = str(strict)
    os.environ[strict_tos_check_key(BING_KEY)] = str(strict)
    qs = {
        "SERVICE": "WMS",
        "REQUEST": "GetCapabilities",
        "MAP": PROJECT_TOS_PROVIDERS,
    }
    rv = client.get(_build_query_string(qs), PROJECT_TOS_PROVIDERS)
    _check_request(rv, 'text/xml')
    del os.environ[strict_tos_check_key(GOOGLE_KEY)]
    del os.environ[strict_tos_check_key(BING_KEY)]
    return rv


def test_tos_strict_layers_false(client):
    """ Test TOS layers restricted. """
    rv = _make_get_capabilities_tos_layers(client, False)
    content = rv.content.decode('utf-8')
    layers = rv.xpath('//wms:Layer')
    assert len(layers) == 2
    assert "osm" in content
    assert "google-satellite" not in content
    assert "bing-map" not in content
    assert "bing-satellite" not in content


def tet_tos_strict_layers_true(client):
    """ Test TOS layers not restricted. """
    rv = _make_get_capabilities_tos_layers(client, True)
    content = rv.content.decode('utf-8')
    layers = rv.xpath('//wms:Layer')
    assert len(layers) == 5
    assert "osm" in content
    assert "google-satellite" in content
    assert "bing-map" in content
    assert "bing-satellite" in content
