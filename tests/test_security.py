"""Regression tests for security breaches.

Each test below asserts the *security property* a fix has to establish,
not a particular implementation of the fix, so that the tests stay valid
whichever remediation is chosen.
"""

import gc
import json
import os
import weakref

from pathlib import Path
from typing import Sequence
from urllib.parse import quote

import pytest

from qgis.core import (
    QgsAttributeEditorField,
    QgsCategorizedSymbolRenderer,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProject,
    QgsRasterLayer,
    QgsRendererCategory,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
    edit,
)
from qgis.server import QgsBufferServerResponse

from lizmap_server.api import defaults, errors
from lizmap_server.core import (
    get_lizmap_groups,
    get_lizmap_override_filter,
    get_lizmap_user_login,
    is_editing_context,
)
from lizmap_server.filter_by_polygon import NO_FEATURES, FilterByPolygon
from lizmap_server.legend_onoff_filter import LegendOnOffAccessControl, LegendOnOffFilter
from lizmap_server.lizmap_accesscontrol import LizmapAccessControlFilter
from lizmap_server.tooltip import Tooltip

from .utils import _build_query_string


#
# Fakes, shared by several findings
#


class FakeRequestHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, params=None, headers=None):
        self._params = params if params is not None else {}
        self._headers = headers if headers is not None else {}

    def parameterMap(self):
        return self._params

    def requestHeaders(self):
        return self._headers


class FakeAccessControls:
    """Minimal duck typing of a QgsAccessControlFilter chain."""

    def __init__(self, subset_string):
        self._subset_string = subset_string

    def extraSubsetString(self, layer):
        return self._subset_string


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, handler=None, subset_string=""):
        self._handler = handler
        self._access_controls = FakeAccessControls(subset_string)

    def requestHandler(self):
        return self._handler

    def accessControls(self):
        return self._access_controls


