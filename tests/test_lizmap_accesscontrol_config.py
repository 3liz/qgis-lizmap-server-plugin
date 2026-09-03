"""Tests for the Lizmap access control rules driven by the CFG file."""

import itertools
import json
import pytest

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from lizmap_server.filter_by_polygon import ALL_FEATURES, NO_FEATURES, FilterType
from lizmap_server.lizmap_accesscontrol import LizmapAccessControlFilter
from lizmap_server.tos_definitions import (
    BING_KEY,
    GOOGLE_KEY,
    strict_tos_check_key,
)


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

    def accessControls(self):
        return self._iface.accessControls()

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
def make_acl(client, tmp_path):
    """Build an access control filter reading a given Lizmap configuration."""

    # Each call gets its own directory: the Lizmap config is cached on
    # (path, mtime), so rewriting a single path may return a stale config.
    #
    # This will trick the modified time based config cache. In some situation
    # the same modified timestamp is returned for two consecutive write !!!!
    count = itertools.count()

    def _make(config=None, headers=None, params=None):
        root = tmp_path.joinpath(f"acl-{next(count)}")
        root.mkdir(exist_ok=True)
        qgs = root.joinpath("project.qgs")
        qgs.write_text("")
        if config is not None:
            root.joinpath("project.qgs.cfg").write_text(json.dumps(config))

        iface = client.server.serverInterface()
        acl = LizmapAccessControlFilter(iface)
        acl.iface = FakeServerInterface(iface, FakeRequestHandler(headers, params), qgs)
        return acl

    return _make



def _layer(name="points"):
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer&field=user:string", name, "memory")
    assert layer.isValid()
    return layer


#
# layerPermissions
#


def test_acl_invalid_layer(project, make_acl):
    """An invalid layer is not readable outside of WMS."""
    layer = QgsVectorLayer("Point?crs=epsg:4326", "invalid", "unknown_provider")
    assert not layer.isValid()

    acl = make_acl(params={"SERVICE": "WFS"})
    rights = acl.layerPermissions(layer)

    assert not rights.canRead
    assert not rights.canInsert
    assert not rights.canUpdate
    assert not rights.canDelete


def test_acl_no_config(project, make_acl):
    """Without any Lizmap configuration, the default rights are applied."""
    layer = _layer()
    acl = make_acl(headers={"X-Lizmap-User-Groups": "test1"})

    rights = acl.layerPermissions(layer)
    assert rights.canRead


def test_acl_no_group(project, make_acl):
    """Without any group, the default rights are applied."""
    layer = _layer()
    acl = make_acl(config={"layers": {"points": {}}})

    rights = acl.layerPermissions(layer)
    assert rights.canRead


def test_acl_wfs_getfeature(project, make_acl):
    """The filter expression cache is resolved for a WFS GetFeature."""
    layer = _layer()
    project.addMapLayer(layer)

    acl = make_acl(
        config={"options": {}, "layers": {"points": {}}},
        headers={"X-Lizmap-User-Groups": "test1"},
        params={"SERVICE": "WFS", "REQUEST": "GETFEATURE"},
    )
    rights = acl.layerPermissions(layer)
    assert rights.canRead


def test_acl_no_layers_in_config(project, make_acl):
    """A configuration without any layer applies the default rights."""
    layer = _layer()
    acl = make_acl(config={"options": {}}, headers={"X-Lizmap-User-Groups": "test1"})

    rights = acl.layerPermissions(layer)
    assert rights.canRead


