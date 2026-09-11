"""Test filter by polygon."""

import gc
import weakref

from typing import Sequence

import unittest
import pytest

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    edit,
)

from lizmap_server.filter_by_polygon import NO_FEATURES, FilterByPolygon


class TestFilterByPolygon(unittest.TestCase):
    def test_not_filtered_layer(self):
        """Test for not filtered layer."""
        json = {
            "config": {
                "polygon_layer_id": "FOO",
                "group_field": "groups",
            },
            "layers": [
                {
                    "layer": "BAR",
                    "primary_key": "primary",
                    "spatial_relationship": "intersects",
                    "filter_mode": "display_and_editing",
                },
            ],
        }
        points = QgsVectorLayer("Point?field=id:integer", "points", "memory")
        self.assertFalse(FilterByPolygon(json, points).is_filtered())
        self.assertFalse(FilterByPolygon(json, points).is_valid())

    # noinspection PyArgumentList
    def test_filter_by_polygon_filter(self):
        """Test the generation of filter by polygon."""
        polygon = QgsVectorLayer("Polygon?field=id:integer&field=groups:string", "polygon", "memory")
        with edit(polygon):
            feature = QgsFeature(polygon.fields())
            feature.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"))
            feature.setAttributes([1, "east,admins"])
            self.assertTrue(polygon.addFeature(feature))

            feature = QgsFeature(polygon.fields())
            feature.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0,0 -5,-5 -5,-5 0,0 0))"))
            feature.setAttributes([1, "west,admins"])
            self.assertTrue(polygon.addFeature(feature))

            #  -5                0                5
            #  ####################################
            #  #                 |                |
            #  #  west, admins   |  east, admins  |
            #  #                 |                |
            #  ####################################

        points = QgsVectorLayer("Point?field=id:integer", "points", "memory")
        with edit(points):
            # In east group
            feature = QgsFeature(points.fields())
            feature.setGeometry(QgsGeometry.fromWkt("POINT(1 1)"))
            feature.setAttributes([1])
            self.assertTrue(points.addFeature(feature))

            # Outside
            feature = QgsFeature(points.fields())
            feature.setGeometry(QgsGeometry.fromWkt("POINT(10 10)"))
            feature.setAttributes([2])
            self.assertTrue(points.addFeature(feature))

            # In west group
            feature = QgsFeature(points.fields())
            feature.setGeometry(QgsGeometry.fromWkt("POINT(-1 -1)"))
            feature.setAttributes([3])
            self.assertTrue(points.addFeature(feature))

        # The only layer is display_and_editing
        json = {
            "config": {
                "polygon_layer_id": polygon.id(),
                "group_field": "groups",
            },
            "layers": [
                {
                    "layer": points.id(),
                    "primary_key": "id",
                    "spatial_relationship": "intersects",
                    "filter_mode": "display_and_editing",
                },
            ],
        }

        project = QgsProject.instance()
        project.addMapLayer(polygon)

        config = FilterByPolygon(json, points, editing=False)
        self.assertTrue(config.is_filtered())
        self.assertTrue(FilterByPolygon(json, points).is_valid())

        # For unknown
        groups = ("unknown",)
        geom = config._polygon_for_groups_with_qgis_api(groups)
        self.assertTrue(geom.isEmpty())
        subset, ewkt = config.subset_sql(groups)
        self.assertEqual("1 = 0", subset)
        self.assertEqual("", ewkt)

        # For admins, they see everything inside, not the one outside
        groups = ("admins",)
        geom = config._polygon_for_groups_with_qgis_api(groups)
        self.assertEqual(
            "MultiPolygon (((0 0, 0 5, 5 5, 5 0, 0 0)),((0 0, 0 -5, -5 -5, -5 0, 0 0)))", geom.asWkt(0)
        )
        subset, ewkt = config.subset_sql(groups)
        self.assertEqual('"id" IN ( 1 , 3 )', subset)
        self.assertEqual(
            "SRID=4326;MultiPolygon (((0 0, 0 5, 5 5, 5 0, 0 0)),((0 0, 0 -5, -5 -5, -5 0, 0 0)))", ewkt
        )

        # For east
        groups = ("east",)
        geom = config._polygon_for_groups_with_qgis_api(groups)
        self.assertEqual("MultiPolygon (((0 0, 0 5, 5 5, 5 0, 0 0)))", geom.asWkt(0))
        subset, ewkt = config.subset_sql(groups)
        self.assertEqual('"id" IN ( 1 )', subset)
        self.assertEqual("SRID=4326;MultiPolygon (((0 0, 0 5, 5 5, 5 0, 0 0)))", ewkt)

        # For west
        groups = ("west",)
        geom = config._polygon_for_groups_with_qgis_api(groups)
        self.assertEqual("MultiPolygon (((0 0, 0 -5, -5 -5, -5 0, 0 0)))", geom.asWkt(0))
        subset, ewkt = config.subset_sql(groups)
        self.assertEqual('"id" IN ( 3 )', subset)
        self.assertEqual("SRID=4326;MultiPolygon (((0 0, 0 -5, -5 -5, -5 0, 0 0)))", ewkt)

        # The only layer is editing only
        json = {
            "config": {
                "polygon_layer_id": polygon.id(),
                "group_field": "groups",
            },
            "layers": [
                {
                    "layer": points.id(),
                    "primary_key": "id",
                    "spatial_relationship": "intersects",
                    "filter_mode": "editing",
                },
            ],
        }

        config = FilterByPolygon(json, points, editing=False)
        self.assertTrue(config.is_filtered())
        self.assertTrue(FilterByPolygon(json, points).is_valid())

        groups = ("admins",)
        subset, ewkt = config.subset_sql(groups)
        self.assertEqual("", subset)
        self.assertEqual("", ewkt)

        config = FilterByPolygon(json, points, editing=True)
        self.assertTrue(config.is_filtered())
        self.assertTrue(FilterByPolygon(json, points).is_valid())

        groups = ("admins",)
        geom = config._polygon_for_groups_with_qgis_api(groups)
        self.assertEqual(
            "MultiPolygon (((0 0, 0 5, 5 5, 5 0, 0 0)),((0 0, 0 -5, -5 -5, -5 0, 0 0)))", geom.asWkt(0)
        )
        # self.assertEqual('"id" IN (1, 3)', config.subset_sql(groups))
        # self.assertEqual('', config.subset_sql(groups))
        project.clear()

    def test_format_sql_in(self):
        """Test SQL IN statement."""
        # Integer only
        sql = FilterByPolygon._format_sql_in("code", (1, 2, 3))
        expected = '"code" IN ( 1 , 2 , 3 )'
        self.assertEqual(expected, sql)

        # Integer as string
        sql = FilterByPolygon._format_sql_in("code", ("1", "2", "3"))
        expected = "\"code\" IN ( '1' , '2' , '3' )"
        self.assertEqual(expected, sql)

        # String
        sql = FilterByPolygon._format_sql_in("code", ("a", "b", "c"))
        expected = "\"code\" IN ( 'a' , 'b' , 'c' )"
        self.assertEqual(expected, sql)

    def test_format_qgis_expression(self):
        """Test building a QGIS expression."""
        sql = FilterByPolygon._format_qgis_expression_relationship(
            QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"),
            use_st_intersect=False,
            use_centroid=True,
        )
        expected = """
contains(
    transform(geom_from_wkt('Polygon ((0 0, 0 5, 5 5, 5 0, 0 0))'), 'EPSG:4326', 'EPSG:2154'),
    centroid($geometry)
)"""
        self.assertEqual(expected, sql)

        sql = FilterByPolygon._format_qgis_expression_relationship(
            QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"),
            use_st_intersect=False,
            use_centroid=True,
        )
        expected = """
contains(
    geom_from_wkt('Polygon ((0 0, 0 5, 5 5, 5 0, 0 0))'),
    centroid($geometry)
)"""
        self.assertEqual(expected, sql)

    def test_subset_string_postgres(self):
        """Test building a postgresql string for filter by polygon."""
        # ST_Intersect
        sql = FilterByPolygon._format_sql_st_relationship(
            QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            "geom",
            QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"),
            use_st_intersect=True,
            use_centroid=True,
        )
        expected = """
ST_Intersects(
    ST_Transform(ST_SetSRID(ST_GeomFromText('Polygon ((0 0, 0 5, 5 5, 5 0, 0 0))'), 4326), 2154),
    ST_Centroid("geom")
)"""
        self.assertEqual(expected, sql, sql)

        # ST_Contains
        sql = FilterByPolygon._format_sql_st_relationship(
            QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            "geom",
            QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"),
            use_st_intersect=False,
            use_centroid=False,
        )
        expected = """
ST_Contains(
    ST_Transform(ST_SetSRID(ST_GeomFromText('Polygon ((0 0, 0 5, 5 5, 5 0, 0 0))'), 4326), 2154),
    "geom"
)"""
        self.assertEqual(expected, sql)

        # ST_Contains
        sql = FilterByPolygon._format_sql_st_relationship(
            QgsCoordinateReferenceSystem("EPSG:2154"),
            QgsCoordinateReferenceSystem("EPSG:2154"),
            "geom",
            QgsGeometry.fromWkt("POLYGON((0 0,0 5,5 5,5 0,0 0))"),
            use_st_intersect=False,
            use_centroid=True,
        )
        expected = """
ST_Contains(
    ST_SetSRID(ST_GeomFromText('Polygon ((0 0, 0 5, 5 5, 5 0, 0 0))'), 2154),
    ST_Centroid(\"geom\")
)"""
        self.assertEqual(expected, sql)

    def test_format_table_name(self):
        """Test format table name."""
        uri = QgsDataSourceUri()
        uri.setConnection("localhost", "5432", "dbname", "johny", "xxx")
        uri.setDataSource("public", "roads", "the_geom", "cityid = 2643", "primary_key_field")

        self.assertEqual('"public"."roads"', FilterByPolygon._format_table_name(uri))

        uri.setDataSource("", "roads", "the_geom", "cityid = 2643", "primary_key_field")

        self.assertEqual('"roads"', FilterByPolygon._format_table_name(uri))

        uri.setDataSource(
            "", '(SELECT * FROM "public"."roads")', "the_geom", "cityid = 2643", "primary_key_field"
        )

        self.assertEqual('(SELECT * FROM "public"."roads")', FilterByPolygon._format_table_name(uri))


