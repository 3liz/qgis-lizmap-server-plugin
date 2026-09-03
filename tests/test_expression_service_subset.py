"""Tests for the ReplaceExpressionText request with an extra subset string.

The extra subset string comes from the registered access control plugins: the
server interface is stubbed to provide one.
"""

import json

import pytest

from qgis.core import QgsProject, QgsVectorLayer
from qgis.server import QgsBufferServerResponse

from lizmap_server.exception import ExpressionServiceError
from lizmap_server.expression_service.request_replaceexpressiontext import replace_expression_text

FEATURE = '{"type": "Feature", "geometry": null, "properties": {"NAME_1": "Bretagne"}}'


class FakeAccessControls:
    """Minimal duck typing of a QgsAccessControlFilter chain."""

    def __init__(self, subset_string):
        self._subset_string = subset_string

    def extraSubsetString(self, layer):
        return self._subset_string


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, subset_string):
        self._access_controls = FakeAccessControls(subset_string)

    def accessControls(self):
        return self._access_controls


@pytest.fixture
def project(rootdir):
    """A project with the 'france_parts' layer."""
    instance = QgsProject.instance()
    instance.clear()

    layer = QgsVectorLayer(
        str(rootdir.joinpath("data/france_parts/france_parts.shp")),
        "france_parts",
        "ogr",
    )
    assert layer.isValid()
    instance.addMapLayer(layer)

    yield instance
    instance.clear()


@pytest.fixture
def iface():
    """A server interface providing an extra subset string."""
    return FakeServerInterface("\"NAME_1\" = 'Bretagne'")


def _params(**kwargs):
    params = {"LAYER": "france_parts", "STRINGS": '["[% 1 + 1 %]"]'}
    params.update(kwargs)
    return params


def _body(response: QgsBufferServerResponse) -> dict:
    response.flush()
    return json.loads(bytes(response.body()).decode())


def test_replace_without_feature(project, iface):
    """The subset string must be restored after the request."""
    layer = project.mapLayersByName("france_parts")[0]

    response = QgsBufferServerResponse()
    replace_expression_text(_params(), response, project, iface)

    assert _body(response)["results"] == [{"0": "2"}]
    # The subset string of the layer has been restored
    assert layer.subsetString() == ""


def test_replace_with_features(project, iface):
    """The subset string must be restored after the request."""
    layer = project.mapLayersByName("france_parts")[0]

    response = QgsBufferServerResponse()
    replace_expression_text(_params(FEATURE=FEATURE), response, project, iface)

    assert len(_body(response)["results"]) == 1
    assert layer.subsetString() == ""


def test_replace_malformed_features(project, iface):
    """A malformed FEATURES must restore the subset string."""
    layer = project.mapLayersByName("france_parts")[0]

    response = QgsBufferServerResponse()
    with pytest.raises(ExpressionServiceError):
        replace_expression_text(_params(FEATURES="{not json}"), response, project, iface)

    assert layer.subsetString() == ""


def test_replace_features_not_a_list(project, iface):
    """FEATURES which is not a list must restore the subset string."""
    layer = project.mapLayersByName("france_parts")[0]

    response = QgsBufferServerResponse()
    with pytest.raises(ExpressionServiceError):
        replace_expression_text(_params(FEATURES='{"type": "Feature"}'), response, project, iface)

    assert layer.subsetString() == ""


def test_replace_features_not_a_feature(project, iface):
    """A feature with a wrong type must restore the subset string."""
    layer = project.mapLayersByName("france_parts")[0]

    response = QgsBufferServerResponse()
    with pytest.raises(ExpressionServiceError):
        replace_expression_text(
            _params(FEATURES='[{"type": "FeatureCollection"}]'), response, project, iface
        )

    assert layer.subsetString() == ""


def test_replace_no_feature_parsed(project, iface, monkeypatch):
    """Features which cannot be parsed must restore the subset string."""
    from lizmap_server.expression_service import request_replaceexpressiontext as module

    monkeypatch.setattr(module, "QgsJsonUtils_stringToFeatureList", lambda *args: None)

    layer = project.mapLayersByName("france_parts")[0]

    response = QgsBufferServerResponse()
    with pytest.raises(ExpressionServiceError):
        replace_expression_text(_params(FEATURE=FEATURE), response, project, iface)

    assert layer.subsetString() == ""


def test_replace_all_features(project, iface):
    """All the features of the layer may be used, with the extra subset string."""
    response = QgsBufferServerResponse()
    replace_expression_text(_params(FEATURES="ALL"), response, project, iface)

    # Only the feature matching the extra subset string
    assert len(_body(response)["results"]) == 1
