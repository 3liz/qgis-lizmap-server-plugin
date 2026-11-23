"""Regression tests for login filter."""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsVectorLayer,
    edit,
)

from lizmap_server.lizmap_accesscontrol import LizmapAccessControlFilter


def _matching_ids(layer: QgsVectorLayer, expression: str) -> list:
    """The ids of the features matching the expression."""
    request = QgsFeatureRequest()
    request.setFilterExpression(expression)
    return sorted(feature["id"] for feature in layer.getFeatures(request))


#
# Login filter — Operator precedence drops the polygon filter (ACL bypass)
#
# `_filter_by_login` returns an unparenthesised OR chain which is concatenated
# with the polygon filter using AND. Because AND binds tighter than OR, every
# feature whose login attribute is 'all' escapes the spatial restriction.
#


# Only the two features inside this polygon may ever be returned.
POLYGON_FILTER = "intersects($geometry, geom_from_wkt('POLYGON((0 0, 0 5, 5 5, 5 0, 0 0))'))"

INSIDE = [1, 2]
ALL_IDS = [1, 2, 3, 4]


def _acl_layer() -> QgsVectorLayer:
    """Four points, two inside the polygon above, with an ACL attribute."""
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=id:integer&field=f:string", "points", "memory")
    assert layer.isValid()
    with edit(layer):
        for identifier, value, wkt in (
            (1, "grp_1", "POINT(1 1)"),  # inside, own group
            (2, "all", "POINT(2 2)"),  # inside, everyone
            (3, "grp_1", "POINT(10 10)"),  # outside, own group
            (4, "all", "POINT(11 11)"),  # outside, everyone
        ):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes([identifier, value])
            assert layer.addFeature(feature)
    return layer


def test_login_filter_does_not_escape_the_polygon_filter():
    """`polygon AND login_filter` must not return features outside the polygon."""
    layer = _acl_layer()
    config = {
        "filterPrivate": False,
        "filterAttribute": "f",
        "allow_multiple_acl_values": False,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("grp_1",), "", "ogr")

    # On its own, the filter lets every feature of the two groups through
    assert _matching_ids(layer, login_filter) == ALL_IDS

    # Combined with the spatial filter, only the features inside the polygon
    assert _matching_ids(layer, f"{POLYGON_FILTER} AND {login_filter}") == INSIDE


def test_login_filter_with_multiple_acl_values():
    """The filter of multiple values must not escape the polygon filter either.

    This filter is PostgreSQL SQL (string_to_array, &&), which QGIS cannot evaluate
    on a memory layer: its structure is checked instead. It is a single parenthesised
    term, so it cannot be split by an AND added before or after it.
    """
    config = {
        "filterPrivate": False,
        "filterAttribute": "f",
        "allow_multiple_acl_values": True,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("grp_1",), "", "postgres")

    assert login_filter == "(string_to_array(\"f\", ',') && ARRAY['grp_1', 'all'])"
    # No OR left, which could take precedence over an AND
    assert " OR " not in login_filter.upper()


def test_private_login_filter_does_not_escape_the_polygon_filter():
    """The 'filterPrivate' variant has the same precedence problem."""
    layer = _acl_layer()
    config = {
        "filterPrivate": True,
        "filterAttribute": "f",
        "allow_multiple_acl_values": False,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("other",), "grp_1", "ogr")

    assert _matching_ids(layer, login_filter) == ALL_IDS
    assert _matching_ids(layer, f"{POLYGON_FILTER} AND {login_filter}") == INSIDE


def test_login_filter_is_safe_when_joined_by_qgis():
    """QGIS joins the filter to other subset strings with AND, without parenthesis."""
    layer = _acl_layer()
    config = {
        "filterPrivate": False,
        "filterAttribute": "f",
        "allow_multiple_acl_values": False,
    }

    login_filter = LizmapAccessControlFilter._filter_by_login(config, ("grp_1",), "", "ogr")

    # A subset string hiding the feature 4, as another access control filter would do
    assert _matching_ids(layer, f'"id" <> 4 AND {login_filter}') == [1, 2, 3]
