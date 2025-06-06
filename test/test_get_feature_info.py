import logging
import xml.etree.ElementTree as ET

from test.utils import _build_query_string, _check_request

from qgis.core import Qgis
from xmldiff import main as xml_diff

LOGGER = logging.getLogger('server')

__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

PROJECT = "get_feature_info.qgs"
BBOX = "48.331869%2C-2.847776%2C48.971191%2C-0.659558"
BASE_QUERY = (
    f"?MAP={PROJECT}&"
    f"STYLES=d%C3%A9faut&"
    f"SERVICE=WMS&"
    f"VERSION=1.3.0"
    f"&REQUEST=GetFeatureInfo&"
    f"EXCEPTIONS=application%2Fvnd.ogc.se_inimage&"
    f"BBOX={BBOX}&"
    f"FI_POINT_TOLERANCE=25&"
    f"FI_LINE_TOLERANCE=10&"
    f"FI_POLYGON_TOLERANCE=5&"
    f"FEATURE_COUNT=10&"
    f"HEIGHT=537&"
    f"WIDTH=1838&"
    f"FORMAT=image%2Fpng&"
    f"CRS=EPSG%3A4326&"
    f"INFO_FORMAT=text%2Fxml&"
)

# Points
NO_FEATURE = "I=817&J=87&"
SINGLE_FEATURE = "I=1435&J=398&"

# Layers
LAYER_DEFAULT_POPUP = "default_popup"
DEFAULT_POPUP = f"LAYERS={LAYER_DEFAULT_POPUP}&QUERY_LAYERS={LAYER_DEFAULT_POPUP}&"

# The layer qgis_popup_shortname has a shortname customshortname
LAYER_QGIS_POPUP = "customshortname"
QGIS_POPUP = f"LAYERS={LAYER_QGIS_POPUP}&QUERY_LAYERS={LAYER_QGIS_POPUP}&"

LAYER_QGIS_FORM = "qgis_form"
QGIS_FORM = f"LAYERS={LAYER_QGIS_FORM}&QUERY_LAYERS={LAYER_QGIS_FORM}&"

LAYER_FORM_SHORTNAME = "customformshortname"
LAYER_FORM = f"LAYERS={LAYER_FORM_SHORTNAME}&QUERY_LAYERS={LAYER_FORM_SHORTNAME}&"


def test_no_get_feature_info_default_popup(client):
    """ Test the get feature info without a feature with default layer. """
    qs = BASE_QUERY + NO_FEATURE + DEFAULT_POPUP
    rv = client.get(qs, PROJECT)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('text/xml') == 0
    title_attribute = f'title="{LAYER_DEFAULT_POPUP}"' if Qgis.QGIS_VERSION_INT >= 33600 else ''
    expected = f'''
    <GetFeatureInfoResponse>
        <Layer name="{LAYER_DEFAULT_POPUP}" {title_attribute}/>
    </GetFeatureInfoResponse>
    '''
    diff = xml_diff.diff_texts(expected, rv.content)
    assert diff == [], diff


def test_single_get_feature_info_default_popup(client):
    """ Test the get feature info with a single feature with default layer. """
    qs = BASE_QUERY + SINGLE_FEATURE + DEFAULT_POPUP
    rv = client.get(qs, PROJECT)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('text/xml') == 0
    title_attribute = f'title="{LAYER_DEFAULT_POPUP}"' if Qgis.QGIS_VERSION_INT >= 33600 else ''
    expected = f'''
    <GetFeatureInfoResponse>
        <Layer name="{LAYER_DEFAULT_POPUP}" {title_attribute}>
            <Feature id="1">
                <Attribute name="OBJECTID" value="2662"/>
                <Attribute name="NAME_0" value="France"/>
                <Attribute name="VARNAME_1" value="Bretaa|Brittany"/>
                <Attribute name="Region" value="Bretagne"/>
                <Attribute name="Shape_Leng" value="18.39336934850"/>
                <Attribute name="Shape_Area" value="3.30646936365"/>
                <Attribute name="lwc_user" value="No user provided"/>
                <Attribute name="lwc_groups" value="No user groups provided"/>
            </Feature>
        </Layer>
    </GetFeatureInfoResponse>
    '''
    diff = xml_diff.diff_texts(expected, rv.content)
    assert diff == [], diff


def test_single_get_feature_info_default_popup_user(client):
    """ Test the get feature info with a single feature with default layer. """
    qs = BASE_QUERY + SINGLE_FEATURE + DEFAULT_POPUP
    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    rv = client.get(qs, PROJECT, headers)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('text/xml') == 0
    title_attribute = f'title="{LAYER_DEFAULT_POPUP}"' if Qgis.QGIS_VERSION_INT >= 33600 else ''
    expected = f'''
    <GetFeatureInfoResponse>
        <Layer name="{LAYER_DEFAULT_POPUP}" {title_attribute}>
            <Feature id="1">
                <Attribute name="OBJECTID" value="2662"/>
                <Attribute name="NAME_0" value="France"/>
                <Attribute name="VARNAME_1" value="Bretaa|Brittany"/>
                <Attribute name="Region" value="Bretagne"/>
                <Attribute name="Shape_Leng" value="18.39336934850"/>
                <Attribute name="Shape_Area" value="3.30646936365"/>
                <Attribute name="lwc_user" value="Bretagne"/>
                <Attribute name="lwc_groups" value="test1"/>
            </Feature>
        </Layer>
    </GetFeatureInfoResponse>
    '''
    diff = xml_diff.diff_texts(expected, rv.content)
    assert diff == [], diff


