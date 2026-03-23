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
    assert resolved.path ==  f"{rootdir}/data/legend"


def test_lizmap_api_routes(client):
    from lizmap_server.api import errors, routes

    route, match_infos  = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/list/")
    assert route is not None
    assert match_infos.get("PATH") == ""

    route, match_infos  = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/list/foo/bar")
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

    route, _ = routes.find_route(QgsServerRequest.GetMethod, "/api/v1/projects/layouts/")
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

    rv = client.get("/lizmap/api/v1/projects/layouts/?p=/data/montpellier/montpellier.qgs")
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
    rv = client.get("/lizmap/api/v1/")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_lizmap_openapi::content\n", content)


def test_lizmap_api_landinpage(client):
    """Test lizmap landing page"""
    rv = client.get("/lizmap/")
    assert rv.status_code == 200
    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    content = json.loads(rv.content.decode("utf-8"))
    print("\n::test_landingpage::content\n", content)