#
# QGIS expression injection via user group / login
#
# The groups (or the login) come from the `X-Lizmap-User-Groups` header or from
# the `LIZMAP_USER_GROUPS` parameter and are interpolated verbatim into a QGIS
# expression by `_polygon_for_groups_with_qgis_api`.
#


@pytest.fixture
def project():
    """A clean QGIS project instance."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


# Closes the string literal and the enclosing calls, appends 'or true', then
# re-opens what the template closes after the interpolation point.
GROUP_INJECTION = (
    "a'), trim(@element))) or true or array_intersect(array('x'), array_foreach(string_to_array('b"
)

# East and west polygons, plus a polygon for a group whose name holds a quote
EAST = "POLYGON((0 0,0 5,5 5,5 0,0 0))"
WEST = "POLYGON((0 0,0 -5,-5 -5,-5 0,0 0))"
FAR = "POLYGON((10 10,10 15,15 15,15 10,10 10))"


def _polygon_config(project: QgsProject) -> tuple[dict, QgsVectorLayer, QgsVectorLayer]:
    """A filter by polygon configuration, its polygon layer and the filtered layer."""
    polygon = QgsVectorLayer(
        "Polygon?crs=epsg:4326&field=id:integer&field=groups:string",
        "polygon",
        "memory",
    )
    assert polygon.isValid()
    with edit(polygon):
        for identifier, groups, wkt in (
            (1, "east,admins", EAST),
            (2, "west,admins", WEST),
            (3, "O'Brien", FAR),
        ):
            feature = QgsFeature(polygon.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes([identifier, groups])
            assert polygon.addFeature(feature)

    points = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer", "points", "memory")
    assert points.isValid()
    with edit(points):
        for identifier, wkt in ((1, "POINT(1 1)"), (2, "POINT(-1 -1)"), (3, "POINT(11 11)")):
            feature = QgsFeature(points.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes([identifier])
            assert points.addFeature(feature)

    project.addMapLayer(polygon)

    config = {
        "config": {
            "polygon_layer_id": polygon.id(),
            "group_field": "groups",
        },
        "layers": [
            {
                "layer": points.id(),
                "primary_key": "id",
                "spatial_relationship": "intersects",
                "filter_mode": "display_and_editing",
            },
        ],
    }
    return config, polygon, points


def test_group_injection_does_not_select_every_polygon(project):
    """An expression injected in a group name must not lift the spatial restriction."""
    config, _, points = _polygon_config(project)

    injected = FilterByPolygon(config, points)._polygon_for_groups_with_qgis_api((GROUP_INJECTION,))
    unknown = FilterByPolygon(config, points)._polygon_for_groups_with_qgis_api(("unknown",))

    # The injected value is a group name like any other: it matches no polygon
    assert injected.isEmpty(), f"The injection selected {injected.asWkt(0)}"
    assert unknown.isEmpty()


def test_group_injection_does_not_lift_the_subset_string(project):
    """The generated subset string must hide everything for an injected group."""
    config, _, points = _polygon_config(project)

    subset, ewkt = FilterByPolygon(config, points).subset_sql((GROUP_INJECTION,))

    assert subset == NO_FEATURES
    assert ewkt == ""


def test_group_with_a_quote_is_matched_literally(project):
    """A group name holding a single quote must be quoted, not break the expression."""
    config, _, points = _polygon_config(project)

    geometry = FilterByPolygon(config, points)._polygon_for_groups_with_qgis_api(("O'Brien",))

    # The third polygon, and only this one
    assert not geometry.isEmpty()
    assert geometry.intersects(QgsGeometry.fromWkt(FAR))
    assert not geometry.intersects(QgsGeometry.fromWkt(EAST))


def test_user_with_a_quote_is_matched_literally(project):
    """The same values may come from the login when 'filter_by_user' is set."""
    config, _, points = _polygon_config(project)
    config["config"]["filter_by_user"] = True

    config_filter = FilterByPolygon(config, points)
    assert config_filter.is_filtered_by_user()

    subset, _ = config_filter.subset_sql(("O'Brien",))

    # The point inside the 'O'Brien' polygon
    assert subset == '"id" IN ( 3 )'


@pytest.mark.xfail
def test_filter_by_polygon_does_not_retain_the_instance(project):
    """The `lru_cache` on the instance methods must not keep the layers alive."""
    config, _, points = _polygon_config(project)

    config_filter = FilterByPolygon(config, points)
    config_filter._polygon_for_groups_with_qgis_api(("east",))
    config_filter._features_ids_with_qgis_api(QgsGeometry.fromWkt(EAST))

    reference = weakref.ref(config_filter)
    del config_filter
    gc.collect()

    assert reference() is None, "The filter by polygon instance is retained by the cache"


#
# Unescaped values in the generated IN (…) subset string
#
# `_format_sql_in` quotes the values by string interpolation. The values are
# primary key values read back from the layer, so a value holding a single
# quote breaks — or extends — the subset string applied to the layer.
#


def _matching_ids(layer: QgsVectorLayer, expression: str) -> list:
    """The ids of the features matching the expression."""
    request = QgsFeatureRequest()
    request.setFilterExpression(expression)
    return sorted(feature["id"] for feature in layer.getFeatures(request))


def _code_layer(values: Sequence[str]) -> QgsVectorLayer:
    """A layer with a text primary key holding the given values."""
    layer = QgsVectorLayer("None?field=id:integer&field=code:string", "codes", "memory")
    assert layer.isValid()
    with edit(layer):
        for identifier, value in enumerate(values, start=1):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([identifier, value])
            assert layer.addFeature(feature)
    return layer


def test_format_sql_in_escapes_the_quote():
    """A value holding a single quote must not break the subset string."""
    value = "L'Île"
    layer = _code_layer(["Paris", value, "Lyon"])

    subset = FilterByPolygon._format_sql_in("code", (value,))

    expression = QgsExpression(subset)
    assert not expression.hasParserError(), f"{subset}: {expression.parserErrorString()}"
    assert _matching_ids(layer, subset) == [2]


def test_format_sql_in_does_not_allow_injection():
    """A crafted primary key value must not turn the filter into a tautology."""
    payload = "x') OR ('1'='1"
    layer = _code_layer(["Paris", "Lyon", payload])

    subset = FilterByPolygon._format_sql_in("code", (payload,))

    # Only the feature actually holding this value
    assert _matching_ids(layer, subset) == [3], subset


def test_format_sql_in_quotes_the_column():
    """The primary key must be quoted as a column reference."""
    subset = FilterByPolygon._format_sql_in('co"de', (1,))

    expression = QgsExpression(subset)
    assert not expression.hasParserError(), f"{subset}: {expression.parserErrorString()}"


def test_format_sql_in_keeps_the_plain_values():
    """The escaping must not change the output for ordinary values."""
    assert FilterByPolygon._format_sql_in("code", (1, 2, 3)) == '"code" IN ( 1 , 2 , 3 )'
    assert FilterByPolygon._format_sql_in("code", ("a", "b")) == "\"code\" IN ( 'a' , 'b' )"
