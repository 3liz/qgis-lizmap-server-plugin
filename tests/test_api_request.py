"""Tests for the http request delegate."""

import json
import sys

import pytest

from pathlib import Path

from qgis.core import QgsProject
from qgis.server import (
    QgsBufferServerRequest,
    QgsBufferServerResponse,
    QgsServerApiContext,
    QgsServerRequest,
)

from lizmap_server.api import defaults
from lizmap_server.api.errors import HTTPError, HTTPForbidden
from lizmap_server.api.models import Link
from lizmap_server.api.request import HTTPRequestDelegate


def _delegate(client, url="http://localhost:8080/lizmap/api/v1?foo=bar&foo=baz", headers=None):
    request = QgsBufferServerRequest(
        url,
        QgsServerRequest.Method.GetMethod,
        headers if headers is not None else {},
        None,
    )
    response = QgsBufferServerResponse()
    iface = client.server.serverInterface()
    context = QgsServerApiContext("/lizmap", request, response, None, iface)
    return HTTPRequestDelegate(context), response


def test_api_request_properties(client):
    """The delegate must expose the request properties."""
    delegate, _ = _delegate(client)

    assert delegate.method == QgsServerRequest.Method.GetMethod
    assert delegate.request is not None
    assert delegate.path == "/lizmap/api/v1"
    assert delegate.host == "localhost"
    assert delegate.scheme == "http"
    assert delegate.port == ":8080"
    assert delegate.query == {"foo": "bar"}
    assert delegate.query_all == {"foo": ["bar", "baz"]}
    assert delegate.parameter("FOO") == "baz"
    assert delegate.parameter("UNKNOWN", "a default") == "a default"
    assert delegate.serverInterface is not None
    assert delegate.server_context.name == "FCGI"

    # No port in the url
    delegate, _ = _delegate(client, url="http://localhost/lizmap/api/v1")
    assert delegate.port == ""


def test_api_request_headers(client):
    """Headers are read from the request."""
    delegate, _ = _delegate(client, headers={"X-Forwarded-Host": "example.com"})
    assert delegate.header("X-Forwarded-Host") == "example.com"
    assert delegate.header("X-Not-Set") is None


def test_api_request_write(client):
    """The delegate only writes bytes or strings."""
    delegate, response = _delegate(client)

    delegate.write("some text")
    response.flush()
    assert bytes(response.body()) == b"some text"

    with pytest.raises(TypeError, match="write\\(\\) only accepts"):
        delegate.write(42)


def test_api_request_write_json(client):
    """Both json values and json models may be written."""
    delegate, response = _delegate(client)
    delegate.write_json({"foo": "bar"})
    response.flush()
    assert json.loads(bytes(response.body())) == {"foo": "bar"}
    assert response.headers()["Content-Type"] == "application/json"

    delegate, response = _delegate(client)
    delegate.write_json(Link(href="http://localhost/lizmap", rel="self", mime_type="application/json"))
    response.flush()
    assert json.loads(bytes(response.body()))["href"] == "http://localhost/lizmap"


def test_api_request_finish(client):
    """finish() must be called only once."""
    delegate, response = _delegate(client)

    delegate.finish("the end")
    response.flush()
    assert bytes(response.body()) == b"the end"

    # A second call is a no-op
    delegate.finish("ignored")
    response.flush()
    assert bytes(response.body()) == b"the end"


def test_api_request_send_error(client):
    """An error response must be a json document."""
    delegate, response = _delegate(client)

    delegate.send_error(400, reason="Bad request")
    assert response.statusCode() == 400
    assert json.loads(bytes(response.body())) == {"code": 400, "description": "Bad request"}


def test_api_request_send_error_from_exception(client):
    """The reason may be extracted from an HTTP error."""
    delegate, response = _delegate(client)

    try:
        raise HTTPError(404, reason="Not found", log_message="No such project")
    except HTTPError as e:
        delegate.send_error(e.status_code, exc_info=sys.exc_info())

    assert response.statusCode() == 404
    assert json.loads(bytes(response.body())) == {"code": 404, "description": "Not found"}


