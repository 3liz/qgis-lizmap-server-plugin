"""Tests for the tooltip generation from the drag&drop form."""

import pytest

from qgis.core import (
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsAttributeEditorRelation,
    QgsAttributeEditorTextElement,
    QgsEditorWidgetSetup,
    QgsExpression,
    QgsOptionalExpression,
    QgsProject,
    QgsRelation,
    QgsVectorLayer,
)
from qgis.gui import QgsExternalResourceWidget

from lizmap_server.tooltip import InvalidWidgetConfig, Tooltip


def _layer(name: str = "layer") -> QgsVectorLayer:
    layer = QgsVectorLayer(
        "Point?crs=epsg:4326&field=id:integer&field=name:string&field=photo:string"
        "&field=code:string&field=kind:string&field=day:string&field=secret:string",
        name,
        "memory",
    )
    assert layer.isValid()
    return layer


def test_tooltip_helpers():
    """The small html/expression generators."""
    assert Tooltip.create_popup("<p></p>").startswith('<div class="container popup_lizmap_dd')

    assert Tooltip.remove_none({"a": 1, "b": None}) == {"a": 1}

    assert Tooltip.friendly_name("name", "") == "name"
    assert Tooltip.friendly_name("name", "L'alias") == "L’alias"  # noqa: RUF001

    assert Tooltip._generate_field_view("name") == '"name"'
    assert Tooltip._generate_represent_value("name") == 'represent_value("name")'

    assert Tooltip._generate_eval_visibility('"a" = 1') == "[% if (\"a\" = 1, '', 'hidden') %]"

    result = Tooltip._generate_attribute_editor_relation("A label", "rel_id", "layer_id")
    assert "<p><b>A label</b></p>" in result
    assert 'data-relation-id="rel_id"' in result
    assert 'data-referencing-layer-id="layer_id"' in result

    result = Tooltip._generate_text_label("A label", "[% 1 + 1 %]")
    assert "<p><strong>A label</strong>" in result
    assert '<div class="field">[% 1 + 1 %]</div>' in result


def test_tooltip_generate_date():
    """The date widget must use the configured format."""
    assert '\'yyyy-MM-dd\'' in Tooltip._generate_date({}, "day")
    assert "format_date(" in Tooltip._generate_date({}, "day")

    result = Tooltip._generate_date({"display_format": "dd/MM/yyyy"}, "day")
    assert "'dd/MM/yyyy'" in result


def test_tooltip_generate_value_map():
    """The value map widget is converted to an hstore expression."""
    # QGIS >= 3.x stores the map as a list of single entry dictionaries
    config = {"map": [{"Label A": "a"}, {"L'label B": "b"}, {"<NULL>": None}]}
    result = Tooltip._generate_value_map(config, "kind")
    assert "hstore_to_map(" in result
    assert "L’label B" in result  # noqa: RUF001
    assert "<NULL>" not in result

    # It can also be a dictionary
    config = {"map": {"Label A": "a", "<NULL>": "null_value"}}
    result = Tooltip._generate_value_map(config, "kind")
    assert "hstore_to_map(" in result
    assert "<NULL>" not in result

    # A dictionary without any null entry
    result = Tooltip._generate_value_map({"map": {"Label A": "a"}}, "kind")
    assert "hstore_to_map(" in result

    # The widget is not configured yet
    assert Tooltip._generate_value_map({"map": None}, "kind") == "''"


def test_tooltip_generate_external_resource():
    """The external resource widget depends on the document viewer."""
    content = QgsExternalResourceWidget.DocumentViewerContent

    result = Tooltip._generate_external_resource({"DocumentViewer": content.Image}, "photo", "Photo")
    assert "<img src=" in result

    result = Tooltip._generate_external_resource({"DocumentViewer": content.Web}, "photo", "Photo")
    assert "<iframe src=" in result

    result = Tooltip._generate_external_resource({"DocumentViewer": content.NoContent}, "photo", "Photo")
    assert "base_file_name(" in result

    with pytest.raises(TypeError):
        Tooltip._generate_external_resource({"DocumentViewer": -1}, "photo", "Photo")


def test_tooltip_text_element():
    """A text element must be rendered as a label."""
    layer = _layer()
    node = QgsAttributeEditorTextElement("A text", None)
    node.setText("Hello")

    html = Tooltip.create_popup_node_item_from_form(
        layer, node, 1, [], "", QgsProject.instance().relationManager()
    )
    assert "<strong>A text</strong>" in html


def test_tooltip_invalid_field():
    """A field which is not in the layer must be skipped."""
    layer = _layer()
    node = QgsAttributeEditorField("does_not_exist", -1, None)

    html = Tooltip.create_popup_node_item_from_form(
        layer, node, 1, [], "some html", QgsProject.instance().relationManager()
    )
    assert html == "some html"


def test_tooltip_hidden_field():
    """A hidden field must not be rendered."""
    layer = _layer()
    index = layer.fields().indexOf("secret")
    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("Hidden", {}))

    node = QgsAttributeEditorField("secret", index, None)
    html = Tooltip.create_popup_node_item_from_form(
        layer, node, 1, [], "some html", QgsProject.instance().relationManager()
    )
    assert html == "some html"


