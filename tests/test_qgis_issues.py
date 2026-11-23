#
# Issues from QGIS not fixable in Lizmap server
#

import pytest

from qgis.core import (
    QgsAttributeEditorField,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsProject,
    QgsVectorLayer,
    edit,
)

from lizmap_server.tooltip import Tooltip


@pytest.fixture
def project():
    """A clean QGIS project instance."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


@pytest.mark.xfail
def test_maptip_escapes_the_feature_values(project):
    """A feature value must not be injected as HTML in the popup."""
    layer = QgsVectorLayer(
        "Point?crs=epsg:4326&field=id:integer&field=name:string",
        "layer",
        "memory",
    )
    assert layer.isValid()
    with edit(layer):
        feature = QgsFeature(layer.fields())
        feature.setAttributes([1, "<script>alert('xss')</script>"])
        assert layer.addFeature(feature)

    index = layer.fields().indexOf("name")
    node = QgsAttributeEditorField("name", index, None)
    html = Tooltip.create_popup_node_item_from_form(
        layer,
        node,
        1,
        [],
        "",
        project.relationManager(),
    )

    context = QgsExpressionContext()
    context.appendScope(QgsExpressionContextUtils.globalScope())
    context.appendScope(QgsExpressionContextUtils.layerScope(layer))
    context.setFeature(next(layer.getFeatures()))

    rendered = QgsExpression.replaceExpressionText(html, context)

    assert "<script>" not in rendered, rendered