def test_single_get_feature_info_qgis_popup(client):
    """ Test the get feature info with a single feature with QGIS maptip. """
    qs = BASE_QUERY + SINGLE_FEATURE + QGIS_POPUP + "WITH_MAPTIP=true&"
    rv = client.get(qs, PROJECT)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('text/xml') == 0

    title_attribute = f'title="{LAYER_QGIS_POPUP}"' if Qgis.QGIS_VERSION_INT >= 33600 else ''

    # Note the line <TH>maptip</TH>
    expected = f'''
    <GetFeatureInfoResponse>
        <Layer name="{LAYER_QGIS_POPUP}" {title_attribute}>
            <Feature id="1">
                <Attribute name="OBJECTID" value="2662"/>
                <Attribute name="NAME_0" value="France"/>
                <Attribute name="VARNAME_1" value="Bretaa|Brittany"/>
                <Attribute name="Region" value="Bretagne"/>
                <Attribute name="Shape_Leng" value="18.39336934850"/>
                <Attribute name="Shape_Area" value="3.30646936365"/>
                <Attribute name="maptip" value="&lt;p>France&lt;/p>"/>
            </Feature>
        </Layer>
    </GetFeatureInfoResponse>
    '''
    diff = xml_diff.diff_texts(expected, rv.content)
    assert diff == [], diff


def test_single_get_feature_info_form_popup(client):
    """ Test the get feature info with a single feature with QGIS form. """
    qs = BASE_QUERY + SINGLE_FEATURE + QGIS_FORM
    rv = client.get(qs, PROJECT)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('text/xml') == 0

    # Let's check only the XML first
    root = ET.fromstring(rv.content.decode('utf-8'))
    map_tip = ''
    for layer in root:
        for feature in layer:
            item = root.find(".//Attribute[@name='maptip']")
            map_tip = item.attrib.get("value")
            feature.remove(item)

    xml_lines = ET.tostring(root, encoding='utf8', method='xml').decode("utf-8").split('\n')
    xml_string = '\n'.join(xml_lines[1:])

    title_attribute = f'title="{LAYER_QGIS_FORM}"' if Qgis.QGIS_VERSION_INT >= 33600 else ''

    expected = f'''
    <GetFeatureInfoResponse>
        <Layer name="{LAYER_QGIS_FORM}" {title_attribute}>
            <Feature id="1">
                <Attribute name="OBJECTID" value="2662"/>
                <Attribute name="NAME_0" value="France"/>
                <Attribute name="VARNAME_1" value="Bretaa|Brittany"/>
                <Attribute name="Region" value="Bretagne"/>
                <Attribute name="Shape_Leng" value="18.39336934850"/>
                <Attribute name="Shape_Area" value="3.30646936365"/>
            </Feature>
        </Layer>
    </GetFeatureInfoResponse>
    '''
    diff = xml_diff.diff_texts(expected, xml_string.strip())
    assert diff == [], diff

    # Let's check the maptip content
    assert '<div class="container popup_lizmap_dd form-horizontal" style="width:100%;">' in map_tip


def test_single_get_feature_info_form_shortname_popup(client):
    """ Test the get feature info with a single feature with QGIS form and a shortname. """
    qs = BASE_QUERY + SINGLE_FEATURE + LAYER_FORM + "WITH_MAPTIP=true&"

    rv = client.get(qs, PROJECT)
    root = _check_request(rv, content_type="text/xml")

    # Let's check only the XML first
    map_tip = ''
    for layer in root:
        for feature in layer:
            item = root.find(".//Attribute[@name='maptip']")
            map_tip = item.attrib.get("value")
            feature.remove(item)

    # Let's check the maptip content
    assert '<div class="container popup_lizmap_dd form-horizontal" style="width:100%;">' in map_tip


def test_single_get_feature_info_ascii(client):
    """ Test the Get Feature Info with different filters. """
    qs = {
        "SERVICE": "WMS",
        "REQUEST": "GetFeatureInfo",
        "VERSION": "1.3.0",
        "CRS": "EPSG:4326",
        "MAP": PROJECT,
        "LAYER": "accents",
        "INFO_FORMAT": "application/json",
        "QUERY_LAYERS": "accents",
        "LAYERS": "accents",
        "STYLE": "default",
        "BBOX": "47.854014654373024,-2.1121730324386476,48.63739203589741,0.06890198724626884",
        "WIDTH": "1832",
        "HEIGHT": "658",
        "FEATURE_COUNT": "10",
        "I": "379",
        "J": "431",
        "FI_POINT_TOLERANCE": "25",
        "FI_LINE_TOLERANCE": "10",
        "FI_POLYGON_TOLERANCE": "5",
        "FILTER": "accents:\"NAME_1\" = 'Bret\\'agne'",
    }

    rv = client.get(_build_query_string(qs, use_urllib=True), PROJECT)
    data = _check_request(rv)

    expected = {
        'features': [
            {
                'geometry': None,
                'id': 'accents.3',
                'properties': {
                    'NAME_1': "Bret'agne",
                },
                'type': 'Feature',
            },
        ],
        'type': 'FeatureCollection',
    }
    assert expected == data, data
