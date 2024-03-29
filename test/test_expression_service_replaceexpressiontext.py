import json

from test.utils import _build_query_string, _check_request
from urllib.parse import quote

__copyright__ = 'Copyright 2013, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

PROJECT_FILE = "france_parts.qgs"
BASE_QUERY = {
    'SERVICE': 'EXPRESSION',
    'REQUEST': 'replaceExpressionText',
    'MAP': PROJECT_FILE,
}


def test_layer_error_no_layer(client):
    """ Test Expression replaceExpressionText request with no layer. """
    rv = client.get(_build_query_string(dict(BASE_QUERY)), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_layer_error_unknown_layer(client):
    """ Test Expression replaceExpressionText request with unknown layer. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'UNKNOWN_LAYER'
    rv = client.get(_build_query_string(dict(BASE_QUERY)), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_string_error(client):
    """ Test Expression replaceExpressionText request without expression. """
    qs = dict(BASE_QUERY)
    qs['LAYER'] = 'france_parts'
    rv = client.get(_build_query_string(dict(BASE_QUERY)), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_features_error(client):
    """  Test Expression replaceExpressionText request with Feature or Features parameter error
    """
    # Make a request
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''), quote('[% prop0 %]', safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURE={\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    # Make a request
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''), quote('[% prop0 %]', safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURE={\"type\":\"feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    # type feature and not Feature error
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    # Make a request
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''), quote('[% prop0 %]', safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURES=["
    qs += "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    qs += ", "
    qs += "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [105.0, 0.5]}, \"properties\": {\"prop0\": \"value1\"}}"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0


def test_request_without_features(client):
    """  Test Expression replaceExpressionText request without Feature or Features parameter
    """
    # Make a request
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts&STRING=%s" % (
        quote('[% 1 + 1 %]', safe=''))
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == '2'

    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts&STRINGS=[\"%s\", \"%s\"]" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''))
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == '1'
    assert '1' in b['results'][0]
    assert b['results'][0]['1'] == '2'

    qs = "?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP=%s&LAYER=france_parts&STRINGS={\"a\":\"%s\", \"b\":\"%s\"}" % (
        PROJECT_FILE, quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''))
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == '1'
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == '2'


def test_request_with_features(client):
    """  Test Expression replaceExpressionText request with Feature or Features parameter
    """
    # Make a request
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''), quote('[% prop0 %]', safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURE={\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == '1'
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == '2'
    assert b['results'][0]['c'] == 'value0'
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == '102'

    # Make a request
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''), quote('[% prop0 %]', safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURES=["
    qs += "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    qs += ", "
    qs += "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [105.0, 0.5]}, \"properties\": {\"prop0\": \"value1\"}}"
    qs += "]"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 2
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == '1'
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == '2'
    assert b['results'][0]['c'] == 'value0'
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == '102'

    assert 'c' in b['results'][1]
    assert b['results'][1]['c'] == 'value1'
    assert 'd' in b['results'][1]
    assert b['results'][1]['d'] == '105'


def test_request_with_form_scope(client):
    """  Test Expression replaceExpressionText request without Feature or Features and Form_Scope parameters
    """
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %]', safe=''), quote("[% current_value('prop0') %]", safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURE={\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    qs += "&FORM_SCOPE=true"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == '1'
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == '2'
    assert b['results'][0]['c'] == 'value0'
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == '102'

    # Make a request without form scope but with current_value function
    # One template has multiple expressions
    qs = f"?SERVICE=EXPRESSION&REQUEST=replaceExpressionText&MAP={PROJECT_FILE}&LAYER=france_parts"
    qs += "&STRINGS={\"a\":\"%s\", \"b\":\"%s\", \"c\":\"%s\", \"d\":\"%s\"}" % (
        quote('[% 1 %]', safe=''), quote('[% 1 + 1 %] [% 2 + 2 %]', safe=''), quote("[% current_value('prop0') %]", safe=''),
        quote('[% $x %]', safe=''))
    qs += "&FEATURE={\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200

    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    b = json.loads(rv.content.decode('utf-8'))

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == '1'
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == '2 4'
    assert b['results'][0]['c'] == ''
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == '102'
