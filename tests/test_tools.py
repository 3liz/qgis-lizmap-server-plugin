"""Tests for the small utility modules: tools, logger and exception."""

import pytest

from lizmap_server import logger
from lizmap_server.exception import LizmapFilterException, ServiceError
from lizmap_server.tools import (
    check_environment_variable,
    plugin_metadata,
    plugin_path,
    to_bool,
    unwrap,
    version,
)


def test_tools_plugin_metadata():
    """The plugin metadata must be readable from the package resources."""
    assert plugin_path("metadata.txt").exists()
    assert plugin_metadata()["general"]["version"] == version()


def test_tools_check_environment_variable(monkeypatch):
    """The Lizmap API must be reported as disabled when the env variable is missing."""
    monkeypatch.setenv("QGIS_SERVER_LIZMAP_REVEAL_SETTINGS", "TRUE")
    assert check_environment_variable() is True

    monkeypatch.delenv("QGIS_SERVER_LIZMAP_REVEAL_SETTINGS")
    assert check_environment_variable() is False

    monkeypatch.setenv("QGIS_SERVER_LIZMAP_REVEAL_SETTINGS", "no")
    assert check_environment_variable() is False


def test_tools_unwrap():
    """unwrap() must reject None values."""
    obj = object()
    assert unwrap(obj) is obj
    assert to_bool(unwrap("yes")) is True

    with pytest.raises(AssertionError):
        unwrap(None)


def test_logger_log_exception():
    """Logging an exception must not raise."""
    try:
        raise ValueError("Some error")
    except ValueError as e:
        logger.log_exception(e)


def test_logger_profiling(monkeypatch):
    """The profiling decorator must run the function in both modes."""

    @logger.profiling
    def _func(value):
        return value * 2

    assert _func(2) == 4

    monkeypatch.setattr(logger, "PROFILE", True)
    assert _func(3) == 6


def test_exception_service_error():
    """The service error must build a proper message."""
    error = ServiceError("Bad", "A message", 400)
    assert error.code == "Bad"
    assert error.response_code == 400
    assert str(error) == "A message"


def test_exception_filter_response():
    """The filter exception must format a XML response."""
    exception = LizmapFilterException("Bad", "A message")
    body, content_type = exception.formatResponse()
    assert content_type == "text/xml; charset=utf-8"
    assert b"locator" not in bytes(body)

    exception = LizmapFilterException("Bad", "A message", locator="Here")
    body, _ = exception.formatResponse()
    assert b'locator="Here"' in bytes(body)