@pytest.fixture
def project():
    """A clean QGIS project instance."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


def _matching_ids(layer: QgsVectorLayer, expression: str) -> list:
    """The ids of the features matching the expression."""
    request = QgsFeatureRequest()
    request.setFilterExpression(expression)
    return sorted(feature["id"] for feature in layer.getFeatures(request))


#
# Login filter — Operator precedence drops the polygon filter (ACL bypass)
#
# `_filter_by_login` returns an unparenthesised OR chain which is concatenated
# with the polygon filter using AND. Because AND binds tighter than OR, every
# feature whose login attribute is 'all' escapes the spatial restriction.
#


# Only the two features inside this polygon may ever be returned.
POLYGON_FILTER = "intersects($geometry, geom_from_wkt('POLYGON((0 0, 0 5, 5 5, 5 0, 0 0))'))"

INSIDE = [1, 2]
ALL_IDS = [1, 2, 3, 4]


def _acl_layer() -> QgsVectorLayer:
    """Four points, two inside the polygon above, with an ACL attribute."""
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer&field=f:string", "points", "memory")
    assert layer.isValid()
    with edit(layer):
        for identifier, value, wkt in (
            (1, "grp_1", "POINT(1 1)"),  # inside, own group
            (2, "all", "POINT(2 2)"),  # inside, everyone
            (3, "grp_1", "POINT(10 10)"),  # outside, own group
            (4, "all", "POINT(11 11)"),  # outside, everyone
        ):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes([identifier, value])
            assert layer.addFeature(feature)
    return layer


def test_security_1_login_filter_does_not_escape_the_polygon_filter():
    """`polygon AND login_filter` must not return features outside the polygon."""
    layer = _acl_layer()
    config = {
        "filterPrivate": False,
        "filterAttribute": "f",
        "allow_multiple_acl_values": False,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("grp_1",), "", "ogr")

    # On its own, the filter lets every feature of the two groups through
    assert _matching_ids(layer, login_filter) == ALL_IDS

    # Combined with the spatial filter, only the features inside the polygon
    assert _matching_ids(layer, f"{POLYGON_FILTER} AND {login_filter}") == INSIDE


def test_security_1_login_filter_with_multiple_acl_values():
    """The eight terms long chain must not escape the polygon filter either."""
    layer = _acl_layer()
    config = {
        "filterPrivate": False,
        "filterAttribute": "f",
        "allow_multiple_acl_values": True,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("grp_1",), "", "postgres")

    assert _matching_ids(layer, login_filter) == ALL_IDS
    assert _matching_ids(layer, f"{POLYGON_FILTER} AND {login_filter}") == INSIDE


def test_security_1_private_login_filter_does_not_escape_the_polygon_filter():
    """The 'filterPrivate' variant has the same precedence problem."""
    layer = _acl_layer()
    config = {
        "filterPrivate": True,
        "filterAttribute": "f",
        "allow_multiple_acl_values": False,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("other",), "grp_1", "ogr")

    assert _matching_ids(layer, login_filter) == ALL_IDS
    assert _matching_ids(layer, f"{POLYGON_FILTER} AND {login_filter}") == INSIDE


def test_security_1_login_filter_is_safe_when_joined_by_qgis():
    """QGIS joins the filter to other subset strings with AND, without parenthesis."""
    layer = _acl_layer()
    config = {
        "filterPrivate": False,
        "filterAttribute": "f",
        "allow_multiple_acl_values": False,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("grp_1",), "", "ogr")

    # A subset string hiding the feature 4, as another access control filter would do
    assert _matching_ids(layer, f'"id" <> 4 AND {login_filter}') == [1, 2, 3]


#
# QGIS expression injection via user group / login
#
# The groups (or the login) come from the `X-Lizmap-User-Groups` header or from
# the `LIZMAP_USER_GROUPS` parameter and are interpolated verbatim into a QGIS
# expression by `_polygon_for_groups_with_qgis_api`.
#


# Closes the string literal and the enclosing calls, appends 'or true', then
# re-opens what the template closes after the interpolation point.
GROUP_INJECTION = (
    "a'), trim(@element))) or true or array_intersect(array('x'), array_foreach(string_to_array('b"
)

# East and west polygons, plus a polygon for a group whose name holds a quote
EAST = "POLYGON((0 0,0 5,5 5,5 0,0 0))"
WEST = "POLYGON((0 0,0 -5,-5 -5,-5 0,0 0))"
FAR = "POLYGON((10 10,10 15,15 15,15 10,10 10))"


def _polygon_config(project: QgsProject) -> tuple[dict, QgsVectorLayer, QgsVectorLayer]:
    """A filter by polygon configuration, its polygon layer and the filtered layer."""
    polygon = QgsVectorLayer(
        "Polygon?crs=epsg:4326&field=id:integer&field=groups:string",
        "polygon",
        "memory",
    )
    assert polygon.isValid()
    with edit(polygon):
        for identifier, groups, wkt in (
            (1, "east,admins", EAST),
            (2, "west,admins", WEST),
            (3, "O'Brien", FAR),
        ):
            feature = QgsFeature(polygon.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes([identifier, groups])
            assert polygon.addFeature(feature)

    points = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer", "points", "memory")
    assert points.isValid()
    with edit(points):
        for identifier, wkt in ((1, "POINT(1 1)"), (2, "POINT(-1 -1)"), (3, "POINT(11 11)")):
            feature = QgsFeature(points.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes([identifier])
            assert points.addFeature(feature)

    project.addMapLayer(polygon)

    config = {
        "config": {
            "polygon_layer_id": polygon.id(),
            "group_field": "groups",
        },
        "layers": [
            {
                "layer": points.id(),
                "primary_key": "id",
                "spatial_relationship": "intersects",
                "filter_mode": "display_and_editing",
            },
        ],
    }
    return config, polygon, points


def test_security_2_group_injection_does_not_select_every_polygon(project):
    """An expression injected in a group name must not lift the spatial restriction."""
    config, _, points = _polygon_config(project)

    injected = FilterByPolygon(config, points)._polygon_for_groups_with_qgis_api((GROUP_INJECTION,))
    unknown = FilterByPolygon(config, points)._polygon_for_groups_with_qgis_api(("unknown",))

    # The injected value is a group name like any other: it matches no polygon
    assert injected.isEmpty(), f"The injection selected {injected.asWkt(0)}"
    assert unknown.isEmpty()


def test_security_2_group_injection_does_not_lift_the_subset_string(project):
    """The generated subset string must hide everything for an injected group."""
    config, _, points = _polygon_config(project)

    subset, ewkt = FilterByPolygon(config, points).subset_sql((GROUP_INJECTION,))

    assert subset == NO_FEATURES
    assert ewkt == ""


def test_security_2_group_with_a_quote_is_matched_literally(project):
    """A group name holding a single quote must be quoted, not break the expression."""
    config, _, points = _polygon_config(project)

    geometry = FilterByPolygon(config, points)._polygon_for_groups_with_qgis_api(("O'Brien",))

    # The third polygon, and only this one
    assert not geometry.isEmpty()
    assert geometry.intersects(QgsGeometry.fromWkt(FAR))
    assert not geometry.intersects(QgsGeometry.fromWkt(EAST))


def test_security_2_user_with_a_quote_is_matched_literally(project):
    """The same values may come from the login when 'filter_by_user' is set."""
    config, _, points = _polygon_config(project)
    config["config"]["filter_by_user"] = True

    config_filter = FilterByPolygon(config, points)
    assert config_filter.is_filtered_by_user()

    subset, _ = config_filter.subset_sql(("O'Brien",))

    # The point inside the 'O'Brien' polygon
    assert subset == '"id" IN ( 3 )'


#
#  Path traversal in the Lizmap API project endpoints
#
# `PurePosixPath` does not normalise '..', so the containment checks in
# `StaticRoute.resolve_path` and `DynamicRoute.resolve_path` pass for paths
# escaping the configured root.
#


TRAVERSALS = (
    "/data/../../etc/passwd",
    "/data/../conftest.py",
    "/data/montpellier/../../../etc/passwd",
    "/data/..",
    "../other",
)


@pytest.mark.parametrize("path", TRAVERSALS)
def test_security_3_resolve_defaults_project_uri_rejects_traversal(path):
    """A path escaping the search path must not be resolved."""
    with pytest.raises(errors.HTTPForbidden):
        defaults.resolve_project_uri(path)


@pytest.mark.parametrize("path", TRAVERSALS)
def test_security_3_collect_projects_rejects_traversal(path):
    """No project may be collected from outside the search path."""
    with pytest.raises(errors.HTTPForbidden):
        list(defaults.collect_projects("Test", path))


def test_security_3_api_description_cannot_escape_the_root(client, rootdir, tmp_path):
    """A project outside the configured root must not be opened by the API."""
    outside = tmp_path / "outside.qgs"
    assert QgsProject().write(str(outside))

    relative = os.path.relpath(outside, Path(rootdir).joinpath("data"))
    assert relative.startswith("..")

    response = client.get(f"/lizmap/api/v1/projects/description?p=/data/{relative}")

    assert response.status_code == 403, response.content


def test_security_3_api_layers_cannot_escape_the_root(client, rootdir, tmp_path):
    """The '?p=' parameter of the other endpoints must be checked as well."""
    outside = tmp_path / "outside.qgs"
    assert QgsProject().write(str(outside))

    relative = os.path.relpath(outside, Path(rootdir).joinpath("data"))
    query = f"?p=/data/{relative}"

    assert client.get(f"/lizmap/api/v1/projects/layers/unknown{query}").status_code == 403
    assert client.get(f"/lizmap/api/v1/projects/layouts{query}").status_code == 403


def test_security_3_api_list_cannot_escape_the_root(client):
    """The '{PATH:.+}' pattern matches '..': no project may be listed from above."""
    response = client.get("/lizmap/api/v1/projects/list/data/..")

    if response.status_code == 200:
        content = json.loads(response.content.decode("utf-8"))
        assert content["projects"] == [], "Projects listed from outside the search path"
    else:
        assert response.status_code == 403


#
# The EXPRESSION service evaluates unrestricted client expressions
#
# The fix is design-level: either allowlist the referenced functions and layers
# on the unsafe paths, or gate them behind an environment variable. The tests
# only assert the outcome — the disclosed value must not reach the response —
# so any of those remediations satisfies them.
#


SECRET_ENV = "LIZMAP_TEST_DATABASE_PASSWORD"
SECRET_VALUE = "s3cr3t-database-password"

EXPRESSION_PROJECT = "france_parts.qgs"
LAYER = "france_parts"


@pytest.fixture
def secret_env(monkeypatch):
    """An environment variable holding a secret, as a database password would."""
    monkeypatch.setenv(SECRET_ENV, SECRET_VALUE)
    return SECRET_VALUE


ENV_REQUESTS = {
    "EVALUATE": {
        "REQUEST": "Evaluate",
        "EXPRESSIONS": '{{"a":"{}"}}'.format(quote(f"env('{SECRET_ENV}')", safe="")),
    },
    "VIRTUALFIELDS": {
        "REQUEST": "VirtualFields",
        "VIRTUALS": '{{"a":"{}"}}'.format(quote(f"env('{SECRET_ENV}')", safe="")),
        "LIMIT": "1",
    },
    "REPLACEEXPRESSIONTEXT": {
        "REQUEST": "ReplaceExpressionText",
        "STRING": quote(f"[% env('{SECRET_ENV}') %]", safe=""),
    },
}


@pytest.mark.parametrize("request_name", sorted(ENV_REQUESTS))
def test_security_4_env_is_not_disclosed(client, secret_env, request_name):
    """`env()` must not read the server environment on behalf of a client."""
    qs = {
        "SERVICE": "EXPRESSION",
        "MAP": EXPRESSION_PROJECT,
        "LAYER": LAYER,
    }
    qs.update(ENV_REQUESTS[request_name])

    response = client.get(_build_query_string(qs), EXPRESSION_PROJECT)

    assert SECRET_VALUE.encode() not in response.content, response.content


def test_security_4_env_is_not_an_oracle_in_a_filter(client, secret_env):
    """A FILTER must not be usable to guess the value of an environment variable."""
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "GetFeatureWithFormScope",
        "MAP": EXPRESSION_PROJECT,
        "LAYER": LAYER,
        "FORM_FEATURE": '{"type":"Feature","geometry":null,"properties":{"prop0":"x"}}',
    }

    def _features(value):
        query = dict(qs)
        query["FILTER"] = quote(f"env('{SECRET_ENV}') = '{value}'", safe="")
        response = client.get(_build_query_string(query), EXPRESSION_PROJECT)
        content = json.loads(response.content.decode("utf-8"))
        return len(content.get("features", []))

    # A right and a wrong guess must not be distinguishable
    assert _features(SECRET_VALUE) == _features("wrong-guess")


def test_security_4_aggregate_does_not_bypass_the_login_filter(client):
    """`aggregate()` must not read the rows hidden by the login filter.

    The 'france_parts_liz_filter_group' project filters the layer on 'NAME_1'
    against the user groups: the 'test1' group sees no feature at all.
    """
    project_file = "france_parts_liz_filter_group.qgs"
    expression = "aggregate('france_parts','concatenate',attribute('NAME_1'),concatenator:=',')"
    qs = {
        "SERVICE": "EXPRESSION",
        "REQUEST": "Evaluate",
        "MAP": project_file,
        "LAYER": LAYER,
        "EXPRESSIONS": '{{"a":"{}"}}'.format(quote(expression, safe="")),
    }

    response = client.get(
        _build_query_string(qs),
        project_file,
        {"X-Lizmap-User-Groups": "test1"},
    )

    assert b"Bretagne" not in response.content, response.content
    assert b"Pays de la Loire" not in response.content, response.content


#
# Unescaped values in the generated IN (…) subset string
#
# `_format_sql_in` quotes the values by string interpolation. The values are
# primary key values read back from the layer, so a value holding a single
# quote breaks — or extends — the subset string applied to the layer.
#


def _code_layer(values: Sequence[str]) -> QgsVectorLayer:
    """A layer with a text primary key holding the given values."""
    layer = QgsVectorLayer("None?field=id:integer&field=code:string", "codes", "memory")
    assert layer.isValid()
    with edit(layer):
        for identifier, value in enumerate(values, start=1):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([identifier, value])
            assert layer.addFeature(feature)
    return layer


def test_security_5_format_sql_in_escapes_the_quote():
    """A value holding a single quote must not break the subset string."""
    value = "L'Île"
    layer = _code_layer(["Paris", value, "Lyon"])

    subset = FilterByPolygon._format_sql_in("code", (value,))

    expression = QgsExpression(subset)
    assert not expression.hasParserError(), f"{subset}: {expression.parserErrorString()}"
    assert _matching_ids(layer, subset) == [2]


def test_security_5_format_sql_in_does_not_allow_injection():
    """A crafted primary key value must not turn the filter into a tautology."""
    payload = "x') OR ('1'='1"
    layer = _code_layer(["Paris", "Lyon", payload])

    subset = FilterByPolygon._format_sql_in("code", (payload,))

    # Only the feature actually holding this value
    assert _matching_ids(layer, subset) == [3], subset


def test_security_5_format_sql_in_quotes_the_column():
    """The primary key must be quoted as a column reference."""
    subset = FilterByPolygon._format_sql_in('co"de', (1,))

    expression = QgsExpression(subset)
    assert not expression.hasParserError(), f"{subset}: {expression.parserErrorString()}"


def test_security_5_format_sql_in_keeps_the_plain_values():
    """The escaping must not change the output for ordinary values."""
    assert FilterByPolygon._format_sql_in("code", (1, 2, 3)) == '"code" IN ( 1 , 2 , 3 )'
    assert FilterByPolygon._format_sql_in("code", ("a", "b")) == "\"code\" IN ( 'a' , 'b' )"


#
# Shared project state mutated per-request and not always restored
#
# The subset string of the cached layer and the current style are restored at
# the end of the handler, but not in a `try/finally`.
#


@pytest.fixture
def france_parts(rootdir, project):
    """The 'france_parts' layer, added to the project instance."""
    layer = QgsVectorLayer(
        str(rootdir.joinpath("data/france_parts/france_parts.shp")),
        "france_parts",
        "ogr",
    )
    assert layer.isValid()
    project.addMapLayer(layer)
    return layer


ACL_SUBSET = "\"NAME_1\" = 'Bretagne'"


def test_security_6_virtual_fields_restores_the_subset_string(project, france_parts, monkeypatch):
    """An exception in the feature loop must not leave the ACL filter installed."""
    from lizmap_server.expression_service import request_virtualfields as module

    def boom(*args, **kwargs):
        raise RuntimeError("Failure inside the feature loop")

    monkeypatch.setattr(module, "get_server_fid", boom)

    params = {"LAYER": "france_parts", "VIRTUALS": '{"a": "1"}'}
    with pytest.raises(RuntimeError):
        module.virtual_fields(
            params,
            QgsBufferServerResponse(),
            project,
            FakeServerInterface(subset_string=ACL_SUBSET),
        )

    assert france_parts.subsetString() == ""


def test_security_6_replace_expression_text_restores_the_subset_string(
    project,
    france_parts,
    monkeypatch,
):
    """The same, for the REPLACEEXPRESSIONTEXT request."""
    from lizmap_server.expression_service import request_replaceexpressiontext as module

    class Boom:
        @staticmethod
        def encodeValue(value):
            raise RuntimeError("Failure inside the feature loop")

    monkeypatch.setattr(module, "QgsJsonUtils", Boom)

    params = {
        "LAYER": "france_parts",
        "STRINGS": '["[% 1 + 1 %]"]',
        "FEATURE": '{"type": "Feature", "geometry": null, "properties": {"NAME_1": "Bretagne"}}',
    }
    with pytest.raises(RuntimeError):
        module.replace_expression_text(
            params,
            QgsBufferServerResponse(),
            project,
            FakeServerInterface(subset_string=ACL_SUBSET),
        )

    assert france_parts.subsetString() == ""


def _categorized_layer(name: str = "categorized") -> QgsVectorLayer:
    """A categorized vector layer, with two rule keys."""
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer&field=cat:string", name, "memory")
    assert layer.isValid()

    def symbol():
        return QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.PointGeometry)

    categories = [
        QgsRendererCategory("a", symbol(), "A"),
        QgsRendererCategory("b", symbol(), "B"),
    ]
    layer.setRenderer(QgsCategorizedSymbolRenderer("cat", categories))
    return layer


def test_security_6_legend_onoff_restores_the_current_style(client, project):
    """The client supplied style must not stay on the shared project layer."""
    layer = _categorized_layer()
    assert layer.styleManager().addStyleFromLayer("other")
    layer.styleManager().setCurrentStyle("default")
    project.addMapLayer(layer)

    params = {"LAYERS": "categorized", "STYLES": "other"}

    access_control = LegendOnOffAccessControl(client.server.serverInterface())
    access_control.iface = FakeServerInterface(FakeRequestHandler(params))
    access_control.layerPermissions(layer)

    legend_filter = LegendOnOffFilter(client.server.serverInterface())
    legend_filter.serverInterface = lambda: FakeServerInterface(FakeRequestHandler(params))
    legend_filter.responseComplete()

    # The next request must not inherit the style of this one
    assert layer.styleManager().currentStyle() == "default"


#
# Identity accepted from unauthenticated request parameters
#
# By design, but the security prerequisite (QGIS Server unreachable except
# through Lizmap Web Client) is undocumented. The review suggests documenting
# it and adding an environment gated 'headers only' mode.
#
# The name below is the one the tests expect: change it here and in the
# implementation together.
#

HEADERS_ONLY_ENV = "QGIS_SERVER_LIZMAP_IDENTITY_HEADERS_ONLY"


@pytest.fixture
def headers_only(monkeypatch):
    """Enable the 'identity from headers only' mode."""
    monkeypatch.setenv(HEADERS_ONLY_ENV, "TRUE")


def test_security_7_groups_from_parameters_are_ignored(headers_only):
    """`LIZMAP_USER_GROUPS` must be ignored in headers only mode."""
    handler = FakeRequestHandler(params={"LIZMAP_USER_GROUPS": "admins"})
    assert get_lizmap_groups(handler) == ()

    # The header is still honoured
    handler = FakeRequestHandler(
        params={"LIZMAP_USER_GROUPS": "admins"},
        headers={"X-Lizmap-User-Groups": "users"},
    )
    assert get_lizmap_groups(handler) == ("users",)


def test_security_7_login_from_parameters_is_ignored(headers_only):
    """`LIZMAP_USER` must be ignored in headers only mode."""
    handler = FakeRequestHandler(params={"LIZMAP_USER": "admin"})
    assert get_lizmap_user_login(handler) == ""

    handler = FakeRequestHandler(
        params={"LIZMAP_USER": "admin"},
        headers={"X-Lizmap-User": "user"},
    )
    assert get_lizmap_user_login(handler) == "user"


def test_security_7_override_filter_from_parameters_is_ignored(headers_only):
    """`LIZMAP_OVERRIDE_FILTER` disables all row level filtering: parameters must not set it."""
    handler = FakeRequestHandler(params={"LIZMAP_OVERRIDE_FILTER": "1"})
    assert get_lizmap_override_filter(handler) is False

    handler = FakeRequestHandler(
        params={"LIZMAP_OVERRIDE_FILTER": "0"},
        headers={"X-Lizmap-Override-Filter": "1"},
    )
    assert get_lizmap_override_filter(handler) is True


def test_security_7_edition_context_from_parameters_is_ignored(headers_only):
    """`LIZMAP_EDITION_CONTEXT` selects the editing filters: parameters must not set it."""
    handler = FakeRequestHandler(params={"LIZMAP_EDITION_CONTEXT": "1"})
    assert is_editing_context(handler) is False

    handler = FakeRequestHandler(
        params={"LIZMAP_EDITION_CONTEXT": "0"},
        headers={"X-Lizmap-Edition-Context": "1"},
    )
    assert is_editing_context(handler) is True


def test_security_7_parameters_are_still_accepted_by_default():
    """Without the environment variable, the documented parameters keep working."""
    handler = FakeRequestHandler(params={"LIZMAP_USER_GROUPS": "admins"})
    assert get_lizmap_groups(handler) == ("admins",)

    handler = FakeRequestHandler(params={"LIZMAP_OVERRIDE_FILTER": "1"})
    assert get_lizmap_override_filter(handler) is True


def test_security_7_trust_boundary_is_documented(rootdir):
    """The README must state the prerequisite of the parameter based identity.

    The identity parameters are only safe while QGIS Server is unreachable
    except through Lizmap Web Client, and while LWC strips them from the
    client supplied OWS query strings.
    """
    readme = Path(rootdir).parent.joinpath("README.md").read_text(encoding="utf-8").lower()

    assert "trust boundary" in readme, "The README must have a 'trust boundary' section"
    assert "lizmap_override_filter" in readme
    assert "lizmap_user_groups" in readme


#
# Lower severity observations
#


@pytest.mark.parametrize("value", ("a", "a:b:c", "", ";", "a:b;c", ":", "a:"))
def test_security_8_malformed_legend_on_is_not_an_error(project, value):
    """A malformed LEGEND_ON must not raise: the request is unauthenticated."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    LegendOnOffAccessControl._setup_legend(layer, value, True)
    LegendOnOffFilter._reset_legend(value, project)


