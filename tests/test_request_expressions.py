"""Tests of the checks of the expressions sent in the OGC requests."""

import json

import pytest

from lizmap_server.request_expressions import (
    forbidden_function_in_expression,
    forbidden_function_in_request,
    forbidden_function_in_text,
)

from .utils import Client, OWSResponse, _build_query_string

PROJECT = "france_parts.qgs"


@pytest.mark.parametrize(
    "expression,expected",
    [
        # Functions reading other layers
        ("aggregate('layer', 'count', 1) = 3", "aggregate"),
        ("attribute(get_feature_by_id('layer', 1), 'user') = 'admin'", "get_feature_by_id"),
        ("get_feature('layer', 'id', 1) IS NOT NULL", "get_feature"),
        ("relation_aggregate('relation', 'count', 1) > 0", "relation_aggregate"),
        ("overlay_intersects('layer')", "overlay_intersects"),
        # Functions reading the server environment
        ("env('HOME') = '/home/qgis'", "env"),
        ("file_exists('/etc/passwd')", "file_exists"),
        # Case, whitespaces and comments between the name and the parenthesis
        ("AGGREGATE ('layer', 'count', 1) = 3", "aggregate"),
        ("aggregate /* comment */ ('layer', 'count', 1) = 3", "aggregate"),
        ("aggregate -- comment\n('layer', 'count', 1) = 3", "aggregate"),
        # In a list of expressions, as for several type names
        ("\"NAME_1\" = 'a';env('HOME') = 'b'", "env"),
        # Allowed expressions
        ("\"NAME_1\" = 'Bretagne'", None),
        ("\"environment\" = 'env' AND lower(\"NAME_1\") = 'a'", None),
        ("count(1) > 0", None),
        ("my_env(1) = 1", None),
        ("@project_path IS NOT NULL", None),
    ],
)
def test_forbidden_function_in_expression(expression: str, expected: str | None):
    """The forbidden functions are found in a QGIS expression.

    :param expression: The QGIS expression.
    :param expected: The expected forbidden function, or None.
    """
    assert forbidden_function_in_expression(expression) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        # Expressions of a layout label
        ("Title [% env('HOME') %]", "env"),
        ("[% 1 + 1 %] and [% aggregate('layer', 'count', 1) %]", "aggregate"),
        ("Title [% @project_title %]", None),
        # Plain text is not an expression
        ("Population env (2 km)", None),
        # Functions of an OGC filter
        ('<ogc:Filter><ogc:Function name="aggregate"/></ogc:Filter>', "aggregate"),
        ("<Filter><Function name='Get_Feature_By_Id'/></Filter>", "get_feature_by_id"),
        ('<Filter><Function name=" env "/></Filter>', "env"),
        # XML entities are decoded, as by an XML parser
        ('<Filter><Function name="&#101;nv"/></Filter>', "env"),
        ('<Filter><Function name="upper"/></Filter>', None),
        ("<Filter><PropertyIsEqualTo><PropertyName>env</PropertyName></PropertyIsEqualTo></Filter>", None),
    ],
)
def test_forbidden_function_in_text(text: str, expected: str | None):
    """The forbidden functions are found in the label expressions and in the OGC filters.

    :param text: The text to check.
    :param expected: The expected forbidden function, or None.
    """
    assert forbidden_function_in_text(text) == expected


def test_forbidden_function_in_request():
    """All the parameters and the body of a request are checked."""
    # EXP_FILTER, whatever the case of the parameter name
    assert forbidden_function_in_request({"service": "WFS", "exp_filter": "env('HOME') = 'a'"}) == "env"

    # Label of a GetPrint request
    params = {"SERVICE": "WMS", "REQUEST": "GetPrint", "my_label": "[% file_exists('/etc/passwd') %]"}
    assert forbidden_function_in_request(params) == "file_exists"

    # Body of a POST request, as XML or as an URL encoded form
    body = '<GetFeature><Query><Filter><Function name="aggregate"/></Filter></Query></GetFeature>'
    assert forbidden_function_in_request({}, body) == "aggregate"
    assert forbidden_function_in_request({}, "LABEL=%5B%25+env%28%27HOME%27%29+%25%5D") == "env"

    # The services with their own checks are not checked
    params = {"SERVICE": "EXPRESSION", "STRING": "[% aggregate('layer', 'count', 1) %]"}
    assert forbidden_function_in_request(params) is None

    # Allowed request
    params = {"SERVICE": "WFS", "EXP_FILTER": "\"NAME_1\" = 'Bretagne'", "TYPENAME": "france_parts"}
    assert forbidden_function_in_request(params) is None


def _get_feature(client: Client, **params: str) -> OWSResponse:
    """Send a WFS GetFeature request on the france_parts layer.

    :param client: The QGIS Server test client.
    :param params: The additional parameters, already URL encoded.
    :returns: The response.
    """
    qs = {
        "SERVICE": "WFS",
        "VERSION": "1.0.0",
        "REQUEST": "GetFeature",
        "MAP": PROJECT,
        "TYPENAME": "france_parts",
        "OUTPUTFORMAT": "GeoJSON",
        **params,
    }
    return client.get(_build_query_string(qs, use_urllib=True), PROJECT)


def test_wfs_exp_filter(client):
    """A WFS EXP_FILTER with a forbidden function is rejected, an allowed one is evaluated."""
    rv = _get_feature(client, EXP_FILTER="aggregate('france_parts', 'count', 1) = 4")
    assert rv.status_code == 400
    assert b"Expression function 'aggregate' is not allowed" in rv.content

    rv = _get_feature(client, EXP_FILTER="\"NAME_1\" = 'Bretagne'")
    assert rv.status_code == 200
    assert len(json.loads(rv.content)["features"]) == 1


def test_wfs_ogc_filter(client):
    """A WFS FILTER with a forbidden function is rejected."""
    ogc_filter = (
        '<Filter xmlns="http://www.opengis.net/ogc"><PropertyIsEqualTo>'
        '<Function name="aggregate"><Literal>france_parts</Literal><Literal>count</Literal>'
        "<Literal>1</Literal></Function><Literal>4</Literal></PropertyIsEqualTo></Filter>"
    )
    rv = _get_feature(client, FILTER=ogc_filter)
    assert rv.status_code == 400
    assert b"Expression function 'aggregate' is not allowed" in rv.content