def test_acl_no_edition_layers(project, make_acl):
    """Without any edition layer, the edition rights are reset."""
    layer = _layer()
    acl = make_acl(
        config={"options": {}, "layers": {"points": {}}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert rights.canRead
    assert not rights.canInsert
    assert not rights.canUpdate
    assert not rights.canDelete


def test_acl_edition_layer_not_configured(project, make_acl):
    """A layer without its own edition config has no edition right."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "editionLayers": {"another_layer_id": {"capabilities": {}}},
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert not rights.canInsert
    assert not rights.canUpdate
    assert not rights.canDelete


def test_acl_edition_capabilities(project, make_acl):
    """The edition rights are read from the capabilities."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "editionLayers": {
                layer.id(): {
                    "acl": "test1, test2",
                    "capabilities": {
                        "createFeature": "True",
                        "deleteFeature": "False",
                        "modifyAttribute": "False",
                        "modifyGeometry": "True",
                    },
                },
            },
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert rights.canInsert
    assert not rights.canDelete
    assert rights.canUpdate


def test_acl_edition_not_allowed_group(project, make_acl):
    """A group which is not in the acl cannot edit the layer."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "editionLayers": {
                layer.id(): {
                    "acl": "admins",
                    "capabilities": {
                        "createFeature": "True",
                        "deleteFeature": "True",
                        "modifyAttribute": "True",
                        "modifyGeometry": "True",
                    },
                },
            },
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert not rights.canInsert
    assert not rights.canUpdate
    assert not rights.canDelete


def test_acl_edition_without_acl(project, make_acl):
    """Without any acl, everybody may edit the layer."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "editionLayers": {
                layer.id(): {
                    "capabilities": {
                        "createFeature": "True",
                        "deleteFeature": "True",
                        "modifyAttribute": "True",
                        "modifyGeometry": "True",
                    },
                },
            },
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert rights.canInsert
    assert rights.canUpdate
    assert rights.canDelete


