"""Tests for the error paths of the LIZMAP service."""

import json

import pytest

from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer, edit
from qgis.PyQt.QtCore import QByteArray
from qgis.server import (
    QgsBufferServerRequest,
    QgsBufferServerResponse,
    QgsServerRequest,
)

from lizmap_server.filter_by_polygon import ALL_FEATURES, NO_FEATURES
from lizmap_server.lizmap_service import LizmapService


class FakeRequestHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, headers=None, params=None):
        self._headers = headers if headers is not None else {}
        self._params = params if params is not None else {}

    def parameter(self, key, default=""):
        return self._params.get(key.upper(), default)

    def requestHeaders(self):
        return self._headers

    def parameterMap(self):
        return self._params


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, iface, handler, config_path):
        self._iface = iface
        self._handler = handler
        self._config_path = str(config_path)

    def requestHandler(self):
        return self._handler

    def serviceRegistry(self):
        return self._iface.serviceRegistry()

    def configFilePath(self):
        return self._config_path


@pytest.fixture
def project():
    """A clean QGIS project."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


@pytest.fixture
def make_service(client, tmp_path):
    """Build a Lizmap service reading a given Lizmap configuration."""

    def _make(config=None, headers=None, params=None):
        qgs = tmp_path.joinpath("project.qgs")
        qgs.write_text("")
        if config is not None:
            tmp_path.joinpath("project.qgs.cfg").write_text(json.dumps(config))

        iface = client.server.serverInterface()
        service = LizmapService(iface)
        service.server_iface = FakeServerInterface(iface, FakeRequestHandler(headers, params), qgs)
        return service

    return _make


def _response_body(response: QgsBufferServerResponse) -> dict:
    response.flush()
    return json.loads(bytes(response.body()).decode())


def _layers():
    polygon = QgsVectorLayer("Polygon?crs=epsg:4326&field=id:integer&field=groups:string", "polygon", "memory")
    with edit(polygon):
        feature = QgsFeature(polygon.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"))
        feature.setAttributes([1, "bob"])
        assert polygon.addFeature(feature)

    points = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer", "points", "memory")
    with edit(points):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POINT(1 1)"))
        feature.setAttributes([1])
        assert points.addFeature(feature)

    return polygon, points


#
# executeRequest
#


def test_lizmap_service_invalid_post_data(client, make_service):
    """A POST body which is not utf-8 must be rejected."""
    service = make_service()

    request = QgsBufferServerRequest(
        "?SERVICE=LIZMAP&REQUEST=GETSERVERSETTINGS",
        QgsServerRequest.Method.PostMethod,
        {},
        QByteArray(b"\xff\xfe invalid"),
    )
    response = QgsBufferServerResponse()
    service.executeRequest(request, response, QgsProject.instance())

    body = _response_body(response)
    assert body["status"] == "fail"
    assert body["message"] == "Invalid POST DATA for 'GETSERVERSETTINGS'"


def test_lizmap_service_internal_error(client, make_service, monkeypatch):
    """An unexpected error must be reported as an internal error."""
    service = make_service()

    def broken(*args, **kwargs):
        raise RuntimeError("Something went wrong")

    monkeypatch.setattr(service, "get_server_settings", broken)

    request = QgsBufferServerRequest(
        "?SERVICE=LIZMAP&REQUEST=GETSERVERSETTINGS",
        QgsServerRequest.Method.GetMethod,
        {},
        None,
    )
    response = QgsBufferServerResponse()
    service.executeRequest(request, response, QgsProject.instance())

    body = _response_body(response)
    assert body["code"] == "Internal server error"
    assert body["message"] == "Internal 'lizmap' service error"


#
# GetSubsetString
#


def test_lizmap_service_unknown_layer(project, make_service):
    """An unknown layer must be rejected."""
    from lizmap_server.exception import ServiceError

    service = make_service()
    response = QgsBufferServerResponse()

    with pytest.raises(ServiceError):
        service.polygon_filter({"LAYER": "unknown"}, response, project)


def test_lizmap_service_override_filter(project, make_service):
    """The override filter header disables any filter."""
    _, points = _layers()
    project.addMapLayer(points)

    service = make_service(headers={"X-Lizmap-Override-Filter": "true"})
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == ALL_FEATURES


def test_lizmap_service_without_config(project, make_service):
    """Without any Lizmap configuration, no filter is applied."""
    _, points = _layers()
    project.addMapLayer(points)

    service = make_service()
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == ALL_FEATURES


def test_lizmap_service_without_layers_config(project, make_service):
    """A configuration without any layer applies no filter."""
    _, points = _layers()
    project.addMapLayer(points)

    service = make_service(config={"options": {}})
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == ALL_FEATURES


def test_lizmap_service_layer_not_in_config(project, make_service):
    """A layer which is not in the configuration is not filtered."""
    _, points = _layers()
    project.addMapLayer(points)

    service = make_service(config={"layers": {"another": {}}})
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == ALL_FEATURES


def test_lizmap_service_invalid_polygon_config(project, make_service):
    """An invalid filter by polygon hides every feature."""
    _, points = _layers()
    project.addMapLayer(points)

    service = make_service(
        config={
            "layers": {"points": {}},
            "filter_by_polygon": {
                "config": {"polygon_layer_id": "unknown_layer", "group_field": "groups"},
                "layers": [{"layer": points.id(), "primary_key": "id"}],
            },
        },
    )
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == NO_FEATURES


def test_lizmap_service_polygon_error(project, make_service, monkeypatch):
    """An error while reading the filter by polygon hides every feature."""
    import lizmap_server.lizmap_service as module

    def broken(*args, **kwargs):
        raise RuntimeError("Broken")

    monkeypatch.setattr(module, "FilterByPolygon", broken)

    _, points = _layers()
    project.addMapLayer(points)

    service = make_service(config={"layers": {"points": {}}})
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == NO_FEATURES


@pytest.mark.parametrize(
    "filter_type,expected",
    [
        ("SQL", '"id" IN ( 1 )'),
        ("SAFESQL", '"id" IN ( 1 )'),
        ("EXPRESSION", "geom_from_wkt"),
        ("", '"id" IN ( 1 )'),
    ],
)
def test_lizmap_service_filter_types(project, make_service, filter_type, expected):
    """Each filter type generates its own filter."""
    polygon, points = _layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    service = make_service(
        config={
            "layers": {"points": {}},
            "filter_by_polygon": {
                "config": {"polygon_layer_id": polygon.id(), "group_field": "groups"},
                "layers": [
                    {
                        "layer": points.id(),
                        "primary_key": "id",
                        "spatial_relationship": "intersects",
                        "filter_mode": "display_and_editing",
                    },
                ],
            },
        },
        headers={"X-Lizmap-User-Groups": "bob"},
    )
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points", "FILTER_TYPE": filter_type}, response, project)

    assert expected in _response_body(response)["filter"]


def test_lizmap_service_filter_by_user(project, make_service):
    """The filter may be done on the user login instead of the groups."""
    polygon, points = _layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    service = make_service(
        config={
            "layers": {"points": {}},
            "filter_by_polygon": {
                "config": {
                    "polygon_layer_id": polygon.id(),
                    "group_field": "groups",
                    "filter_by_user": True,
                },
                "layers": [
                    {
                        "layer": points.id(),
                        "primary_key": "id",
                        "spatial_relationship": "intersects",
                        "filter_mode": "display_and_editing",
                    },
                ],
            },
        },
        headers={"X-Lizmap-User": "bob"},
    )
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    assert _response_body(response)["filter"] == '"id" IN ( 1 )'


def test_lizmap_service_layer_not_filtered(project, make_service):
    """A layer which is not in the filter by polygon has no response."""
    polygon, points = _layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    service = make_service(
        config={
            "layers": {"points": {}},
            "filter_by_polygon": {
                "config": {"polygon_layer_id": polygon.id(), "group_field": "groups"},
                "layers": [{"layer": "another_layer_id", "primary_key": "id"}],
            },
        },
        headers={"X-Lizmap-User-Groups": "bob"},
    )
    response = QgsBufferServerResponse()
    service.polygon_filter({"LAYER": "points"}, response, project)

    # Nothing has been written: QGIS Server handles the request
    response.flush()
    assert bytes(response.body()) == b""
