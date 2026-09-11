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

from pathlib import Path

import pytest


from lizmap_server.core import (
    get_lizmap_groups,
    get_lizmap_override_filter,
    get_lizmap_user_login,
    is_editing_context,
)


#
# Fakes
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


HEADERS_ONLY_ENV = "QGIS_SERVER_LIZMAP_IDENTITY_HEADERS_ONLY"


@pytest.fixture
def headers_only(monkeypatch):
    """Enable the 'identity from headers only' mode."""
    monkeypatch.setenv(HEADERS_ONLY_ENV, "TRUE")


@pytest.mark.xfail
def test_groups_from_parameters_are_ignored(headers_only):
    """`LIZMAP_USER_GROUPS` must be ignored in headers only mode."""
    handler = FakeRequestHandler(params={"LIZMAP_USER_GROUPS": "admins"})
    assert get_lizmap_groups(handler) == ()

    # The header is still honoured
    handler = FakeRequestHandler(
        params={"LIZMAP_USER_GROUPS": "admins"},
        headers={"X-Lizmap-User-Groups": "users"},
    )
    assert get_lizmap_groups(handler) == ("users",)


#
# Thes tests must fails because lizmap allow for identity for
# unauthenticated request parameters
#
# This is ok as long lizmap-server is behind LWC, but environment gated-options
# should be set for accept identity from headers only
#


@pytest.mark.xfail
def test_login_from_parameters_is_ignored(headers_only):
    """`LIZMAP_USER` must be ignored in headers only mode."""
    handler = FakeRequestHandler(params={"LIZMAP_USER": "admin"})
    assert get_lizmap_user_login(handler) == ""

    handler = FakeRequestHandler(
        params={"LIZMAP_USER": "admin"},
        headers={"X-Lizmap-User": "user"},
    )
    assert get_lizmap_user_login(handler) == "user"


@pytest.mark.xfail
def test_override_filter_from_parameters_is_ignored(headers_only):
    """`LIZMAP_OVERRIDE_FILTER` disables all row level filtering: parameters must not set it."""
    handler = FakeRequestHandler(params={"LIZMAP_OVERRIDE_FILTER": "1"})
    assert get_lizmap_override_filter(handler) is False

    handler = FakeRequestHandler(
        params={"LIZMAP_OVERRIDE_FILTER": "0"},
        headers={"X-Lizmap-Override-Filter": "1"},
    )
    assert get_lizmap_override_filter(handler) is True


@pytest.mark.xfail
def test_edition_context_from_parameters_is_ignored(headers_only):
    """`LIZMAP_EDITION_CONTEXT` selects the editing filters: parameters must not set it."""
    handler = FakeRequestHandler(params={"LIZMAP_EDITION_CONTEXT": "1"})
    assert is_editing_context(handler) is False

    handler = FakeRequestHandler(
        params={"LIZMAP_EDITION_CONTEXT": "0"},
        headers={"X-Lizmap-Edition-Context": "1"},
    )
    assert is_editing_context(handler) is True


@pytest.mark.xfail
def test_parameters_are_still_accepted_by_default():
    """Without the environment variable, the documented parameters keep working."""
    handler = FakeRequestHandler(params={"LIZMAP_USER_GROUPS": "admins"})
    assert get_lizmap_groups(handler) == ("admins",)

    handler = FakeRequestHandler(params={"LIZMAP_OVERRIDE_FILTER": "1"})
    assert get_lizmap_override_filter(handler) is True


@pytest.mark.xfail
def test_trust_boundary_is_documented(rootdir):
    """The README must state the prerequisite of the parameter based identity.

    The identity parameters are only safe while QGIS Server is unreachable
    except through Lizmap Web Client, and while LWC strips them from the
    client supplied OWS query strings.
    """
    readme = Path(rootdir).parent.joinpath("README.md").read_text(encoding="utf-8").lower()

    assert "trust boundary" in readme, "The README must have a 'trust boundary' section"
    assert "lizmap_override_filter" in readme
    assert "lizmap_user_groups" in readme
