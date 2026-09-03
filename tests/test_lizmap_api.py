import json
import os

import pytest

from pathlib import Path

from qgis.server import (
    QgsServerRequest,
)


from lizmap_server.api.defaults import (
    SEARCH_PATH_ENV,
    PROJECTS_URI_ENV,
    collect_projects,
    resolve_project_uri,
    verify_config,
)


def test_lizmap_api_default_path_resolution(rootdir: Path):

    assert os.getenv(SEARCH_PATH_ENV) == "/data"
    assert os.getenv(PROJECTS_URI_ENV) == f"{rootdir}/data"

    verify_config()

    projects = list(collect_projects("tests", "/data"))
    print("\n::test_default_path_resolution::collect::\n", projects)

    assert len(projects) == 14

    resolved = resolve_project_uri("/data/legend")
    assert resolved is not None
    assert resolved.path == f"{rootdir}/data/legend"


def test_lizmap_api_routes(client):
    from lizmap_server.api import errors, routes

    route, match_infos = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/list")
    assert route is not None
    assert match_infos.get("PATH") is None

    route, match_infos = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/list/foo/bar")
    assert route is not None
    assert match_infos.get("PATH") == "foo/bar"

    route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/description")
    assert route is not None

    with pytest.raises(errors.HTTPNotFound):
        route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/description/foo")

    with pytest.raises(errors.HTTPNotFound):
        route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/layers/")

    route, match_infos = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/layers/bar")
    assert route is not None
    assert match_infos.get("Id") == "bar"

    route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/layouts")
    assert route is not None

    route, match_infos = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/layouts/foobar")
    assert route is not None
    assert match_infos.get("Name") == "foobar"


def test_lizmap_api_projects_list(client):
    """Test the Lizmap API for server settings"""

    # The query must work
    rv = client.get("/lizmap/api/v1/projects/list/data")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_server_api::projects::\n", content)


def test_lizmap_api_projects_description(client):
    """Test the Lizmap API for server settings"""

    rv = client.get("/lizmap/api/v1/projects/description?p=/data/montpellier/montpellier.qgs")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_server_api::description::\n", content)


def test_lizmap_api_projects_layers(client):
    """Test the Lizmap API for server settings"""

    layer_id = "tram_stop_work20150416102656130"

    rv = client.get(f"/lizmap/api/v1/projects/layers/{layer_id}?p=/data/montpellier/montpellier.qgs")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_server_api::description::\n", content)


def test_lizmap_api_projects_layouts(client):
    """Test the Lizmap API for server settings"""

    rv = client.get("/lizmap/api/v1/projects/layouts?p=/data/montpellier/montpellier.qgs")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_server_api::layouts::\n", content)

    rv = client.get("/lizmap/api/v1/projects/layouts/Landscape A4?p=/data/montpellier/montpellier.qgs")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_server_api::layouts::1\n", content)


def test_lizmap_api_openapi(client):
    """Test lizmap openapi specifications"""
    rv = client.get("/lizmap/api/v1")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_openapi::content\n", content)


def test_lizmap_api_trailing_slash(client):
    rv = client.get("/lizmap/api/v1/")
    assert rv.status_code == 200


def test_lizmap_api_landinpage(client):
    """Test lizmap landing page"""
    rv = client.get("/lizmap/")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_landingpage::content\n", content)


def test_lizmap_api_projects_list_root(client):
    """The project list may be requested without any path."""
    rv = client.get("/lizmap/api/v1/projects/list")
    assert rv.status_code == 200

    content = json.loads(rv.content.decode("utf-8"))
    assert "projects" in content
    assert "links" in content


def test_lizmap_api_projects_list_failure(client, monkeypatch):
    """A project which cannot be opened is skipped from the list."""
    from lizmap_server.context.native import Context

    monkeypatch.setattr(Context, "load_project_def", lambda self, md, **kwargs: (None, {}))

    rv = client.get("/lizmap/api/v1/projects/list/data")
    assert rv.status_code == 200

    content = json.loads(rv.content.decode("utf-8"))
    assert content["projects"] == []


def test_lizmap_api_missing_project_parameter(client):
    """The 'p' parameter is mandatory."""
    rv = client.get("/lizmap/api/v1/projects/description")
    assert rv.status_code == 400

    content = json.loads(rv.content.decode("utf-8"))
    assert content == {"code": 400, "description": "Missing project 'p' parameters"}


def test_lizmap_api_unknown_project(client):
    """An unknown project must return a 404."""
    # The path cannot be resolved at all
    rv = client.get("/lizmap/api/v1/projects/description?p=/elsewhere/project.qgs")
    assert rv.status_code == 404

    # The path is resolved but the project does not exist
    rv = client.get("/lizmap/api/v1/projects/description?p=/data/i_do_not_exist.qgs")
    assert rv.status_code == 404

    content = json.loads(rv.content.decode("utf-8"))
    assert content == {"code": 404, "description": "Not found"}


def test_lizmap_api_unknown_layer(client):
    """An unknown layer must return a 404."""
    rv = client.get("/lizmap/api/v1/projects/layers/unknown?p=/data/montpellier/montpellier.qgs")
    assert rv.status_code == 404

    content = json.loads(rv.content.decode("utf-8"))
    assert content == {"code": 404, "description": "Layer not found"}


def test_lizmap_api_unknown_layout(client):
    """An unknown layout must return a 404."""
    rv = client.get("/lizmap/api/v1/projects/layouts/Unknown?p=/data/montpellier/montpellier.qgs")
    assert rv.status_code == 404

    content = json.loads(rv.content.decode("utf-8"))
    assert content == {"code": 404, "description": "Layout not found"}


def test_lizmap_api_internal_error(client, monkeypatch):
    """An unexpected error must return a 500."""
    from lizmap_server.api import routes

    route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/list")

    def broken(request, **match_info):
        raise RuntimeError("Something went wrong")

    monkeypatch.setattr(route, "fn", broken)

    rv = client.get("/lizmap/api/v1/projects/list")
    assert rv.status_code == 500

    content = json.loads(rv.content.decode("utf-8"))
    assert content == {"code": 500, "description": "Internal error"}


def test_lizmap_api_error_after_finish(client, monkeypatch):
    """An error raised after the response is sent must only be logged."""
    from lizmap_server.api import routes

    route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/list")

    def broken(request, **match_info):
        request.write_json({"status": "ok"})
        request.finish()
        raise RuntimeError("Too late")

    monkeypatch.setattr(route, "fn", broken)

    rv = client.get("/lizmap/api/v1/projects/list")
    assert rv.status_code == 200
    assert json.loads(rv.content.decode("utf-8")) == {"status": "ok"}


def test_lizmap_api_forwarded_headers(client):
    """The links must use the forwarded host."""
    rv = client.get(
        "/lizmap/api/v1/projects/list/data",
        headers={"X-Forwarded-Host": "example.com", "X-Forwarded-Proto": "https"},
    )
    assert rv.status_code == 200

    content = json.loads(rv.content.decode("utf-8"))
    assert content["links"][0]["href"].startswith("https://example.com/lizmap")


def test_lizmap_api_metadata(client):
    """The api metadata."""
    from lizmap_server.api.handlers import LizmapApi

    api = LizmapApi(client.server.serverInterface())
    assert api.name() == "Lizmap"
    assert api.description() == "Lizmap api endpoint"
    assert api.rootPath() == "/lizmap"
    assert api.version()
