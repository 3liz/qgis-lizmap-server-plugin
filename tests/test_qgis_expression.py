"""Tests for the Lizmap QGIS expression functions."""

import pytest

from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsProject,
    QgsRasterLayer,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)

# Importing the plugin registers the expression functions
from lizmap_server import qgis_expression  # noqa: F401


@pytest.fixture
def project():
    """A clean QGIS project."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


def _evaluate(expression):
    exp = QgsExpression(expression)
    assert not exp.hasParserError(), exp.parserErrorString()
    value = exp.evaluate(QgsExpressionContext())
    assert not exp.hasEvalError(), exp.evalErrorString()
    return value


def test_expression_layer_not_found(project):
    """An unknown layer has no used attribute."""
    assert _evaluate("layer_renderer_used_attributes('does_not_exist')") == []


def test_expression_not_a_vector_layer(project, rootdir):
    """A raster layer has no used attribute."""
    layer = QgsRasterLayer(str(rootdir.joinpath("data/raster.asc")), "raster", "gdal")
    assert layer.isValid()
    project.addMapLayer(layer)

    assert _evaluate("layer_renderer_used_attributes('raster')") == []


def test_expression_used_attributes(project):
    """The attributes used by the renderer are returned."""
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=cat:string", "points", "memory")
    assert layer.isValid()

    symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.PointGeometry)
    layer.setRenderer(QgsCategorizedSymbolRenderer("cat", [QgsRendererCategory("a", symbol, "A")]))
    project.addMapLayer(layer)

    # By layer name
    assert _evaluate("layer_renderer_used_attributes('points')") == ["cat"]

    # By layer id
    assert _evaluate(f"layer_renderer_used_attributes('{layer.id()}')") == ["cat"]
