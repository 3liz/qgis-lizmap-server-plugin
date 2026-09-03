"""Tests for the api routes and the default project paths resolution."""

from pathlib import PurePosixPath

import pytest

from qgis.server import QgsServerRequest

from lizmap_server.api import defaults, errors, routes
from lizmap_server.api.conditions import (
    PostconditionError,
    PreconditionError,
    assert_postcondition,
    assert_precondition,
)


#
# Conditions
#


def test_api_conditions():
    """Pre and post conditions must raise when not satisfied."""
    assert_precondition(True)
    assert_postcondition(True)

    with pytest.raises(PreconditionError, match="Pre condition failed"):
        assert_precondition(False)

    with pytest.raises(PreconditionError, match="Custom message"):
        assert_precondition(False, "Custom message")

    with pytest.raises(PostconditionError, match="Post condition failed"):
        assert_postcondition(False)

    with pytest.raises(PostconditionError, match="Custom message"):
        assert_postcondition(False, "Custom message")


#
# Errors
#


def test_api_errors():
    """The HTTP errors must carry their status code and reason."""
    error = errors.HTTPError(418, reason="I'm a teapot")
    assert str(error) == "HTTP 418: I'm a teapot"

    error = errors.HTTPError(418, reason="I'm a teapot", log_message="Short and stout")
    assert str(error) == "HTTP 418: I'm a teapot (Short and stout)"

    assert errors.HTTPMethodNotAllowed().status_code == 405
    assert errors.HTTPBadRequest().status_code == 400
    assert errors.HTTPNotFound().status_code == 404


#
# Routes
#


def test_api_static_route():
    """A static route matches an exact location."""
    route = routes.build_route("/api/v1/projects")
    assert not route.is_dynamic

    assert route.match("/api/v1/projects") == {}
    assert route.match("/api/v1/other") is None

    assert route.resolve_path(PurePosixPath("/api/v1/projects/foo")) == ({}, "/api/v1/projects")
    assert route.resolve_path(PurePosixPath("/somewhere/else")) is None


def test_api_dynamic_route():
    """A dynamic route extracts the path arguments."""
    route = routes.build_route("/data/{root}/projects")
    assert route.is_dynamic

    assert route.match("/data/foo/projects") == {"root": "foo"}
    assert route.match("/data/foo/bar/projects") is None

    assert route.resolve_path(PurePosixPath("/data/foo/projects")) == (
        {"root": "foo"},
        "/data/foo/projects",
    )
    assert route.resolve_path(PurePosixPath("/data/foo/other")) is None

    # With an explicit regular expression
    route = routes.build_route("/data/{PATH:.+}")
    assert route.match("/data/foo/bar") == {"PATH": "foo/bar"}


def test_api_invalid_routes():
    """An invalid route definition must be rejected."""
    with pytest.raises(ValueError, match="Invalid path"):
        routes.build_route("/data/{unbalanced")

    with pytest.raises(ValueError, match="Bad pattern"):
        routes.build_route("/data/{var:(unbalanced}")


def test_api_find_route_method_not_allowed():
    """A method without any route must be reported as not allowed."""
    with pytest.raises(errors.HTTPMethodNotAllowed):
        routes.find_route(QgsServerRequest.Method.DeleteMethod, "/api/v1/projects/list")


def test_api_register_post_route():
    """A POST route may be registered."""
    registered = len(routes.ROUTES)
    try:
        routes.post("/api/v1/test-post", doc=False)(lambda request, **kwargs: None)

        route = routes.ROUTES[-1]
        assert route.method == "post"
        assert route.me == QgsServerRequest.Method.PostMethod

        found, _ = routes.find_route(QgsServerRequest.Method.PostMethod, "/api/v1/test-post")
        assert found is route
    finally:
        del routes.ROUTES[registered:]


#
# Default paths
#


@pytest.fixture
def clear_defaults_cache():
    """The environment lookup is cached."""

    def _clear():
        defaults.projects_search_path.cache_clear()
        defaults.project_uri.cache_clear()

    _clear()
    yield _clear
    _clear()


def test_api_defaults_verify_config(monkeypatch, clear_defaults_cache):
    """A search path without a project uri is an error."""
    monkeypatch.setenv(defaults.SEARCH_PATH_ENV, "/data")
    monkeypatch.delenv(defaults.PROJECTS_URI_ENV, raising=False)
    clear_defaults_cache()

    assert defaults.project_uri() is None
    with pytest.raises(RuntimeError, match="Missing LIZMAP_PROJECTS_URI"):
        defaults.verify_config()


def test_api_defaults_no_search_path(monkeypatch, clear_defaults_cache):
    """Without a search path, no project uri may be resolved."""
    monkeypatch.delenv(defaults.SEARCH_PATH_ENV, raising=False)
    clear_defaults_cache()

    assert defaults.projects_search_path() is None
    assert defaults.resolve_project_uri("/data/legend") is None

    # Nothing is collected either
    assert list(defaults.collect_projects("Test", "/data")) == []

    # The config is valid: no search path at all
    defaults.verify_config()


def test_api_defaults_unmatched_path(rootdir):
    """A path which is not under the search path must not be resolved."""
    assert defaults.resolve_project_uri("/somewhere/else") is None

    with pytest.raises(PreconditionError, match="absolute"):
        defaults.resolve_project_uri("data/legend")


def test_api_defaults_dynamic_search_path(monkeypatch, clear_defaults_cache, rootdir):
    """A dynamic search path must be expanded in the projects uri."""
    monkeypatch.setenv(defaults.SEARCH_PATH_ENV, "/data/{root}")
    monkeypatch.setenv(defaults.PROJECTS_URI_ENV, f"file://{rootdir}/data/{{root}}")
    clear_defaults_cache()

    url = defaults.resolve_project_uri("/data/montpellier")
    assert url is not None
    assert url.path == f"{rootdir}/data/montpellier"

    # A deeper path does not match the route anymore
    assert defaults.resolve_project_uri("/data/montpellier/montpellier.qgs") is None


def test_api_defaults_query_template(monkeypatch, clear_defaults_cache, rootdir):
    """A '{path}' template in the query is substituted."""
    monkeypatch.setenv(defaults.SEARCH_PATH_ENV, "/data")
    monkeypatch.setenv(defaults.PROJECTS_URI_ENV, "postgresql://user@host/db?project={path}")
    clear_defaults_cache()

    url = defaults.resolve_project_uri("/data/legend")
    assert url is not None
    assert url.query == "project=legend"

    # Projects with another scheme are not collected
    assert list(defaults.collect_projects("Test", "/data/legend")) == []


def test_api_defaults_collect_single_project(rootdir):
    """A search path pointing to a single file yields this file."""
    projects = list(defaults.collect_projects("Test", "/data/legend.qgs"))
    assert len(projects) == 1
    url, location = projects[0]
    assert url.path == f"{rootdir}/data/legend.qgs"
    assert location == "/data/legend.qgs"


def test_api_defaults_collect_missing_path():
    """A search path pointing to a missing file yields nothing."""
    assert list(defaults.collect_projects("Test", "/data/i_do_not_exist")) == []
