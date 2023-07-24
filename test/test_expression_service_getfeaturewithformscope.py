import json

from test.utils import _build_query_string, _check_request
from urllib.parse import quote

__copyright__ = 'Copyright 2023, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

PROJECT_FILE = 'france_parts.qgs'


def test_layer_error_without_layer(client):
    """ Test Expression GetFeatureFormScope without layer. """
    qs = "?SERVICE=EXPRESSION&REQUEST=GetFeatureWithFormScope&MAP=france_parts.qgs"
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_layer_error_with_unknown_layer(client):
    """ Test Expression GetFeatureFormScope with unknown layer. """
    qs = "?SERVICE=EXPRESSION&REQUEST=GetFeatureWithFormScope&MAP=france_parts.qgs&LAYER=UNKNOWN_LAYER"
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_filter_error_without_filter(client):
    """  Test Expression GetFeatureFormScope request with Filter parameter error
    """
    qs = "?SERVICE=EXPRESSION&REQUEST=Evaluate&MAP=france_parts.qgs&LAYER=france_parts"
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0


def test_comment_space_carriage_return(client):
    """ Test an GetFeatureWithFormScope with some human formatting. """
    project_file = "test_filter_layer_data_by_polygon_for_groups.qgs"
    # An empty line, a QGIS comment, some indentation
    expression = """
\"name\" = 'Mairie de '||

attributes(
    -- with QGIS expression comment
    get_feature('polygons', 'id', current_value('polygon_id'))
)['name']"""

    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': project_file,
        'LAYER': 'townhalls_EPSG2154',
        'FILTER': quote(expression, safe=''),
        'FORM_FEATURE': json.dumps({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [102.0, 0.5]
            },
            "properties": {"polygon_id": 4}})
    }
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv)

    assert b['type'] == 'FeatureCollection'
    assert len(b['features']) == 1
    assert b['features'][0]['type'] == 'Feature'
    assert b['features'][0]['properties']['name'] == 'Mairie de Lattes'


def test_formfeature_error(client):
    """  Test Expression GetFeatureFormScope request with Form_Feature parameter error
    """
    projectfile = "france_parts.qgs"

    # Make a request without form_feature
    qs = "?SERVICE=EXPRESSION&REQUEST=Evaluate&MAP=france_parts.qgs&LAYER=france_parts"
    qs += "&FILTER=%s" % (
        quote("NAME_1 = current_value('prop0')", safe=''))
    rv = client.get(qs, projectfile)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    # Make a request without well-formed form_feature
    qs = "?SERVICE=EXPRESSION&REQUEST=GetFeatureWithFormScope&MAP=france_parts.qgs&LAYER=france_parts"
    qs += "&FILTER=%s" % (
        quote("NAME_1 = current_value('prop0')", safe=''))
    qs += "&FORM_FEATURE={\"type\":\"Feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"Bretagne\"}"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0

    # Make a request without well-formed form_feature
    qs = "?SERVICE=EXPRESSION&REQUEST=GetFeatureWithFormScope&MAP=france_parts.qgs&LAYER=france_parts"
    qs += "&FILTER=%s" % (
        quote("NAME_1 = current_value('prop0')", safe=''))
    qs += "&FORM_FEATURE={\"type\":\"feature\", \"geometry\": {\"type\": \"Point\", \"coordinates\": [102.0, 0.5]}, \"properties\": {\"prop0\": \"Bretagne\"}}"
    # type feature and not Feature error
    rv = client.get(qs, projectfile)
    assert rv.status_code == 400
    assert rv.headers.get('Content-Type', '').find('application/json') == 0


def test_request_get_feature_form_scope_current_value(client):
    """ Test Expression GetFeatureFormScope request with current_value. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "NAME_1 = current_value('prop0')",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop0": "Bretagne"}
            }
        )}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'id' in b['features'][0]
    assert b['features'][0]['id'] == 'france_parts.1'  # should be 4


def test_request_get_feature_form_scope_with_geom(client):
    """ Test Expression GetFeatureFormScope request with a geometry. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "NAME_1 = current_value('prop0')",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop0": "Bretagne"}
            }
        ),
        'WITH_GEOMETRY': 'True'}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is not None
    assert 'type' in b['features'][0]['geometry']
    assert b['features'][0]['geometry']['type'] == 'MultiPolygon'


