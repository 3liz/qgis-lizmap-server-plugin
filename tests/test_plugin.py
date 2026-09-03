"""Tests for the plugin registration."""

import sys

import pytest

from qgis.server import (
    QgsBufferServerRequest,
    QgsBufferServerResponse,
    QgsServer,
    QgsServerRequest,
)

import lizmap_server

from lizmap_server import plugin as plugin_module
from lizmap_server.lizmap_api_handler import register_lizmap_api
from lizmap_server.plugin import LizmapServer


def _server_request(server: QgsServer, query: str) -> QgsBufferServerResponse:
    request = QgsBufferServerRequest(query, QgsServerRequest.Method.GetMethod, {}, None)
    response = QgsBufferServerResponse()
    server.handleRequest(request, response)
    return response


def test_plugin_class_factory(monkeypatch):
    """In QGIS Desktop, the plugin only displays a warning."""
    from qgis.PyQt.QtWidgets import QMessageBox

    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: messages.append((title, text))),
    )

    class FakeIface:
        def mainWindow(self):
            return None

    iface = FakeIface()
    plugin = lizmap_server.classFactory(iface)
    assert plugin.iface is iface

    plugin.initGui()
    assert plugin.unload() is None

    assert len(messages) == 1
    assert messages[0][0] == "Lizmap server plugin"
    assert "only" in messages[0][1]


def test_plugin_server_class_factory():
    """The server plugin must register all the services and filters."""
    server = QgsServer()
    plugin = lizmap_server.serverClassFactory(server.serverInterface())
    assert isinstance(plugin, LizmapServer)
    assert plugin.version


def test_plugin_plausible_failure(monkeypatch):
    """A failure of the statistics must not prevent the plugin from loading."""

    class BrokenPlausible:
        def __init__(self):
            raise RuntimeError("Broken")

    monkeypatch.setattr(plugin_module, "Plausible", BrokenPlausible)

    server = QgsServer()
    assert LizmapServer(server.serverInterface()) is not None


@pytest.mark.parametrize(
    "name",
    [
        "ExpressionService",
        "LizmapService",
        "LizmapFilter",
        "LizmapAccessControlFilter",
        "GetFeatureInfoFilter",
        "GetLegendGraphicFilter",
        "LegendOnOffFilter",
        "LegendOnOffAccessControl",
    ],
)
def test_plugin_registration_failure(monkeypatch, name):
    """A failure while registering a service or a filter must be re-raised."""

    def broken(*args, **kwargs):
        raise RuntimeError(f"Broken {name}")

    monkeypatch.setattr(plugin_module, name, broken)

    server = QgsServer()
    with pytest.raises(RuntimeError, match=f"Broken {name}"):
        LizmapServer(server.serverInterface())


#
# Legacy API, when pydantic is not installed
#


def test_plugin_api_disabled(monkeypatch):
    """The API must not be registered when the environment variable is missing."""
    import lizmap_server.lizmap_api_handler as api_handler

    monkeypatch.delenv("QGIS_SERVER_LIZMAP_REVEAL_SETTINGS", raising=False)

    # The service registry must not be touched at all
    registries = []
    monkeypatch.setattr(api_handler, "unwrap", lambda value: registries.append(value) or value)

    server = QgsServer()
    register_lizmap_api(server.serverInterface())
    assert registries == []


@pytest.fixture
def restore_lizmap_api(client):
    """The QGIS service registry is global: register the API back afterwards."""
    yield

    from lizmap_server.api.handlers import LizmapApi
    from lizmap_server.tools import unwrap

    iface = client.server.serverInterface()
    unwrap(iface.serviceRegistry()).registerApi(LizmapApi(iface))


def test_plugin_legacy_server_info_handler(monkeypatch, restore_lizmap_api):
    """Without pydantic, only the legacy server info handler is registered."""
    import json

    monkeypatch.setenv("QGIS_SERVER_LIZMAP_REVEAL_SETTINGS", "TRUE")
    monkeypatch.setitem(sys.modules, "pydantic", None)
    monkeypatch.setitem(sys.modules, "pydantic_extra_types", None)
    monkeypatch.delitem(sys.modules, "lizmap_server.legacy_server_info_handler", raising=False)

    server = QgsServer()
    register_lizmap_api(server.serverInterface())

    response = _server_request(server, "/lizmap/server.json")
    assert response.statusCode() == 200

    content = json.loads(bytes(response.body()).decode())
    assert "qgis_server" in content
    assert "plugins" in content["qgis_server"]


def test_plugin_legacy_server_info_handler_metadata():
    """The legacy handler must expose the QGIS API metadata."""
    from qgis.server import QgsServerOgcApi

    from lizmap_server.legacy_server_info_handler import ServerInfoHandler

    handler = ServerInfoHandler()
    assert handler.path().pattern() == "server.json"
    assert handler.summary() == "Server information"
    assert handler.description() == "Get info about the current QGIS server"
    assert handler.operationId() == "server"
    assert handler.linkTitle() == "Handler Lizmap API server info"
    assert handler.linkType() == QgsServerOgcApi.Rel.data


def test_plugin_legacy_server_info_handler_error(monkeypatch):
    """An exception raised while handling the request must be logged and re-raised."""
    import lizmap_server.legacy_server_info_handler as legacy

    from lizmap_server.legacy_server_info_handler import ServerInfoHandler

    def broken(*args, **kwargs):
        raise RuntimeError("Broken")

    monkeypatch.setattr(legacy, "server_info", broken)

    class FakeContext:
        def serverInterface(self):
            return None

    handler = ServerInfoHandler()
    with pytest.raises(RuntimeError, match="Broken"):
        handler.handleRequest(FakeContext())
