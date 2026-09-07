"""Tests for the request helpers of ``lizmap_server.core``."""

import json

from lizmap_server.core import (
    find_layer,
    find_vector_layer,
    find_vector_layer_from_params,
    get_lizmap_config,
    get_lizmap_groups,
    get_lizmap_layer_login_filter,
    get_lizmap_override_filter,
    get_lizmap_user_login,
    get_server_fid,
    is_editing_context,
)

from qgis.core import Qgis, QgsFeature, QgsFields, QgsField
from qgis.PyQt.QtCore import QMetaType


class FakeHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, headers=None, params=None):
        self._headers = headers if headers is not None else {}
        self._params = params if params is not None else {}

    def requestHeaders(self):
        return self._headers

    def parameterMap(self):
        return self._params


def test_core_groups_from_parameters():
    """Groups must be read from the parameters when no header is provided."""
    assert get_lizmap_groups(FakeHandler()) == ()

    handler = FakeHandler(params={"LIZMAP_USER_GROUPS": "group_a, group_b"})
    assert get_lizmap_groups(handler) == ("group_a", "group_b")

    handler = FakeHandler(headers={"X-Lizmap-User-Groups": "group_a"}, params={"LIZMAP_USER_GROUPS": "b"})
    assert get_lizmap_groups(handler) == ("group_a",)

    # Headers without the Lizmap key, fallback on parameters
    handler = FakeHandler(headers={"Accept": "*/*"}, params={"LIZMAP_USER_GROUPS": "group_c"})
    assert get_lizmap_groups(handler) == ("group_c",)


def test_core_user_login_from_parameters():
    """The user login must be read from the parameters when no header is provided."""
    assert get_lizmap_user_login(FakeHandler()) == ""

    handler = FakeHandler(params={"LIZMAP_USER": "Bob"})
    assert get_lizmap_user_login(handler) == "Bob"

    handler = FakeHandler(headers={"X-Lizmap-User": "Alice"}, params={"LIZMAP_USER": "Bob"})
    assert get_lizmap_user_login(handler) == "Alice"


def test_core_override_filter():
    """The override filter must be read from headers and parameters."""
    assert get_lizmap_override_filter(FakeHandler()) is False

    handler = FakeHandler(headers={"X-Lizmap-Override-Filter": "yes"})
    assert get_lizmap_override_filter(handler) is True

    handler = FakeHandler(params={"LIZMAP_OVERRIDE_FILTER": "true"})
    assert get_lizmap_override_filter(handler) is True

    handler = FakeHandler(params={"FOO": "bar"})
    assert get_lizmap_override_filter(handler) is False


def test_core_editing_context():
    """The editing context must be read from headers and parameters."""
    assert is_editing_context(FakeHandler()) is False

    handler = FakeHandler(headers={"X-Lizmap-Edition-Context": "true"})
    assert is_editing_context(handler) is True

    handler = FakeHandler(params={"LIZMAP_EDITION_CONTEXT": "true"})
    assert is_editing_context(handler) is True

    handler = FakeHandler(params={"FOO": "bar"})
    assert is_editing_context(handler) is False


def test_core_server_fid():
    """The server feature id is built from the primary key attributes."""
    fields = QgsFields()
    fields.append(QgsField("id", QMetaType.Type.Int))
    fields.append(QgsField("code", QMetaType.Type.QString))

    feature = QgsFeature(fields)
    feature.setId(12)
    feature.setAttributes([5, "AB"])

    assert get_server_fid(feature, []) == "12"
    assert get_server_fid(feature, ["id"]) == "5"
    assert get_server_fid(feature, ["id", "code"]) == "5@@AB"


def test_core_find_layer(client):
    """Layers must be found by name, short name and id."""
    project = client.get_project("france_parts.qgs")
    layer = find_vector_layer("france_parts", project)
    assert layer is not None

    # By layer id
    assert find_layer(layer.id(), project) is layer

    # By short name
    if Qgis.versionInt() < 33800:
        layer.setShortName("a_short_name")
    else:
        layer.serverProperties().setShortName("a_short_name")
    assert find_layer("a_short_name", project) is layer

    # Unknown layer
    assert find_layer("does_not_exist", project) is None
    assert find_vector_layer("does_not_exist", project) is None

    # From the request parameters
    assert find_vector_layer_from_params({}, project) is None
    assert find_vector_layer_from_params({"LAYER": "france_parts"}, project) is layer
    assert find_vector_layer_from_params({"layer": "france_parts"}, project) is layer


def test_core_lizmap_config_not_json(tmp_path):
    """A malformed CFG file must be reported as an empty configuration."""
    project = tmp_path.joinpath("project.qgs")
    project.write_text("")

    config = tmp_path.joinpath("project.qgs.cfg")

    config.write_text("this is not json")
    assert get_lizmap_config(str(project)) is None

    # An empty (but valid) json configuration
    config.write_text(json.dumps({}))
    assert get_lizmap_config(str(project)) is None


def test_core_login_filter_not_a_dict():
    """A login filter which is not a dictionary must be discarded."""
    config = {"loginFilteredLayers": {"a_layer": "not a dict"}}
    assert get_lizmap_layer_login_filter(config, "a_layer") is None