def test_acl_edition_without_capabilities(project, make_acl):
    """Without any capability, the edition rights are reset."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "editionLayers": {layer.id(): {"acl": "test1"}},
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert not rights.canInsert
    assert not rights.canUpdate
    assert not rights.canDelete


def test_acl_layer_not_in_config(project, make_acl):
    """A layer which is not in the configuration keeps the default rights."""
    layer = _layer()
    acl = make_acl(
        config={"options": {}, "layers": {"another": {"group_visibility": ["admins"]}}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )

    rights = acl.layerPermissions(layer)
    assert rights.canRead


def test_acl_group_visibility(project, make_acl):
    """The group visibility hides the layer for the other groups."""
    layer = _layer()

    acl = make_acl(
        config={"options": {}, "layers": {"points": {"group_visibility": ["admins"]}}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )
    rights = acl.layerPermissions(layer)
    assert not rights.canRead

    acl = make_acl(
        config={"options": {}, "layers": {"points": {"group_visibility": ["admins"]}}},
        headers={"X-Lizmap-User-Groups": "admins"},
    )
    rights = acl.layerPermissions(layer)
    assert rights.canRead


#
# External providers, terms of service
#


@pytest.mark.parametrize(
    "provider,source",
    [
        (GOOGLE_KEY, "type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds"),
        (BING_KEY, "type=xyz&url=https://ecn.t3.tiles.virtualearth.net/tiles/a"),
    ],
)
def test_acl_tos_without_config(project, make_acl, monkeypatch, provider, source):
    """Without any Lizmap config, the strict TOS check applies."""
    layer = QgsRasterLayer(source, "external", "wms")
    assert layer.isValid()

    monkeypatch.setenv(strict_tos_check_key(provider), "TRUE")
    acl = make_acl(params={"SERVICE": "WMS"})
    rights = acl.layerPermissions(layer)
    assert not rights.canRead

    monkeypatch.setenv(strict_tos_check_key(provider), "FALSE")
    acl = make_acl(params={"SERVICE": "WMS"})
    rights = acl.layerPermissions(layer)
    assert rights.canRead


@pytest.mark.parametrize(
    "provider,source,key",
    [
        (GOOGLE_KEY, "type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds", "googleKey"),
        (BING_KEY, "type=xyz&url=https://ecn.t3.tiles.virtualearth.net/tiles/a", "bingKey"),
    ],
)
def test_acl_tos_without_api_key(project, make_acl, monkeypatch, provider, source, key):
    """A licensed layer without any API key is discarded."""
    layer = QgsRasterLayer(source, "external", "wms")
    assert layer.isValid()
    monkeypatch.setenv(strict_tos_check_key(provider), "TRUE")

    acl = make_acl(
        config={"options": {}, "layers": {"external": {}}},
        params={"SERVICE": "WMS"},
    )
    rights = acl.layerPermissions(layer)
    assert not rights.canRead

    # With an API key the layer is kept
    acl = make_acl(
        config={"options": {key: "an-api-key"}, "layers": {"external": {}}},
        params={"SERVICE": "WMS"},
    )
    rights = acl.layerPermissions(layer)
    assert rights.canRead


#
# cacheKey
#


def test_acl_cache_key(project, make_acl):
    """The cache key depends on the group visibility."""
    # No group at all
    acl = make_acl()
    assert acl.cacheKey() == ""

    # No configuration
    acl = make_acl(headers={"X-Lizmap-User-Groups": "test1"})
    assert acl.cacheKey() == ""

    # No layer in the configuration
    acl = make_acl(config={"options": {}}, headers={"X-Lizmap-User-Groups": "test1"})
    assert acl.cacheKey() == ""

    # No group visibility
    acl = make_acl(
        config={"options": {}, "layers": {"points": {}}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )
    assert acl.cacheKey() == ""

    # A group visibility is defined
    config = {"options": {}, "layers": {"points": {"group_visibility": ["admins", "users"]}}}
    acl = make_acl(config=config, headers={"X-Lizmap-User-Groups": "test1"})
    assert acl.cacheKey() == "test1"

    # Anonymous
    acl = make_acl(config=config, headers={"X-Lizmap-User-Groups": ""})
    assert acl.cacheKey() == "@@"


def test_acl_cache_key_anonymous_group_visibility(project, make_acl):
    """A group visibility with a single entry is skipped for anonymous users."""
    config = {"options": {}, "layers": {"points": {"group_visibility": [""]}}}
    acl = make_acl(config=config, headers={"X-Lizmap-User-Groups": ""})
    assert acl.cacheKey() == ""


#
# get_lizmap_layer_filter
#


def test_acl_filter_override(project, make_acl):
    """The override filter header disables any filter."""
    layer = _layer()
    acl = make_acl(headers={"X-Lizmap-Override-Filter": "true"})
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == ALL_FEATURES


def test_acl_filter_without_group(project, make_acl):
    """Without any group nor login, no filter is applied."""
    layer = _layer()
    acl = make_acl()
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == ALL_FEATURES


def test_acl_filter_without_config(project, make_acl):
    """Without any configuration, no filter is applied."""
    layer = _layer()

    acl = make_acl(headers={"X-Lizmap-User-Groups": "test1"})
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == ALL_FEATURES

    acl = make_acl(config={"options": {}}, headers={"X-Lizmap-User-Groups": "test1"})
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == ALL_FEATURES


def test_acl_filter_layer_not_in_config(project, make_acl):
    """A layer which is not in the configuration is not filtered."""
    layer = _layer()
    acl = make_acl(
        config={"options": {}, "layers": {"another": {}}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == ALL_FEATURES


def test_acl_filter_invalid_polygon_config(project, make_acl):
    """An invalid filter by polygon hides every feature."""
    layer = _layer()
    project.addMapLayer(layer)

    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "filter_by_polygon": {
                "config": {"polygon_layer_id": "unknown_layer", "group_field": "groups"},
                "layers": [{"layer": layer.id(), "primary_key": "id"}],
            },
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == NO_FEATURES


def test_acl_filter_polygon_error(project, make_acl, monkeypatch):
    """An error while reading the filter by polygon hides every feature."""
    import lizmap_server.lizmap_accesscontrol as module

    def broken(*args, **kwargs):
        raise RuntimeError("Broken")

    monkeypatch.setattr(module, "FilterByPolygon", broken)

    layer = _layer()
    acl = make_acl(
        config={"options": {}, "layers": {"points": {}}},
        headers={"X-Lizmap-User-Groups": "test1"},
    )
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == NO_FEATURES


def test_acl_filter_edition_only(project, make_acl):
    """A login filter for edition only does not filter the layer."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "loginFilteredLayers": {
                "points": {
                    "layerId": layer.id(),
                    "filterAttribute": "user",
                    "filterPrivate": "False",
                    "edition_only": "True",
                },
            },
        },
        headers={"X-Lizmap-User-Groups": "test1"},
    )
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == ALL_FEATURES