def test_tooltip_widget_types():
    """Each supported widget type must generate its own expression."""
    layer = _layer()
    fields = layer.fields()
    relation_manager = QgsProject.instance().relationManager()

    setups = {
        "photo": QgsEditorWidgetSetup(
            "ExternalResource",
            {"DocumentViewer": QgsExternalResourceWidget.DocumentViewerContent.Image},
        ),
        "kind": QgsEditorWidgetSetup("ValueMap", {"map": [{"Label A": "a"}]}),
        "day": QgsEditorWidgetSetup("DateTime", {"display_format": "dd/MM/yyyy"}),
    }
    for name, setup in setups.items():
        layer.setEditorWidgetSetup(fields.indexOf(name), setup)

    expected = {
        "photo": "<img src=",
        "kind": "hstore_to_map(",
        "day": "format_date(",
    }
    for name, marker in expected.items():
        node = QgsAttributeEditorField(name, fields.indexOf(name), None)
        html = Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "", relation_manager)
        assert marker in html, name


def test_tooltip_value_relation():
    """The value relation widget needs a valid layer."""
    layer = _layer()
    index = layer.fields().indexOf("code")
    relation_manager = QgsProject.instance().relationManager()

    # No 'Layer' in the configuration
    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("ValueRelation", {}))
    node = QgsAttributeEditorField("code", index, None)
    with pytest.raises(InvalidWidgetConfig):
        Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "", relation_manager)

    # The layer is not in the project
    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("ValueRelation", {"Layer": "unknown_id"}))
    html = Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "some html", relation_manager)
    assert html == "some html"

    # The layer is in the project
    project = QgsProject.instance()
    referenced = _layer("referenced")
    project.addMapLayer(referenced)
    try:
        layer.setEditorWidgetSetup(
            index, QgsEditorWidgetSetup("ValueRelation", {"Layer": referenced.id()})
        )
        html = Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "", relation_manager)
        assert 'represent_value("code")' in html
    finally:
        project.removeMapLayer(referenced.id())


def test_tooltip_relation_reference():
    """The relation reference widget needs a valid relation."""
    layer = _layer()
    index = layer.fields().indexOf("code")
    project = QgsProject.instance()
    relation_manager = project.relationManager()

    # No 'Relation' in the configuration
    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("RelationReference", {}))
    node = QgsAttributeEditorField("code", index, None)
    with pytest.raises(InvalidWidgetConfig):
        Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "", relation_manager)

    # The relation does not exist
    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("RelationReference", {"Relation": "unknown"}))
    html = Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "some html", relation_manager)
    assert html == "some html"

    # A valid relation
    referenced = _layer("referenced")
    project.addMapLayer(layer)
    project.addMapLayer(referenced)
    relation = QgsRelation()
    relation.setId("a_relation")
    relation.setName("A relation")
    relation.setReferencingLayer(layer.id())
    relation.setReferencedLayer(referenced.id())
    relation.addFieldPair("code", "name")
    assert relation.isValid()
    relation_manager.addRelation(relation)
    try:
        layer.setEditorWidgetSetup(
            index, QgsEditorWidgetSetup("RelationReference", {"Relation": "a_relation"})
        )
        html = Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "", relation_manager)
        assert 'represent_value("code")' in html

        # A relation node
        node = QgsAttributeEditorRelation("a_relation", None)
        node.setLabel("The relation")
        html = Tooltip.create_popup_node_item_from_form(layer, node, 1, [], "", relation_manager)
        assert 'data-relation-id="a_relation"' in html
    finally:
        relation_manager.setRelations([])
        project.removeMapLayer(referenced.id())
        project.removeMapLayer(layer.id())


@pytest.mark.parametrize("bootstrap_5", [False, True])
def test_tooltip_containers(bootstrap_5):
    """The containers must generate the tabs and the fieldsets."""
    layer = _layer()
    fields = layer.fields()
    relation_manager = QgsProject.instance().relationManager()

    root = QgsAttributeEditorContainer("root", None)

    # A field at the root level, before the tabs
    root.addChildElement(QgsAttributeEditorField("id", fields.indexOf("id"), root))

    # A first tab, with a nested group box and a visibility expression
    tab = QgsAttributeEditorContainer("Tab 1", root)
    tab.setVisibilityExpression(QgsOptionalExpression(QgsExpression('"id" > 0')))
    tab.addChildElement(QgsAttributeEditorField("name", fields.indexOf("name"), tab))
    group = QgsAttributeEditorContainer("Group", tab)
    group.addChildElement(QgsAttributeEditorField("code", fields.indexOf("code"), group))
    tab.addChildElement(group)
    root.addChildElement(tab)

    # A second tab, with a visibility expression
    tab2 = QgsAttributeEditorContainer("Tab 2", root)
    tab2.setVisibilityExpression(QgsOptionalExpression(QgsExpression('"id" = 1')))
    tab2.addChildElement(QgsAttributeEditorField("day", fields.indexOf("day"), tab2))
    root.addChildElement(tab2)

    # A field at the root level, after the tabs
    root.addChildElement(QgsAttributeEditorField("kind", fields.indexOf("kind"), root))

    html = Tooltip.create_popup_node_item_from_form(layer, root, 0, [], "", relation_manager, bootstrap_5)

    assert '<div class="before-tabs">' in html
    assert '<ul class="nav nav-tabs">' in html
    assert '<div class="tab-content">' in html
    assert '<div class="after-tabs">' in html
    assert "<fieldset" in html
    assert "<legend class=\"float-none\">Group</legend>" in html
    assert "[% if (\"id\" = 1, '', 'hidden') %]" in html
    # The first tab is active and has a visibility expression
    assert "active [% if (\"id\" > 0, '', 'hidden') %]" in html

    if bootstrap_5:
        assert 'data-bs-toggle="tab"' in html
    else:
        assert 'data-bs-toggle="tab"' not in html