@pytest.mark.parametrize("parameter", ("LEGEND_ON", "LEGEND_OFF"))
def test_security_8_malformed_legend_parameter_in_permissions(client, project, parameter):
    """`layerPermissions` is called on every WMS request: it must not raise."""
    layer = _categorized_layer()
    project.addMapLayer(layer)

    access_control = LegendOnOffAccessControl(client.server.serverInterface())
    access_control.iface = FakeServerInterface(
        FakeRequestHandler({"LAYERS": "categorized", parameter: "categorized"}),
    )

    access_control.layerPermissions(layer)


def test_security_8_legend_on_a_raster_layer(client, project, rootdir):
    """A raster renderer has no 'checkLegendSymbolItem': it must be skipped."""
    raster = QgsRasterLayer(str(rootdir.joinpath("data/raster.asc")), "raster")
    assert raster.isValid()
    project.addMapLayer(raster)

    LegendOnOffAccessControl._setup_legend(raster, "raster:0", True)

    access_control = LegendOnOffAccessControl(client.server.serverInterface())
    access_control.iface = FakeServerInterface(
        FakeRequestHandler({"LAYERS": "raster", "LEGEND_ON": "raster:0"}),
    )

    access_control.layerPermissions(raster)


def test_security_8_maptip_escapes_the_feature_values(project):
    """A feature value must not be injected as HTML in the popup."""
    layer = QgsVectorLayer(
        "Point?crs=epsg:4326&field=id:integer&field=name:string",
        "layer",
        "memory",
    )
    assert layer.isValid()
    with edit(layer):
        feature = QgsFeature(layer.fields())
        feature.setAttributes([1, "<script>alert('xss')</script>"])
        assert layer.addFeature(feature)

    index = layer.fields().indexOf("name")
    node = QgsAttributeEditorField("name", index, None)
    html = Tooltip.create_popup_node_item_from_form(
        layer,
        node,
        1,
        [],
        "",
        project.relationManager(),
    )

    context = QgsExpressionContext()
    context.appendScope(QgsExpressionContextUtils.globalScope())
    context.appendScope(QgsExpressionContextUtils.layerScope(layer))
    context.setFeature(next(layer.getFeatures()))

    rendered = QgsExpression.replaceExpressionText(html, context)

    assert "<script>" not in rendered, rendered


def test_security_8_filter_by_polygon_does_not_retain_the_instance(project):
    """The `lru_cache` on the instance methods must not keep the layers alive."""
    config, _, points = _polygon_config(project)

    config_filter = FilterByPolygon(config, points)
    config_filter._polygon_for_groups_with_qgis_api(("east",))
    config_filter._features_ids_with_qgis_api(QgsGeometry.fromWkt(EAST))

    reference = weakref.ref(config_filter)
    del config_filter
    gc.collect()

    assert reference() is None, "The filter by polygon instance is retained by the cache"
