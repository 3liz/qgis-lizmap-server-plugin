from test.utils import PROJECT_FILE, _build_query_string, _check_request
from urllib.parse import quote

__copyright__ = 'Copyright 2019, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'


def test_layer_error_without_layer(client):
    """ Test Expression Evaluate request without layer parameter. """
    # Make a request without layer
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
    }
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'] == 'Invalid \'Evaluate\' REQUEST: LAYER parameter is mandatory'


def test_layer_error_with_layer_error(client):
    """ Test Expression Evaluate request with layer parameter error. """
    # Make a request with an unknown layer
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "UNKNOWN_LAYER",
    }
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'].startswith('Invalid LAYER parameter for \'Evaluate\'')

def test_expression_error(client):
    """ Test Expression Evaluate request with Expression parameter error. """
    # Make a request without expression
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
    }
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'] == 'Invalid \'Evaluate\' REQUEST: EXPRESSION or EXPRESSIONS parameter is mandatory'

    # Make a request with an invalid expression
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\"}}".format(
            quote('foobar()', safe=''),
        ),
    }
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'].startswith('Invalid EXPRESSIONS for \'Evaluate\'')

def test_features_error(client):
    """  Test Expression Evaluate request with Feature or Features parameter error
    """
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote('prop0', safe=''),
            quote('$x', safe=''),
        ),
        "FEATURE": "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}",
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)

    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'].startswith('Invalid \'Evaluate\' REQUEST: FEATURES')

    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote('prop0', safe=''),
            quote('$x', safe=''),
        ),
        "FEATURE": "{\"type\":\"feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}",
    }
    qs = _build_query_string(qs)
    # type feature and not Feature error
    rv = client.get(qs, PROJECT_FILE)

    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'].startswith('Invalid \'Evaluate\' REQUEST: FEATURES')

    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote('prop0', safe=''),
            quote('$x', safe=''),
        ),
        "FEATURES": ("["
            "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
            ", "
            "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [105.0, 0.5]}, \"properties\": {\"prop0\": \"value1\"}}"
            ),
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)

    b = _check_request(rv, http_code=400)

    assert 'status' in b
    assert b['status'] == 'fail'

    assert 'code' in b
    assert b['code'] == 'Bad request error'

    assert 'message' in b
    assert b['message'].startswith('Invalid \'Evaluate\' REQUEST: FEATURES')


def test_request_expression_without_features(client):
    """  Test Expression Evaluate request without Feature or Features parameter
    """
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSION": quote('1 + 1', safe=''),
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)

    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == 2

    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "[\"{}\", \"{}\"]".format(quote('1', safe=''), quote('1 + 1', safe='')),
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == 1
    assert '1' in b['results'][0]
    assert b['results'][0]['1'] == 2

    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
        quote('1', safe=''),
            quote('1 + 1', safe=''),
        ),
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == 1
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == 2

    # Request with lizmap headers and custom variables
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\"}}".format(
            quote('@lizmap_user', safe=''),
            quote('@lizmap_user_groups', safe=''),
        ),
    }
    qs = _build_query_string(qs)
    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    rv = client.get(qs, PROJECT_FILE, headers)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == 'Bretagne'
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == ['test1']


def test_layer_field_aggregates(client):
    """ Get the distinct values of the NAME_1 field """
    # Test expression
    expressions = {
        'distinct_values': """
            to_json(
                array_distinct(
                    aggregate(
                        layer:='france_parts',
                        aggregate:='array_agg',
                        expression:=\\"NAME_1\\",
                        order_by:=@element
                    )
                )
            )
        """,
        'min_area': """
            aggregate(
                layer:='france_parts',
                aggregate:='min',
                expression:=\\"Area_sqkm\\"
            )
        """,
    }
    query_string = '{'
    query_expressions = []
    for key, expression in expressions.items():
        query_expression = quote(expression.replace('\n', ' '), safe='')
        query_expressions.append(f'"{key}":"{query_expression}"')
    query_string += ', '.join(query_expressions)
    query_string += '}'
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": query_string,
    }
    qs = _build_query_string(qs)
    headers = {'X-Lizmap-User-Groups': 'test1', 'X-Lizmap-User': 'Bretagne'}
    request = client.get(qs, PROJECT_FILE, headers)

    data = _check_request(request)

    assert 'status' in data
    assert data['status'] == 'success'
    assert 'results' in data
    assert len(data['results']) == 1

    assert 'distinct_values' in data['results'][0]
    assert data['results'][0]['distinct_values'] == '["Basse-Normandie","Bretagne","Pays de la Loire","Centre"]'

    assert 'min_area' in data['results'][0]
    assert data['results'][0]['min_area'] == 17876.8


