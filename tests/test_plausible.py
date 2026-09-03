"""Tests for the anonymous statistics."""

import pytest

from qgis.PyQt.QtNetwork import QNetworkReply

from lizmap_server import plausible as plausible_module
from lizmap_server.plausible import ENV_SKIP_STATS, Plausible


class FakeReply:
    def __init__(self, error=QNetworkReply.NetworkError.NoError):
        self._error = error

    def error(self):
        return self._error


class FakeNetworkAccessManager:
    """Minimal stand-in for the QGIS network access manager."""

    last_request = None
    last_data = None
    reply = FakeReply()

    @classmethod
    def instance(cls):
        return cls()

    def post(self, request, data):
        FakeNetworkAccessManager.last_request = request
        FakeNetworkAccessManager.last_data = bytes(data).decode()
        return FakeNetworkAccessManager.reply


@pytest.fixture
def network(monkeypatch):
    """Never send a real request to the statistics server."""
    FakeNetworkAccessManager.last_request = None
    FakeNetworkAccessManager.last_data = None
    FakeNetworkAccessManager.reply = FakeReply()
    monkeypatch.setattr(plausible_module, "QgsNetworkAccessManager", FakeNetworkAccessManager)
    return FakeNetworkAccessManager


def test_plausible_disabled_by_environment(monkeypatch, network):
    """The statistics must not be sent when disabled by the environment."""
    monkeypatch.setenv(ENV_SKIP_STATS, "yes")
    assert Plausible().request_stat_event() is False
    assert network.last_data is None


def test_plausible_disabled_on_ci(monkeypatch, network):
    """The statistics must not be sent on a CI."""
    monkeypatch.delenv(ENV_SKIP_STATS, raising=False)
    monkeypatch.setenv("CI", "True")
    assert Plausible().request_stat_event() is False
    assert network.last_data is None


def test_plausible_send_event(monkeypatch, network):
    """The event must be sent once per hour at most."""
    import json

    monkeypatch.delenv(ENV_SKIP_STATS, raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("QGIS_SERVER_APPLICATION_NAME", raising=False)
    # A released version of the plugin
    monkeypatch.setattr(plausible_module, "version", lambda: "2.15.4")

    plausible = Plausible()
    assert plausible.request_stat_event() is True
    assert plausible.previous_date is not None

    data = json.loads(network.last_data)
    assert data["name"] == "lizmap-server"
    assert data["domain"] == plausible_module.PLAUSIBLE_DOMAIN_PROD
    assert data["url"] == plausible_module.PLAUSIBLE_URL_PROD
    assert data["props"]["plugin-version"] == "2.15.4"
    assert data["props"]["os-name"]
    assert data["props"]["qgis-version-branch"]
    assert data["props"]["python-version-branch"]

    # Not twice in the same hour
    network.last_data = None
    assert plausible.request_stat_event() is False
    assert network.last_data is None


def test_plausible_send_event_failure(monkeypatch, network):
    """A failure while sending the event must be reported."""
    monkeypatch.delenv(ENV_SKIP_STATS, raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(Plausible, "_send_stat_event", staticmethod(lambda: False))

    plausible = Plausible()
    assert plausible.request_stat_event() is False
    assert plausible.previous_date is None


def test_plausible_development_version(monkeypatch, network):
    """A development version of the plugin uses the test instance."""
    import json

    monkeypatch.delenv("QGIS_SERVER_APPLICATION_NAME", raising=False)
    monkeypatch.setattr(plausible_module, "version", lambda: "dev")

    assert Plausible._send_stat_event() is True

    data = json.loads(network.last_data)
    assert data["url"] == plausible_module.PLAUSIBLE_URL_TEST
    assert data["domain"] == plausible_module.PLAUSIBLE_DOMAIN_TEST
    assert data["props"]["plugin-version"] == "dev"


@pytest.mark.parametrize(
    "error",
    [QNetworkReply.NetworkError.NoError, QNetworkReply.NetworkError.HostNotFoundError],
)
def test_plausible_lizcloud(monkeypatch, network, error):
    """On Lizcloud, the domain is read from the environment and the reply is logged."""
    import json

    monkeypatch.setenv("QGIS_SERVER_APPLICATION_NAME", "Lizcloud instance")
    monkeypatch.setenv("QGIS_SERVER_PLAUSIBLE_DOMAIN_NAME", "example.com")
    network.reply = FakeReply(error)

    assert Plausible._send_stat_event() is True

    data = json.loads(network.last_data)
    assert data["domain"] == "example.com"
