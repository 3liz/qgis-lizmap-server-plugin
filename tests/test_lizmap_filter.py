import logging

LOGGER = logging.getLogger("server")


def test_no_lizmap_config(client):
    """
    Test Filter response with a project without
    lizmap config
    """
    projectfile = "france_parts.qgs"

    # Make a request without LIZMAP_USER_GROUPS
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 1 group
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs&LIZMAP_USER_GROUPS=test1"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0


def test_no_acl(client):
    """
    Test Filter response with a project with
    a lizmap config without acl
    """
    projectfile = "france_parts_liz.qgs"

    # Make a request without LIZMAP_USER_GROUPS
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts_liz.qgs"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 1 group
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs&LIZMAP_USER_GROUPS=test1"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0


def test_acl(client):
    """
    Test Filter response with a project wit
    a lizmap config with acl
    """
    projectfile = "france_parts_liz_acl.qgs"

    # Make a request without LIZMAP_USER_GROUPS
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts_liz_acl.qgs"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 1 group not authorized
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs&LIZMAP_USER_GROUPS=test1"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 403

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 1 group authorized
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs&LIZMAP_USER_GROUPS=test2"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 2 groups which 1 is authorized
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs&LIZMAP_USER_GROUPS=test1,test2"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with anonymous group not authorized
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts.qgs&LIZMAP_USER_GROUPS="
    rv = client.get(qs, projectfile)
    assert rv.status_code == 403

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0


def test_acl_headers(client):
    """
    Test Filter response with a project wit
    a lizmap config with acl and Lizmap groups in request headers
    """
    projectfile = "france_parts_liz_acl.qgs"

    # Make a request without LIZMAP_USER_GROUPS
    qs = "?SERVICE=WMS&REQUEST=GetCapabilities&MAP=france_parts_liz_acl.qgs"
    rv = client.get(qs, projectfile)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 1 group not authorized
    headers = {"X-Lizmap-User-Groups": "test1"}
    rv = client.get(qs, projectfile, headers)
    assert rv.status_code == 403

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 1 group authorized
    headers = {"X-Lizmap-User-Groups": "test2"}
    rv = client.get(qs, projectfile, headers)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with 2 groups which 1 is authorized
    headers = {"X-Lizmap-User-Groups": "test1,test2"}
    rv = client.get(qs, projectfile, headers)
    assert rv.status_code == 200

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0

    # Make a request with LIZMAP_USER_GROUPS with anonymous group not authorized
    headers = {"X-Lizmap-User-Groups": ""}
    rv = client.get(qs, projectfile, headers)
    assert rv.status_code == 403

    assert rv.headers.get("Content-Type", "").find("text/xml") == 0


#
# Configuration edge cases
#


class FakeRequestHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, headers=None, params=None):
        self._headers = headers if headers is not None else {}
        self._params = params if params is not None else {}
        self.exception = None

    def requestHeaders(self):
        return self._headers

    def parameterMap(self):
        return self._params

    def setServiceException(self, exception):
        self.exception = exception


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, handler, config_path=""):
        self._handler = handler
        self._config_path = str(config_path)

    def requestHandler(self):
        return self._handler

    def configFilePath(self):
        return self._config_path


def _make_filter(client, tmp_path, config=None, headers=None):
    import json

    from lizmap_server.lizmap_filter import LizmapFilter

    qgs = tmp_path.joinpath("project.qgs")
    qgs.write_text("")
    if config is not None:
        tmp_path.joinpath("project.qgs.cfg").write_text(json.dumps(config))

    handler = FakeRequestHandler(headers)
    lizmap_filter = LizmapFilter(client.server.serverInterface())
    lizmap_filter.iface = FakeServerInterface(handler, qgs)
    return lizmap_filter, handler


def test_lizmap_filter_config_without_options(client, tmp_path):
    """A configuration without any option lets the request go through."""
    lizmap_filter, handler = _make_filter(
        client,
        tmp_path,
        config={"layers": {}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    assert lizmap_filter.requestReady() is None
    assert handler.exception is None


def test_lizmap_filter_config_without_acl(client, tmp_path):
    """A configuration without any acl lets the request go through."""
    lizmap_filter, handler = _make_filter(
        client,
        tmp_path,
        config={"options": {}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    assert lizmap_filter.requestReady() is None
    assert handler.exception is None


def test_lizmap_filter_forbidden(client, tmp_path):
    """A group which is not in the acl is forbidden."""
    lizmap_filter, handler = _make_filter(
        client,
        tmp_path,
        config={"options": {"acl": ["admins"]}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    lizmap_filter.requestReady()
    assert handler.exception is not None

    # A group in the acl is allowed
    lizmap_filter, handler = _make_filter(
        client,
        tmp_path,
        config={"options": {"acl": ["admins"]}},
        headers={"X-Lizmap-User-Groups": "admins"},
    )
    lizmap_filter.requestReady()
    assert handler.exception is None


def test_lizmap_filter_error(client, tmp_path):
    """An error must be logged and swallowed."""
    from lizmap_server.lizmap_filter import LizmapFilter

    class BrokenHandler:
        def requestHeaders(self):
            raise RuntimeError("Broken")

    lizmap_filter = LizmapFilter(client.server.serverInterface())
    lizmap_filter.iface = FakeServerInterface(BrokenHandler())

    assert lizmap_filter.requestReady() is None
