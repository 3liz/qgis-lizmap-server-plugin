"""Tests for the error and edge cases of the filter by polygon."""

import pytest

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    edit,
)

from lizmap_server.filter_by_polygon import NO_FEATURES, FilterByPolygon


def _polygons() -> QgsVectorLayer:
    layer = QgsVectorLayer("Polygon?crs=epsg:4326&field=id:integer&field=groups:string", "polygon", "memory")
    with edit(layer):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"))
        feature.setAttributes([1, "east"])
        assert layer.addFeature(feature)

        # Far away from any point
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((80 80,80 81,81 81,81 80,80 80))"))
        feature.setAttributes([2, "far_away"])
        assert layer.addFeature(feature)
    return layer


def _points() -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer", "points", "memory")
    with edit(layer):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POINT(1 1)"))
        feature.setAttributes([1])
        assert layer.addFeature(feature)
    return layer


def _config(polygon, points, **overrides):
    layer_config = {
        "layer": points.id(),
        "primary_key": "id",
        "spatial_relationship": "intersects",
        "filter_mode": "display_and_editing",
    }
    layer_config.update(overrides)
    return {
        "config": {
            "polygon_layer_id": polygon.id(),
            "group_field": "groups",
        },
        "layers": [layer_config],
    }


@pytest.fixture
def project():
    """A clean QGIS project."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


def test_filter_polygon_not_spatial():
    """A layer without geometry is never filtered."""
    layer = QgsVectorLayer("None?field=id:integer", "table", "memory")
    assert not layer.isSpatial()

    config = FilterByPolygon({"layers": [{"layer": layer.id()}]}, layer)
    assert not config.is_filtered()


def test_filter_polygon_no_config():
    """Without any configuration, the layer is not filtered."""
    points = _points()

    assert not FilterByPolygon(None, points).is_filtered()
    assert not FilterByPolygon({}, points).is_filtered()
    assert not FilterByPolygon({"layers": []}, points).is_filtered()


def test_filter_polygon_undefined_properties():
    """The polygon and the primary key must be defined."""
    points = _points()
    config = FilterByPolygon(None, points)

    with pytest.raises(AssertionError, match="polygon is not defined"):
        _ = config.polygon

    with pytest.raises(AssertionError, match="primary_key is not defined"):
        _ = config.primary_key


def test_filter_polygon_invalid_group_field(project):
    """The group field must exist in the polygon layer."""
    polygon = _polygons()
    points = _points()
    project.addMapLayer(polygon)

    config = _config(polygon, points)
    config["config"]["group_field"] = "does_not_exist"

    assert not FilterByPolygon(config, points).is_valid()


def test_filter_polygon_invalid_layer(project):
    """The filtered layer must be valid."""
    polygon = _polygons()
    project.addMapLayer(polygon)

    invalid = QgsVectorLayer("Point?crs=epsg:4326", "invalid", "unknown_provider")
    assert not invalid.isValid()

    config = FilterByPolygon(
        {
            "config": {"polygon_layer_id": polygon.id(), "group_field": "groups"},
            "layers": [{"layer": invalid.id(), "primary_key": "id"}],
        },
        invalid,
    )
    # The layer is not spatial: it is not filtered at all
    assert not config.is_filtered()

    # Force the configuration as if the layer was spatial
    config._primary_key = "id"
    config._polygon = polygon
    config.group_field = "groups"
    assert not config.is_valid()


def test_filter_polygon_unknown_primary_key(project):
    """An unknown primary key is only logged."""
    polygon = _polygons()
    points = _points()
    project.addMapLayer(polygon)

    config = FilterByPolygon(_config(polygon, points, primary_key="does_not_exist"), points)
    assert config.is_valid()


def test_filter_polygon_no_candidate(project):
    """Without any feature in the bounding box, no feature is returned."""
    polygon = _polygons()
    points = _points()
    project.addMapLayer(polygon)

    config = FilterByPolygon(_config(polygon, points), points)
    assert config.is_filtered()

    subset, _ = config.subset_sql(("far_away",))
    assert subset == NO_FEATURES


def test_filter_polygon_contains_relationship(project):
    """A point never contains the filtering polygon."""
    polygon = _polygons()
    points = _points()
    project.addMapLayer(polygon)

    config = FilterByPolygon(_config(polygon, points, spatial_relationship="contains"), points)
    subset, _ = config.subset_sql(("east",))
    assert subset == NO_FEATURES


def test_filter_polygon_unknown_relationship(project):
    """An unknown spatial relationship must raise."""
    polygon = _polygons()
    points = _points()
    project.addMapLayer(polygon)

    config = FilterByPolygon(_config(polygon, points, spatial_relationship="touches"), points)

    with pytest.raises(Exception, match="Spatial relationship unknown"):
        config.subset_sql(("east",))


def test_filter_polygon_format_sql_in_without_values():
    """An empty list of values returns the 'no features' filter."""
    assert FilterByPolygon._format_sql_in("id", []) == NO_FEATURES


def test_filter_polygon_filter_by_user(project):
    """The filter may be done on the user login instead of the groups."""
    polygon = _polygons()
    points = _points()
    project.addMapLayer(polygon)

    config = _config(polygon, points)
    config["config"]["filter_by_user"] = True

    filter_config = FilterByPolygon(config, points)
    assert filter_config.is_filtered_by_user()


def test_filter_polygon_contains_relationship_true(project):
    """A polygon layer filtered by the polygons it contains."""
    filtering = QgsVectorLayer(
        "Polygon?crs=epsg:4326&field=id:integer&field=groups:string", "filtering", "memory"
    )
    with edit(filtering):
        feature = QgsFeature(filtering.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((1 1,1 2,2 2,2 1,1 1))"))
        feature.setAttributes([1, "east"])
        assert filtering.addFeature(feature)

    filtered = QgsVectorLayer("Polygon?crs=epsg:4326&field=id:integer", "filtered", "memory")
    with edit(filtered):
        feature = QgsFeature(filtered.fields())
        feature.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"))
        feature.setAttributes([1])
        assert filtered.addFeature(feature)

    project.addMapLayer(filtering)

    config = FilterByPolygon(
        {
            "config": {"polygon_layer_id": filtering.id(), "group_field": "groups"},
            "layers": [
                {
                    "layer": filtered.id(),
                    "primary_key": "id",
                    "spatial_relationship": "contains",
                    "filter_mode": "display_and_editing",
                },
            ],
        },
        filtered,
    )

    subset, _ = config.subset_sql(("east",))
    assert subset == '"id" IN ( 1 )'


def test_filter_polygon_sql_query_with_connection(project):
    """An already opened connection is reused."""
    from qgis.core import QgsDataSourceUri

    points = _points()
    config = FilterByPolygon(None, points)

    class FakeConnection:
        def __init__(self):
            self.queries = []

        def executeSql(self, sql):
            self.queries.append(sql)
            return (("a result",),)

    connection = FakeConnection()
    config.connection = connection

    assert config.sql_query(QgsDataSourceUri(), "SELECT 1") == (("a result",),)
    assert connection.queries == ["SELECT 1"]


def test_filter_polygon_sql_query_without_connection(project):
    """A connection is opened when none is available."""
    from qgis.core import QgsDataSourceUri, QgsProviderConnectionException

    points = _points()
    config = FilterByPolygon(None, points)
    assert config.connection is None

    uri = QgsDataSourceUri()
    # There is no PostgreSQL server listening on this port
    uri.setConnection("127.0.0.1", "1", "a_database", "a_user", "a_password")

    with pytest.raises(QgsProviderConnectionException):
        config.sql_query(uri, "SELECT 1")

    assert config.connection is not None
