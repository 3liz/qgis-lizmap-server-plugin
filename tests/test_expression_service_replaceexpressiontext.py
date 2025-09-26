import json

from .utils import PROJECT_FILE, _build_query_string, _check_request
from urllib.parse import quote

BASE_QUERY = {
    "SERVICE": "EXPRESSION",
    "REQUEST": "replaceExpressionText",
    "MAP": PROJECT_FILE,
}


def test_layer_error_no_layer(client):
    """Test Expression replaceExpressionText request with no layer."""
    rv = client.get(_build_query_string(dict(BASE_QUERY)), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_layer_error_unknown_layer(client):
    """Test Expression replaceExpressionText request with unknown layer."""
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "UNKNOWN_LAYER"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_string_error(client):
    """Test Expression replaceExpressionText request without expression."""
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_features_error(client):
    """Test Expression replaceExpressionText request with Feature or Features parameter error"""
    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURE"] = (
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}'
    )
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, http_code=400)

    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURE"] = (
        '{"type":"feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
    )
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, http_code=400)

    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURES"] = (
        "["
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
        ", "
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [105.0, 0.5]}, "properties": {"prop0": "value1"}}'
    )
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_request_replace_without_features(client):
    """Test Expression replaceExpressionText request without Feature or Features parameter"""
    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRING"] = quote("[% 1 + 1 %]", safe="")
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 1
    assert "0" in b["results"][0]
    assert b["results"][0]["0"] == "2"

    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '["{}", "{}"]'.format(quote("[% 1 %]", safe=""), quote("[% 1 + 1 %]", safe=""))
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    b = json.loads(rv.content.decode("utf-8"))

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 1
    assert "0" in b["results"][0]
    assert b["results"][0]["0"] == "1"
    assert "1" in b["results"][0]
    assert b["results"][0]["1"] == "2"

    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}"}}'.format(quote("[% 1 %]", safe=""), quote("[% 1 + 1 %]", safe=""))
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    b = json.loads(rv.content.decode("utf-8"))

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 1
    assert "a" in b["results"][0]
    assert b["results"][0]["a"] == "1"
    assert "b" in b["results"][0]
    assert b["results"][0]["b"] == "2"


def test_request_with_features(client):
    """Test Expression replaceExpressionText request with Feature or Features parameter"""
    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURE"] = (
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
    )
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 1
    assert "a" in b["results"][0]
    assert b["results"][0]["a"] == "1"
    assert "b" in b["results"][0]
    assert b["results"][0]["b"] == "2"
    assert b["results"][0]["c"] == "value0"
    assert "d" in b["results"][0]
    assert b["results"][0]["d"] == "102"

    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURES"] = (
        "["
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
        ", "
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [105.0, 0.5]}, "properties": {"prop0": "value1"}}'
        "]"
    )
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 2
    assert "a" in b["results"][0]
    assert b["results"][0]["a"] == "1"
    assert "b" in b["results"][0]
    assert b["results"][0]["b"] == "2"
    assert b["results"][0]["c"] == "value0"
    assert "d" in b["results"][0]
    assert b["results"][0]["d"] == "102"

    assert "c" in b["results"][1]
    assert b["results"][1]["c"] == "value1"
    assert "d" in b["results"][1]
    assert b["results"][1]["d"] == "105"


def test_request_with_features_all(client):
    """Test Expression replaceExpressionText request with Feature or Features parameter"""
    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% NAME_1 %]", safe=""),
        quote("[% round($area) %]", safe=""),
    )
    qs["FEATURES"] = "ALL"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 4

    assert "a" in b["results"][0]
    assert b["results"][0]["a"] == "1"
    assert "b" in b["results"][0]
    assert b["results"][0]["b"] == "2"
    assert b["results"][0]["c"] == "Basse-Normandie"
    assert "d" in b["results"][0]
    assert b["results"][0]["d"] == "27186051602"


def test_request_with_form_scope(client):
    """Test Expression replaceExpressionText request without Feature or Features and Form_Scope parameters"""
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% current_value('prop0') %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURE"] = (
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
    )
    qs["FORM_SCOPE"] = "true"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 1
    assert "a" in b["results"][0]
    assert b["results"][0]["a"] == "1"
    assert "b" in b["results"][0]
    assert b["results"][0]["b"] == "2"
    assert b["results"][0]["c"] == "value0"
    assert "d" in b["results"][0]
    assert b["results"][0]["d"] == "102"

    # Make a request without form scope but with current_value function
    # One template has multiple expressions
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% current_value('prop0') %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURE"] = (
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
    )
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "status" in b
    assert b["status"] == "success"

    assert "results" in b
    assert len(b["results"]) == 1
    assert "a" in b["results"][0]
    assert b["results"][0]["a"] == "1"
    assert "b" in b["results"][0]
    assert b["results"][0]["b"] == "2"
    assert b["results"][0]["c"] == ""
    assert "d" in b["results"][0]
    assert b["results"][0]["d"] == "102"