def test_acl_filter_anonymous(project, make_acl):
    """An anonymous user only sees the features shared with everybody."""
    layer = _layer()
    acl = make_acl(
        config={
            "options": {},
            "layers": {"points": {}},
            "loginFilteredLayers": {
                "points": {
                    "layerId": layer.id(),
                    "filterAttribute": "user",
                    "filterPrivate": "False",
                },
            },
        },
        headers={"X-Lizmap-User-Groups": ""},
    )
    assert acl.get_lizmap_layer_filter(layer, FilterType.QgisExpression) == "\"user\" = 'all'"


#
# Filter by polygon combined with the login filter
#


def _polygon_layers():
    """A polygon layer and the layer it filters."""
    from qgis.core import QgsFeature, QgsGeometry, edit

    polygon = QgsVectorLayer(
        "Polygon?crs=epsg:4326&field=id:integer&field=groups:string", "polygon", "memory"
    )
    with edit(polygon):
        feature = QgsFeature(polygon.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"))
        feature.setAttributes([1, "bob"])
        assert polygon.addFeature(feature)

    points = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer&field=user:string", "points", "memory")
    with edit(points):
        feature = QgsFeature(points.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POINT(1 1)"))
        feature.setAttributes([1, "bob"])
        assert points.addFeature(feature)

    return polygon, points


def _polygon_config(polygon, points, filter_by_user=False, login_filter=None):
    config = {
        "options": {},
        "layers": {"points": {}},
        "filter_by_polygon": {
            "config": {
                "polygon_layer_id": polygon.id(),
                "group_field": "groups",
                "filter_by_user": filter_by_user,
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
    }
    if login_filter is not None:
        config["loginFilteredLayers"] = {"points": login_filter}
    return config


def test_acl_filter_polygon_only(project, make_acl):
    """Without any login filter, the polygon filter is returned."""
    polygon, points = _polygon_layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    acl = make_acl(
        config=_polygon_config(polygon, points),
        headers={"X-Lizmap-User-Groups": "bob"},
    )
    assert "intersects(" in acl.get_lizmap_layer_filter(points, FilterType.QgisExpression)


def test_acl_filter_polygon_by_user(project, make_acl):
    """The polygon filter may be done on the user login."""
    polygon, points = _polygon_layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    acl = make_acl(
        config=_polygon_config(polygon, points, filter_by_user=True),
        headers={"X-Lizmap-User": "bob"},
    )
    assert "intersects(" in acl.get_lizmap_layer_filter(points, FilterType.QgisExpression)


def test_acl_filter_polygon_and_edition_only(project, make_acl):
    """A login filter for edition only keeps the polygon filter."""
    polygon, points = _polygon_layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    acl = make_acl(
        config=_polygon_config(
            polygon,
            points,
            login_filter={
                "layerId": points.id(),
                "filterAttribute": "user",
                "filterPrivate": "False",
                "edition_only": "True",
            },
        ),
        headers={"X-Lizmap-User-Groups": "bob"},
    )
    assert "intersects(" in acl.get_lizmap_layer_filter(points, FilterType.QgisExpression)


def test_acl_filter_polygon_and_anonymous(project, make_acl):
    """An anonymous user gets both the polygon and the login filters."""
    polygon, points = _polygon_layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    acl = make_acl(
        config=_polygon_config(
            polygon,
            points,
            login_filter={
                "layerId": points.id(),
                "filterAttribute": "user",
                "filterPrivate": "False",
            },
        ),
        headers={"X-Lizmap-User-Groups": ""},
    )
    assert acl.get_lizmap_layer_filter(points, FilterType.QgisExpression) == (
        "1 = 0 AND \"user\" = 'all'"
    )


def test_acl_filter_polygon_and_login(project, make_acl):
    """A connected user gets both the polygon and the login filters."""
    polygon, points = _polygon_layers()
    project.addMapLayer(polygon)
    project.addMapLayer(points)

    acl = make_acl(
        config=_polygon_config(
            polygon,
            points,
            login_filter={
                "layerId": points.id(),
                "filterAttribute": "user",
                "filterPrivate": "True",
            },
        ),
        headers={"X-Lizmap-User-Groups": "bob", "X-Lizmap-User": "bob"},
    )
    result = acl.get_lizmap_layer_filter(points, FilterType.QgisExpression)
    assert "intersects(" in result
    assert " AND " in result
    assert "bob" in result
