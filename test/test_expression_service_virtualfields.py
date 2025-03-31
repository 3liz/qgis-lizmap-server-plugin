import json

from urllib.parse import quote
from test.utils import PROJECT_FILE, BASE, _build_query_string, _check_request

__copyright__ = 'Copyright 2019, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

BASE = dict(BASE, **{
    "SERVICE": "EXPRESSION",
})


def test_layer_error(client):
    """  Test Expression VirtualFields request with Layer parameter error
    """
    # Make a request without layer
    qs = dict(BASE, **{
        "REQUEST": "GetFeatureWithFormScope",
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)

    # Make a request with an unknown layer
    qs = dict(BASE, **{
        "REQUEST": "GetFeatureWithFormScope",
        "LAYER": "UNKNOWN_LAYER",
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_virtuals_error(client):
    """  Test Expression VirtualFields request with Virtuals parameter error
    """
    # Make a request without filter
    qs = dict(BASE, **{
        "REQUEST": "Evaluate",
        "LAYER": "france_parts",
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    # Make a request
    qs = dict(BASE, **{
        "REQUEST": "VirtualFields",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"".format(
        quote('1', safe=''),
            quote('1 + 1', safe=''),
        ),
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0


def test_request(client):
    """  Test Expression VirtualFields request
    """
    # Make a request
    qs = dict(BASE, **{
        "REQUEST": "VirtualFields",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
        quote('1', safe=''),
            quote('1 + 1', safe=''),
        ),
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 4

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert 'Region' in b['features'][0]['properties']

    assert 'a' in b['features'][0]['properties']
    assert b['features'][0]['properties']['a'] == 1
    assert 'b' in b['features'][0]['properties']
    assert b['features'][0]['properties']['b'] == 2


def test_request_with_filter(client):
    """  Test Expression VirtualFields request with Filter parameter
    """
    # Make a request
    qs = dict(BASE, **{
        "REQUEST": "VirtualFields",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
        ),
        "FILTER": quote("NAME_1 = 'Bretagne'", safe=''),
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'
    assert 'Region' in b['features'][0]['properties']
    assert b['features'][0]['properties']['Region'] == 'Bretagne'

    assert 'a' in b['features'][0]['properties']
    assert b['features'][0]['properties']['a'] == 1
    assert 'b' in b['features'][0]['properties']
    assert b['features'][0]['properties']['b'] == 2


def test_request_with_filter_fields(client):
    """  Test Expression VirtualFields request with Filter and Fields parameters
    """
    # Make a request
    qs = dict(BASE, **{
        "REQUEST": "VirtualFields",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
        ),
        "FILTER": quote("NAME_1 = 'Bretagne'", safe=''),
        "FIELDS": "ISO,NAME_1",
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'
    assert 'Region' not in b['features'][0]['properties']

    assert 'a' in b['features'][0]['properties']
    assert b['features'][0]['properties']['a'] == 1
    assert 'b' in b['features'][0]['properties']
    assert b['features'][0]['properties']['b'] == 2


def test_request_with_filter_fields_geometry(client):
    """  Test Expression VirtualFields request with Filter, Fields and With_Geometry parameters
    """
    # Make a request
    qs = dict(BASE, **{
        "SERVICE": "EXPRESSION",
        "REQUEST": "VirtualFields",
        "MAP": "france_parts.qgs",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
        ),
        "FILTER": quote("NAME_1 = 'Bretagne'", safe=''),
        "FIELDS": "ISO,NAME_1",
        "WITH_GEOMETRY": True,
    })

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is not None

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'
    assert 'Region' not in b['features'][0]['properties']

    assert 'a' in b['features'][0]['properties']
    assert b['features'][0]['properties']['a'] == 1
    assert 'b' in b['features'][0]['properties']
    assert b['features'][0]['properties']['b'] == 2


def test_request_limit(client):
    """  Test Expression VirtualFields request
    """
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "VirtualFields",
        "MAP": "france_parts.qgs",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
        quote('1', safe=''), quote('1 + 1', safe='')),
        "LIMIT": "2",
    }

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 2

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert 'Region' in b['features'][0]['properties']

    assert 'a' in b['features'][0]['properties']
    assert b['features'][0]['properties']['a'] == 1
    assert 'b' in b['features'][0]['properties']
    assert b['features'][0]['properties']['b'] == 2


def test_request_order(client):
    """  Test Expression VirtualFields request
    """
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "VirtualFields",
        "MAP": "france_parts.qgs",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
        quote('1', safe=''), quote('1 + 1', safe='')),
        "SORTING_ORDER": "DESC",
        "SORTING_FIELD": "NAME_1",
    }

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 4

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert 'Region' in b['features'][0]['properties']

    assert 'a' in b['features'][0]['properties']
    assert b['features'][0]['properties']['a'] == 1
    assert 'b' in b['features'][0]['properties']
    assert b['features'][0]['properties']['b'] == 2

    assert b['features'][0]['id'] == 'france_parts.2'
    assert b['features'][3]['id'] == 'france_parts.0'


def test_request_safe_virtuals(client):
    """  Test Expression VirtualFields request with some un-checked expressions
    """
    forbidden = quote("env('CI')", safe='')
    allowed = quote("format_date(now(), 'yyyy')", safe='')

    qs = dict(BASE, **{
        "REQUEST": "VirtualFields",
        "LAYER": "france_parts",
        "VIRTUALS": "{{\"a\":\"{}\"}}".format(forbidden),
        "SAFE_VIRTUALS": "{{\"b\":\"{}\", \"c\":\"{}\"}}".format(
            forbidden,
            allowed,
        ),
    })
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)
    # On local, and GitHub Action, it's 'True', while on GitLab, it's 'true'.
    assert str(b['features'][0]['properties']['a']).lower() == 'true'
    assert b['features'][0]['properties']['b'] == 'not allowed'
    assert int(b['features'][0]['properties']['c']) >= 2000