def test_request_with_features_geojson(client):
    """Test Expression replaceExpressionText request with Feature or Features parameter"""
    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURE"] = (
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
    )
    qs["FORMAT"] = "GeoJSON"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    assert "id" in b["features"][0]
    assert b["features"][0]["id"] == 0
    assert "properties" in b["features"][0]
    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == "1"
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == "2"
    assert b["features"][0]["properties"]["c"] == "value0"
    assert "d" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["d"] == "102"

    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% prop0 %]", safe=""),
        quote("[% $x %]", safe=""),
    )
    qs["FEATURES"] = (
        "["
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [102.0, 0.5]}, "properties": {"prop0": "value0"}}'
        ", "
        '{"type":"Feature", "geometry": {"type": "Point", "coordinates": [105.0, 0.5]}, "properties": {"prop0": "value1"}}'
        "]"
    )
    qs["FORMAT"] = "GeoJSON"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 2

    assert "id" in b["features"][0]
    assert b["features"][0]["id"] == 0
    assert "properties" in b["features"][0]
    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == "1"
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == "2"
    assert b["features"][0]["properties"]["c"] == "value0"
    assert "d" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["d"] == "102"

    assert "id" in b["features"][1]
    assert b["features"][1]["id"] == 1
    assert "c" in b["features"][1]["properties"]
    assert b["features"][1]["properties"]["c"] == "value1"
    assert "d" in b["features"][1]["properties"]
    assert b["features"][1]["properties"]["d"] == "105"


def test_request_with_features_all_geojson(client):
    """Test Expression replaceExpressionText request with FEATURES=ALL and FORMAT=GeoJSON."""
    # Make a request
    qs = dict(BASE_QUERY)
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% NAME_1 %]", safe=""),
        quote("[% round($area) %]", safe=""),
    )
    qs["FEATURES"] = "ALL"
    qs["FORMAT"] = "GeoJSON"
    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    assert "id" in b["features"][0]
    assert b["features"][0]["id"] == 0
    assert "properties" in b["features"][0]
    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == "1"
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == "2"
    assert b["features"][0]["properties"]["c"] == "Basse-Normandie"
    assert "d" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["d"] == "27186051602"


def test_request_with_features_all_access_control(client):
    """Test request with FEATURES=ALL, FORMAT=GeoJSON and access control."""
    # Project with config with group filter
    project_file = "france_parts_liz_filter_group.qgs"

    # Build query string
    qs = dict(BASE_QUERY)
    qs["MAP"] = project_file
    qs["LAYER"] = "france_parts"
    qs["STRINGS"] = '{{"a":"{}", "b":"{}", "c":"{}", "d":"{}"}}'.format(
        quote("[% 1 %]", safe=""),
        quote("[% 1 + 1 %]", safe=""),
        quote("[% NAME_1 %]", safe=""),
        quote("[% round($area) %]", safe=""),
    )
    qs["FEATURES"] = "ALL"
    qs["FORMAT"] = "GeoJSON"

    # make request without headers
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    # make request with headers - 1 group = 1 feature
    headers = {"X-Lizmap-User-Groups": "Bretagne"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    # make request with headers - 3 groups = 2 features
    headers = {"X-Lizmap-User-Groups": "Bretagne, Centre, test1"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 2

    # make request with headers - 1 group = 0 feature
    headers = {"X-Lizmap-User-Groups": "test1"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 0

    # make request without headers to check filter reset
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    # Project with config with login filter
    project_file = "france_parts_liz_filter_login.qgs"
    qs["MAP"] = project_file

    # make request without headers
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    # make request with headers - 1 login = 1 feature
    headers = {"X-Lizmap-User-Groups": "test1", "X-Lizmap-User": "Bretagne"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    # make request with headers - 1 login = 0 feature
    headers = {"X-Lizmap-User-Groups": "Bretagne, Centre, test1", "X-Lizmap-User": "test"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 0

    # make request without headers to check filter reset
    rv = client.get(_build_query_string(qs), project_file)
    b = _check_request(rv, content_type="application/vnd.geo+json")

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4
