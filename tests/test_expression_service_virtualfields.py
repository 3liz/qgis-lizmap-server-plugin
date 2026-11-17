import json

from urllib.parse import quote
from .utils import (
    PROJECT_FILE,
    Client,
    BASE,
    _build_query_string,
    _check_request,
)

BASE = dict(
    BASE,
    **{
        "SERVICE": "EXPRESSION",
    },
)


def test_layer_error(client):
    """Test Expression VirtualFields request with Layer parameter error"""
    # Make a request without layer
    qs = dict(
        BASE,
        **{
            "REQUEST": "GetFeatureWithFormScope",
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)

    # Make a request with an unknown layer
    qs = dict(
        BASE,
        **{
            "REQUEST": "GetFeatureWithFormScope",
            "LAYER": "UNKNOWN_LAYER",
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_virtuals_error(client):
    """Test Expression VirtualFields request with Virtuals parameter error"""
    # Make a request without filter
    qs = dict(
        BASE,
        **{
            "REQUEST": "Evaluate",
            "LAYER": "france_parts",
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    # Make a request
    qs = dict(
        BASE,
        **{
            "REQUEST": "VirtualFields",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}", "b":"{}"'.format(
                quote("1", safe=""),
                quote("1 + 1", safe=""),
            ),
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 400
    assert rv.headers.get("Content-Type", "").find("application/json") == 0


def test_request(client):
    """Test Expression VirtualFields request"""
    # Make a request
    qs = dict(
        BASE,
        **{
            "REQUEST": "VirtualFields",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(
                quote("1", safe=""),
                quote("1 + 1", safe=""),
            ),
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    assert "type" in b["features"][0]
    assert b["features"][0]["type"] == "Feature"

    assert "geometry" in b["features"][0]
    assert b["features"][0]["geometry"] is None

    assert "properties" in b["features"][0]
    assert "NAME_1" in b["features"][0]["properties"]
    assert "Region" in b["features"][0]["properties"]

    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == 1
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == 2


def test_request_with_filter(client):
    """Test Expression VirtualFields request with Filter parameter"""
    # Make a request
    qs = dict(
        BASE,
        **{
            "REQUEST": "VirtualFields",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(
                quote("1", safe=""),
                quote("1 + 1", safe=""),
            ),
            "FILTER": quote("NAME_1 = 'Bretagne'", safe=""),
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    assert "type" in b["features"][0]
    assert b["features"][0]["type"] == "Feature"

    assert "geometry" in b["features"][0]
    assert b["features"][0]["geometry"] is None

    assert "properties" in b["features"][0]
    assert "NAME_1" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["NAME_1"] == "Bretagne"
    assert "Region" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["Region"] == "Bretagne"

    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == 1
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == 2


def test_request_with_filter_fields(client):
    """Test Expression VirtualFields request with Filter and Fields parameters"""
    # Make a request
    qs = dict(
        BASE,
        **{
            "REQUEST": "VirtualFields",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(
                quote("1", safe=""),
                quote("1 + 1", safe=""),
            ),
            "FILTER": quote("NAME_1 = 'Bretagne'", safe=""),
            "FIELDS": "ISO,NAME_1",
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    b = _check_request(rv)

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    assert "type" in b["features"][0]
    assert b["features"][0]["type"] == "Feature"

    assert "geometry" in b["features"][0]
    assert b["features"][0]["geometry"] is None

    assert "properties" in b["features"][0]
    assert "NAME_1" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["NAME_1"] == "Bretagne"
    assert "Region" not in b["features"][0]["properties"]

    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == 1
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == 2


def test_request_with_filter_fields_geometry(client):
    """Test Expression VirtualFields request with Filter, Fields and With_Geometry parameters"""
    # Make a request
    qs = dict(
        BASE,
        **{
            "SERVICE": "EXPRESSION",
            "REQUEST": "VirtualFields",
            "MAP": "france_parts.qgs",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(
                quote("1", safe=""),
                quote("1 + 1", safe=""),
            ),
            "FILTER": quote("NAME_1 = 'Bretagne'", safe=""),
            "FIELDS": "ISO,NAME_1",
            "WITH_GEOMETRY": True,
        },
    )

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    assert "type" in b["features"][0]
    assert b["features"][0]["type"] == "Feature"

    assert "geometry" in b["features"][0]
    assert b["features"][0]["geometry"] is not None

    assert "properties" in b["features"][0]
    assert "NAME_1" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["NAME_1"] == "Bretagne"
    assert "Region" not in b["features"][0]["properties"]

    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == 1
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == 2


def test_request_limit(client):
    """Test Expression VirtualFields request"""
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "VirtualFields",
        "MAP": "france_parts.qgs",
        "LAYER": "france_parts",
        "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(quote("1", safe=""), quote("1 + 1", safe="")),
        "LIMIT": "2",
    }

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 2

    assert "type" in b["features"][0]
    assert b["features"][0]["type"] == "Feature"

    assert "geometry" in b["features"][0]
    assert b["features"][0]["geometry"] is None

    assert "properties" in b["features"][0]
    assert "NAME_1" in b["features"][0]["properties"]
    assert "Region" in b["features"][0]["properties"]

    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == 1
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == 2


def test_request_order(client):
    """Test Expression VirtualFields request"""
    # Make a request
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "VirtualFields",
        "MAP": "france_parts.qgs",
        "LAYER": "france_parts",
        "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(quote("1", safe=""), quote("1 + 1", safe="")),
        "SORTING_ORDER": "DESC",
        "SORTING_FIELD": "NAME_1",
    }

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    assert "type" in b["features"][0]
    assert b["features"][0]["type"] == "Feature"

    assert "geometry" in b["features"][0]
    assert b["features"][0]["geometry"] is None

    assert "properties" in b["features"][0]
    assert "NAME_1" in b["features"][0]["properties"]
    assert "Region" in b["features"][0]["properties"]

    assert "a" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["a"] == 1
    assert "b" in b["features"][0]["properties"]
    assert b["features"][0]["properties"]["b"] == 2

    assert b["features"][0]["id"] == "france_parts.2"
    assert b["features"][3]["id"] == "france_parts.0"


def test_request_safe_virtuals(client):
    """Test Expression VirtualFields request with some un-checked expressions"""
    forbidden = quote("env('CI')", safe="")
    allowed = quote("format_date(now(), 'yyyy')", safe="")

    qs = dict(
        BASE,
        **{
            "REQUEST": "VirtualFields",
            "LAYER": "france_parts",
            "VIRTUALS": f'{{"a":"{forbidden}"}}',
            "SAFE_VIRTUALS": f'{{"b":"{forbidden}", "c":"{allowed}"}}',
        },
    )
    qs = _build_query_string(qs)
    rv = client.get(qs, PROJECT_FILE)
    _check_request(rv, http_code=400)


def test_request_access_control(client):
    """Test Expression VirtualFields request with access control"""
    # Project with config with group filter
    project_file = "france_parts_liz_filter_group.qgs"

    qs = dict(
        BASE,
        **{
            "REQUEST": "VirtualFields",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}", "b":"{}"}}'.format(
                quote("1", safe=""),
                quote("1 + 1", safe=""),
            ),
        },
    )
    qs["MAP"] = project_file

    # make request without headers
    rv = client.get(_build_query_string(qs), project_file)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    # make request with headers - 1 group = 1 feature
    headers = {"X-Lizmap-User-Groups": "Bretagne"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    # make request with headers - 3 groups = 2 features
    headers = {"X-Lizmap-User-Groups": "Bretagne, Centre, test1"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 2

    # make request with headers - 1 group = 0 feature
    headers = {"X-Lizmap-User-Groups": "test1"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 0

    # make request without headers to check filter reset
    rv = client.get(_build_query_string(qs), project_file)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    # Project with config with login filter
    project_file = "france_parts_liz_filter_login.qgs"
    qs["MAP"] = project_file

    # make request without headers
    rv = client.get(_build_query_string(qs), project_file)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4

    # make request with headers - 1 login = 1 feature
    headers = {"X-Lizmap-User-Groups": "test1", "X-Lizmap-User": "Bretagne"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 1

    # make request with headers - 1 login = 0 feature
    headers = {"X-Lizmap-User-Groups": "Bretagne, Centre, test1", "X-Lizmap-User": "test"}
    rv = client.get(_build_query_string(qs), project_file, headers)
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 0

    # make request without headers to check filter reset
    rv = client.get(_build_query_string(qs), project_file)
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    b = json.loads(rv.content.decode("utf-8"))

    assert "type" in b
    assert b["type"] == "FeatureCollection"

    assert "features" in b
    assert len(b["features"]) == 4


def test_request_filter_forbidden_function(client):
    """A forbidden function in the FILTER is rejected, as the filter can be sent by the client."""
    for expression in ("env('HOME') IS NOT NULL", "file_exists('/etc/passwd')", "NAME_1 = eval('1')"):
        qs = {
            "SERVICE": "EXPRESSION",
            "REQUEST": "VirtualFields",
            "MAP": "france_parts.qgs",
            "LAYER": "france_parts",
            "VIRTUALS": '{{"a":"{}"}}'.format(quote("1", safe="")),
            "FILTER": quote(expression, safe=""),
        }

        rv = client.get(_build_query_string(qs), PROJECT_FILE)
        b = _check_request(rv, http_code=400)
        assert "is not allowed" in b["message"], expression


def _sorted_ids(client: Client, sorting_field: str) -> list:
    """Request the features sorted by descending order of the given field, and return their ids.

    :param client: The QGIS Server test client.
    :param sorting_field: The SORTING_FIELD parameter.
    :returns: The ids of the features, in the order of the response.
    """
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "VirtualFields",
        "MAP": "france_parts.qgs",
        "LAYER": "france_parts",
        "VIRTUALS": '{{"a":"{}"}}'.format(quote("1", safe="")),
        "SORTING_ORDER": "DESC",
        "SORTING_FIELD": quote(sorting_field, safe=""),
    }

    rv = client.get(_build_query_string(qs), PROJECT_FILE)
    b = _check_request(rv)
    return [feature["id"] for feature in b["features"]]


def test_request_order_only_by_a_field(client):
    """The SORTING_FIELD must be a field: an expression is not evaluated and the features are not sorted."""
    unsorted = _sorted_ids(client, "null")

    # A field: the features are sorted
    assert _sorted_ids(client, "NAME_1") == [
        "france_parts.2",
        "france_parts.3",
        "france_parts.1",
        "france_parts.0",
    ]

    # Not a field: same order as without sorting
    assert _sorted_ids(client, "env('HOME')") == unsorted
    assert _sorted_ids(client, '-"OBJECTID"') == unsorted