def test_api_request_send_error_unknown_reason(client):
    """Without any reason, the error is unknown."""
    delegate, response = _delegate(client)

    try:
        raise ValueError("Some error")
    except ValueError:
        delegate.send_error(500, exc_info=sys.exc_info())

    assert json.loads(bytes(response.body())) == {"code": 500, "description": "Unknown"}


def test_api_request_public_url(client):
    """The public url must honour the forwarded headers."""
    delegate, _ = _delegate(client)
    assert delegate.public_url("/foo") == "http://localhost:8080/lizmap/foo"

    delegate, _ = _delegate(client, headers={"X-Forwarded-Host": "example.com"})
    assert delegate.public_url("/foo") == "http://example.com/lizmap/foo"

    delegate, _ = _delegate(
        client,
        headers={"X-Forwarded-Host": "example.com", "X-Forwarded-Proto": "https"},
    )
    assert delegate.public_url("/foo") == "https://example.com/lizmap/foo"

    delegate, _ = _delegate(client, headers={"Forwarded": "host=example.org;proto=https"})
    assert delegate.public_url("/foo") == "https://example.org/lizmap/foo"

    # The 'Forwarded' header may hold unrelated parts
    delegate, _ = _delegate(client, headers={"Forwarded": "for=127.0.0.1;host=example.org"})
    assert delegate.public_url("/foo") == "http://example.org/lizmap/foo"


def test_api_request_public_url_without_host(client):
    """Without any host, the public url is relative."""
    delegate, _ = _delegate(client, url="/lizmap/api/v1")
    assert delegate.host == ""
    assert delegate.public_url("/foo") == "/lizmap/foo"


def test_api_request_send_error_after_finish(client):
    """An error sent after the response is finished must not finish it twice."""
    delegate, response = _delegate(client)

    delegate.finish()
    delegate.send_error(500, reason="Too late")

    assert response.statusCode() == 500


#
# Security tests
#

#
#  Path traversal in the Lizmap API project endpoints
#


TRAVERSALS = (
    "/data/../../etc/passwd",
    "/data/../conftest.py",
    "/data/montpellier/../../../etc/passwd",
    "/data/..",
    "../other",
)


@pytest.mark.parametrize("path", TRAVERSALS)
def test_api_resolve_defaults_project_uri_rejects_traversal(path):
    """A path escaping the search path must not be resolved."""
    with pytest.raises(HTTPForbidden):
        defaults.resolve_project_uri(path)


@pytest.mark.parametrize("path", TRAVERSALS)
def test_api_collect_projects_rejects_traversal(path):
    """No project may be collected from outside the search path."""
    with pytest.raises(HTTPForbidden):
        list(defaults.collect_projects("Test", path))


def test_api_description_cannot_escape_the_root(client, rootdir, tmp_path):
    """A project outside the configured root must not be opened by the API."""
    outside = tmp_path / "outside.qgs"
    assert QgsProject().write(str(outside))

    relative = Path(rootdir).joinpath("data").relative_to(outside, walk_up=True)
    assert str(relative).startswith("..")

    response = client.get(f"/lizmap/api/v1/projects/description?p=/data/{relative}")

    assert response.status_code == 403, response.content


def test_api_layers_cannot_escape_the_root(client, rootdir, tmp_path):
    """The '?p=' parameter of the other endpoints must be checked as well."""
    outside = tmp_path / "outside.qgs"
    assert QgsProject().write(str(outside))

    relative = Path(rootdir).joinpath("data").relative_to(outside, walk_up=True)
    query = f"?p=/data/{relative}"

    assert client.get(f"/lizmap/api/v1/projects/layers/unknown{query}").status_code == 403
    assert client.get(f"/lizmap/api/v1/projects/layouts{query}").status_code == 403


def test_api_list_cannot_escape_the_root(client):
    """The '{PATH:.+}' pattern matches '..': no project may be listed from above."""
    response = client.get("/lizmap/api/v1/projects/list/data/..")

    if response.status_code == 200:
        content = json.loads(response.content.decode("utf-8"))
        assert content["projects"] == [], "Projects listed from outside the search path"
    else:
        assert response.status_code == 403
