import json
import os

import pytest


from lizmap_server.tos_definitions import (
    BING_KEY,
    GOOGLE_KEY,
    strict_tos_check_key,
)


QUERY = "/lizmap/server.json"
KEY = "QGIS_SERVER_LIZMAP_REVEAL_SETTINGS"


def test_lizmap_server_info(client):
    """Test the Lizmap API for server settings"""
    # The environment variable is already there
    assert os.getenv(KEY) == "TRUE"

    # Test default values
    if strict_tos_check_key(GOOGLE_KEY) in os.environ:
        del os.environ[strict_tos_check_key(GOOGLE_KEY)]
    if strict_tos_check_key(BING_KEY) in os.environ:
        del os.environ[strict_tos_check_key(BING_KEY)]

    # The query must work
    rv = client.get(QUERY)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("application/json") == 0

    json_content = json.loads(rv.content.decode("utf-8"))
    assert "qgis_server" in json_content

    expected = {
        "google": True,
        "bing": True,
    }
    assert json_content["qgis_server"]["external_providers_tos_checks"] == expected

    # Names and versions are used in Lizmap Web Client
    expected_plugins = ("atlasprint", "wfsOutputExtension", "lizmap_server")
    assert len(json_content["qgis_server"]["plugins"].keys()) == len(expected_plugins)
    for plugin in expected_plugins:
        assert json_content["qgis_server"]["plugins"][plugin]["name"] == plugin
        assert json_content["qgis_server"]["plugins"][plugin]["version"] == "Not found"

    assert len(json_content["qgis_server"]["fonts"]) >= 1
    assert len(json_content["qgis_server"].get("py_qgis_server").keys()) >= 2


def test_tos_checks(client):
    """Test when TOS for external providers are checked."""
    os.environ[strict_tos_check_key(GOOGLE_KEY)] = str(False)
    os.environ[strict_tos_check_key(BING_KEY)] = str(True)
    rv = client.get(QUERY)
    json_content = json.loads(rv.content.decode("utf-8"))
    expected = {
        "google": False,
        "bing": True,
    }
    assert json_content["qgis_server"]["external_providers_tos_checks"] == expected
    del os.environ[strict_tos_check_key(GOOGLE_KEY)]
    del os.environ[strict_tos_check_key(BING_KEY)]


#
# Server info details
#


class FakeContext:
    """A server context with metadata, as py-qgis-server or QJazz."""

    name = "Test"
    git_repository_url = "https://example.com/repository"
    documentation_url = "https://example.com/documentation"

    def __init__(self, metadata=None, plugins=()):
        self._metadata = metadata
        self._plugins = plugins

    @property
    def metadata(self):
        return self._metadata

    def installed_plugins(self, keys, unknown_default=None):
        return iter(self._plugins)


def test_server_info_with_metadata(client):
    """A server context with metadata must be reported."""
    from lizmap_server.context.common import ServerMetadata
    from lizmap_server.server_info import server_info

    metadata = ServerMetadata(
        name="QJazz",
        version="1.2.3",
        is_stable=True,
        build_id=42,
        commit_id=1234,
    )

    content = server_info(FakeContext(metadata), client.server.serverInterface())

    assert content["qgis_server"]["py_qgis_server"] == {
        "found": True,
        "name": "QJazz",
        "version": "1.2.3",
        "build_id": 42,
        "commit_id": 1234,
        "stable": True,
        "git_repository_url": "https://example.com/repository",
        "documentation_url": "https://example.com/documentation",
    }

    # The expected plugins are always reported
    assert content["qgis_server"]["plugins"]["lizmap_server"]["version"] == "Not found"


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("shared", 'Not available on the "Basic" Lizmap Cloud plan'),
        ("dedicated", "Not installed"),
    ],
)
def test_server_info_lizmap_cloud(client, monkeypatch, mode, expected):
    """DataPlotly is reported according to the Lizmap Cloud plan."""
    from lizmap_server.server_info import DATA_PLOTLY, server_info

    monkeypatch.setenv("LZM_ALLOCATION_MODE", mode)

    content = server_info(FakeContext(), client.server.serverInterface())
    assert content["qgis_server"]["plugins"][DATA_PLOTLY]["version"] == expected


def test_server_info_official_version(client, monkeypatch):
    """An official QGIS build has no commit id."""
    from qgis.core import Qgis

    from lizmap_server.server_info import server_info

    monkeypatch.setattr(Qgis, "devVersion", staticmethod(lambda: "exported"))

    content = server_info(FakeContext(), client.server.serverInterface())
    assert content["qgis_server"]["metadata"]["commit_id"] == ""


def test_server_info_installed_plugin(client):
    """An installed plugin is not reported as missing."""
    from lizmap_server.server_info import server_info

    context = FakeContext(plugins=[("lizmap_server", {"version": "1.0.0", "name": "Lizmap"})])
    content = server_info(context, client.server.serverInterface())

    assert content["qgis_server"]["plugins"]["lizmap_server"]["version"] == "1.0.0"


def test_server_info_missing_service(client):
    """A service which is not registered is not reported."""
    from lizmap_server.server_info import server_info

    class FakeRegistry:
        def getService(self, name, version=""):
            return "a service" if name == "WMS" else None

    class FakeServerInterface:
        def serviceRegistry(self):
            return FakeRegistry()

    content = server_info(FakeContext(), FakeServerInterface())
    assert content["qgis_server"]["services"] == ["WMS"]