def test_request_with_features(client):
    """  Test Expression Evaluate request with Feature or Features parameter
    """
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
        quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote('prop0', safe=''),
            quote('$x', safe=''),
        ),
        "FEATURE": "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}",
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == 1
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == 2
    assert 'c' in b['results'][0]
    assert b['results'][0]['c'] == 'value0'
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == 102.0

    assert 'features' in b
    assert b['features'] == 1

    # Make a second request
    features = "["
    features += "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}"
    features += ", "
    features += "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [105.0, 0.5]}, \"properties\": {\"prop0\": \"value1\"}}"
    features += "]"

    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
        quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote('prop0', safe=''),
            quote('$x', safe=''),
        ),
        "FEATURES": features,
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 2
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == 1
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == 2
    assert 'c' in b['results'][0]
    assert b['results'][0]['c'] == 'value0'
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == 102.0

    assert 'c' in b['results'][1]
    assert b['results'][1]['c'] == 'value1'
    assert 'd' in b['results'][1]
    assert b['results'][1]['d'] == 105.0

    assert 'features' in b
    assert b['features'] == 2


def test_request_with_form_scope(client):
    """  Test Expression Evaluate request without Feature or Features and Form_Scope parameters
    """
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote("current_value('prop0')", safe=''),
            quote('$x', safe=''),
        ),
        "FEATURE": "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}",
        "FORM_SCOPE": True,
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'a' in b['results'][0]
    assert b['results'][0]['a'] == 1
    assert 'b' in b['results'][0]
    assert b['results'][0]['b'] == 2
    assert 'c' in b['results'][0]
    assert b['results'][0]['c'] == 'value0'
    assert 'd' in b['results'][0]
    assert b['results'][0]['d'] == 102.0

    assert 'features' in b
    assert b['features'] == 1

    # Make a request without form scope but with current_value function
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"a\":\"{}\", \"b\":\"{}\", \"c\":\"{}\", \"d\":\"{}\"}}".format(
            quote('1', safe=''),
            quote('1 + 1', safe=''),
            quote("current_value('prop0')", safe=''),
            quote('$x', safe=''),
        ),
        "FEATURE": "{\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"value0\"}}",
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1

    assert 'c' in b['results'][0]
    assert b['results'][0]['c'] is None

    assert 'features' in b
    assert b['features'] == 1

    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": PROJECT_FILE,
        "LAYER": "france_parts",
        "EXPRESSIONS": "{{\"jforms_view_edition-tab2\":\"{}\"}}".format(
            quote(' to_string(\\"has_photo\\") = \'true\' OR \\"has_photo\\" = \'t\'', safe=''),
        ),
        "FEATURE": "{\"type\":\"Feature\", \"geometry\": null, \"properties\": {\"has_photo\": \"f\"}}",
        "FORM_SCOPE": True,
    }
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert 'status' in b
    assert b['status'] == 'success'

    assert 'results' in b
    assert len(b['results']) == 1
    assert 'jforms_view_edition-tab2' in b['results'][0]
    assert not b['results'][0]['jforms_view_edition-tab2']

    assert 'features' in b
    assert b['features'] == 1


def test_lizmap_python_expressions(client):
    """
    Test the expressions provided by the plugin
    """
    # Use the legend.qgs project
    project_file = 'lizmap_expressions.qgs'

    # Test for simple unique symbol
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": 'unique_symbol',
        "EXPRESSION": quote(
            "layer_renderer_used_attributes('unique_symbol')",
            safe='',
        ),
    }
    qs_built = _build_query_string(qs)
    rv = client.get(qs_built, project_file)
    b = _check_request(rv)
    assert 'status' in b
    assert b['status'] == 'success'
    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == []

    # Test for simple unique symbol with expression based color
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": 'unique_symbol_expression_based_color',
        "EXPRESSION": quote(
            "layer_renderer_used_attributes('unique_symbol_expression_based_color')",
            safe='',
        ),
    }
    qs_built = _build_query_string(qs)
    rv = client.get(qs_built, project_file)
    b = _check_request(rv)
    assert 'status' in b
    assert b['status'] == 'success'
    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == ['NAME_1']

    # Test for categorized
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": 'categorized',
        "EXPRESSION": quote(
            "layer_renderer_used_attributes('categorized')",
            safe='',
        ),
    }
    qs_built = _build_query_string(qs)
    rv = client.get(qs_built, project_file)
    b = _check_request(rv)
    assert 'status' in b
    assert b['status'] == 'success'
    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == ['NAME_1']

    # Test for rule based renderer with only one field used
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": 'rule_based',
        "EXPRESSION": quote(
            "layer_renderer_used_attributes('rule_based')",
            safe='',
        ),
    }
    qs_built = _build_query_string(qs)
    rv = client.get(qs_built, project_file)
    b = _check_request(rv)
    assert 'status' in b
    assert b['status'] == 'success'
    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'] == ['NAME_1']

    # Test for rule based renderer with multiple field used
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": 'rule_based_with_multiple_fields',
        "EXPRESSION": quote(
            "layer_renderer_used_attributes('rule_based_with_multiple_fields')",
            safe='',
        ),
    }
    qs_built = _build_query_string(qs)
    rv = client.get(qs_built, project_file)
    b = _check_request(rv)
    assert 'status' in b
    assert b['status'] == 'success'
    assert 'results' in b
    assert len(b['results']) == 1
    assert '0' in b['results'][0]
    assert b['results'][0]['0'].sort() == ['Region', 'NAME_1', 'TYPE_1'].sort()