def test_request_get_feature_form_scope_with_fields(client):
    """ Test Expression GetFeatureFormScope request with some fields. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "NAME_1 = current_value('prop0')",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop0": "Bretagne"}
            }
        ),
        'FIELDS': 'ISO,NAME_1'}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'
    assert 'NAME_0' not in b['features'][0]['properties']

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None


def test_request_get_feature_form_scope_with_spatial_filter(client):
    """ Test Expression GetFeatureFormScope request with a spatial filter. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "intersects($geometry, @current_geometry)",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [-3.0, 48.0]},
                "properties": {"prop0": "Bretagne"}
            }
        )}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is not None
    assert 'type' in b['features'][0]['geometry']
    assert b['features'][0]['geometry']['type'] == 'MultiPolygon'


def test_request_get_feature_without_named_parameters(client):
    """ Test request GetFeatureWithFormScope, with default order in expressions. """
    project_file = "test_filter_layer_data_by_polygon_for_groups.qgs"
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': project_file,
        'LAYER': 'townhalls_EPSG2154',
        'FILTER': quote(
            "\"name\" = 'Mairie de '|| attributes(get_feature('polygons', 'id', current_value('polygon_id')))['name']",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"polygon_id": 4}
            }
        )}
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv)
    assert b['type'] == 'FeatureCollection'
    assert len(b['features']) == 1
    assert b['features'][0]['type'] == 'Feature'
    assert b['features'][0]['properties']['name'] == 'Mairie de Lattes'


def test_request_get_feature_with_named_parameters(client):
    """ Test request GetFeatureWithFormScope, with default order in expressions. """
    project_file = "test_filter_layer_data_by_polygon_for_groups.qgs"
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': project_file,
        'LAYER': 'townhalls_EPSG2154',
        'FILTER': quote(
            "\"name\" = 'Mairie de '|| attributes(get_feature"
            "(layer:='polygons', attribute:='id', value:=current_value('polygon_id')))['name']",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"polygon_id": 4}
            }
        )}
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv)
    assert b['type'] == 'FeatureCollection'
    assert len(b['features']) == 1
    assert b['features'][0]['type'] == 'Feature'
    assert b['features'][0]['properties']['name'] == 'Mairie de Lattes'


def test_request_given_parent_feature(client):
    """ Test Expression GetFeatureFormScope request with a given parent feature. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "NAME_1 = current_parent_value('prop0')",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [-3.0, 48.0]},
                "properties": {"prop1": "Rennes"}
            }
        ),
        'PARENT_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop0": "Bretagne"}
            }
        )}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'id' in b['features'][0]
    assert b['features'][0]['id'] == 'france_parts.1'  # should be 4


def test_request_current_parent_feature(client):
    """ Test Expression GetFeatureFormScope request with the current parent feature. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "NAME_1 = attribute(@current_parent_feature, 'prop0')",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [-3.0, 48.0]},
                "properties": {"prop1": "Rennes"}
            }
        ),
        'PARENT_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop0": "Bretagne"}
            }
        )}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is None

    assert 'id' in b['features'][0]
    assert b['features'][0]['id'] == 'france_parts.1'  # should be 4


def test_request_current_parent_geometry(client):
    """ Test Expression GetFeatureFormScope request with the current parent geometry. """
    qs = {
        'SERVICE': 'EXPRESSION',
        'REQUEST': 'GetFeatureWithFormScope',
        'MAP': PROJECT_FILE,
        'LAYER': 'france_parts',
        'FILTER': quote(
            "intersects($geometry, @current_parent_geometry)",
            safe=''),
        'FORM_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop1": "Rennes"}
            }
        ),
        'PARENT_FEATURE': json.dumps(
            {
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [-3.0, 48.0]},
                "properties": {"prop0": "Bretagne"}
            }
        )}
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert 'type' in b
    assert b['type'] == 'FeatureCollection'

    assert 'features' in b
    assert len(b['features']) == 1

    assert 'type' in b['features'][0]
    assert b['features'][0]['type'] == 'Feature'

    assert 'properties' in b['features'][0]
    assert 'NAME_1' in b['features'][0]['properties']
    assert b['features'][0]['properties']['NAME_1'] == 'Bretagne'

    assert 'geometry' in b['features'][0]
    assert b['features'][0]['geometry'] is not None
    assert 'type' in b['features'][0]['geometry']
    assert b['features'][0]['geometry']['type'] == 'MultiPolygon'
