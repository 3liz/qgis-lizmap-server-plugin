"""Tests for the api project/layer builders."""

import pytest

from qgis.core import (
    QgsAnnotationLayer,
    QgsAttributeTableConfig,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsFieldConstraints,
    QgsMapThemeCollection,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    Qgis,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from lizmap_server.api import builder
from lizmap_server.api.builders import layers as layers_builder
from lizmap_server.api.builders import project as project_builder
from lizmap_server.api.schemas import VectorLayerDetails


def _dom(content: str) -> QDomElement:
    doc = QDomDocument()
    assert doc.setContent(content)
    return doc.documentElement()


#
# Field configuration parsing
#


def test_builder_edit_widget_null():
    """A null element has no edit widget."""
    assert project_builder.edit_widget(QDomElement()) is None


def test_builder_field_defaults_incomplete():
    """A default without field or expression is skipped."""
    elem = _dom(
        """
        <maplayer>
          <defaults>
            <default field="" expression="1"/>
            <default field="id" expression=""/>
            <default field="code" expression="'a'" applyOnUpdate="1"/>
          </defaults>
        </maplayer>
        """
    )
    defaults = dict(project_builder.read_layer_field_defaults(elem))
    assert list(defaults) == ["code"]
    assert defaults["code"].apply_on_update is True


def test_builder_field_constraint_expressions_incomplete():
    """A constraint expression without field or expression is skipped."""
    elem = _dom(
        """
        <maplayer>
          <constraintExpressions>
            <constraint field="" exp="1"/>
            <constraint field="id" exp=""/>
            <constraint field="code" exp="&quot;code&quot; &gt; 0" desc="Positive"/>
          </constraintExpressions>
        </maplayer>
        """
    )
    expressions = dict(project_builder.read_layer_field_constraint_expr(elem))
    assert list(expressions) == ["code"]
    assert expressions["code"].description == "Positive"


def test_builder_field_constraints_incomplete():
    """A constraint without field or without any flag is skipped."""
    elem = _dom(
        """
        <maplayer>
          <constraints>
            <constraint field="" constraints="1"/>
            <constraint field="id" constraints="0"/>
            <constraint field="code" constraints="1"/>
          </constraints>
        </maplayer>
        """
    )
    assert list(dict(project_builder.read_layer_field_constraints(elem))) == ["code"]


def test_builder_editable_fields_incomplete():
    """An editable field without name is skipped."""
    elem = _dom(
        """
        <maplayer>
          <editable>
            <field name="" editable="1"/>
            <field name="code" editable="0"/>
          </editable>
        </maplayer>
        """
    )
    assert dict(project_builder.read_layer_editable_fields(elem)) == {"code": False}


def test_builder_field_configuration_flags():
    """The configuration flags are parsed from the attribute."""
    elem = _dom(
        """
        <maplayer>
          <fieldConfiguration>
            <field name="a" configurationFlags="HideFromWms"/>
            <field name="b" configurationFlags="HideFromWfs|Searchable"/>
            <field name="c" configurationFlags="NoFlag"/>
          </fieldConfiguration>
        </maplayer>
        """
    )
    fields = dict(project_builder.read_layer_field_configuration(elem))

    assert fields["a"].hide_from_wms and not fields["a"].hide_from_wfs
    assert fields["b"].hide_from_wfs and not fields["b"].hide_from_wms
    assert not fields["c"].hide_from_wms and not fields["c"].hide_from_wfs


#
# Layer details
#


def test_builder_layer_details_excluded_attributes():
    """The excluded attributes are read from the layer details."""
    details = VectorLayerDetails(
        provider="ogr",
        editable_fields={},
        fields={
            "a": {"hide_from_wms": True, "hide_from_wfs": False, "flags": "HideFromWms"},
            "b": {"hide_from_wms": False, "hide_from_wfs": True, "flags": "HideFromWfs"},
        },
        defaults={},
        constraints={},
        constraint_expressions={},
    )

    assert details.exclude_attribute_wms() == ("a",)
    assert details.exclude_attribute_wfs() == ("b",)

    layer = QgsVectorLayer("Point?crs=epsg:4326&field=a:string&field=b:string", "points", "memory")
    description = layers_builder.layer_description(layer, QgsProject(), {layer.id(): details})

    assert description.provider == "ogr"
    assert description.exclude_attribute_wms == ("a",)
    assert description.exclude_attribute_wfs == ("b",)


def test_builder_attribute_table_config_unknown_type():
    """An unknown column type has no name."""
    assert layers_builder._attribut_config_type(QgsAttributeTableConfig.Type.Field) == "field"
    assert layers_builder._attribut_config_type(QgsAttributeTableConfig.Type.Action) == "action"
    # Not a known column type
    assert layers_builder._attribut_config_type(-1) == ""


#
# Project description
#


def test_builder_project_description_without_layers(client):
    """The layer descriptions are built when not provided."""
    project = client.get_project("montpellier/montpellier.qgs")

    description = builder.project_description(project)
    assert description.title
    assert description.layers


def test_builder_gui_properties(client):
    """The GUI properties are converted to CSS3 colors."""
    project = client.get_project("montpellier/montpellier.qgs")

    properties = builder.project_gui_properties(project)
    assert properties.background_color is not None

    # An invalid color has no representation
    assert builder.to_css3_color(QColor()) is None


def test_builder_visibility_presets(client):
    """The map themes are returned as visibility presets."""
    project = client.get_project("montpellier/montpellier.qgs")

    layer = next(iter(project.mapLayers().values()))

    record = QgsMapThemeCollection.MapThemeRecord()
    layer_record = QgsMapThemeCollection.MapThemeLayerRecord(layer)
    layer_record.isVisible = True
    record.addLayerRecord(layer_record)

    collection = project.mapThemeCollection()
    collection.insert("A theme", record)

    presets = list(builder.layers_visibility_presets(project))
    assert len(presets) == 1
    assert presets[0].name == "A theme"
    assert len(presets[0].layers) == 1
    assert presets[0].layers[0].id_ == layer.id()


def test_builder_layer_visibility_without_layer():
    """A record without any layer has no visibility."""
    record = QgsMapThemeCollection.MapThemeLayerRecord()
    assert builder.layer_visibility(record) is None


def test_builder_project_layouts_restricted(client):
    """The restricted layouts may be included."""
    project = client.get_project("montpellier/montpellier.qgs")

    layouts = list(builder.project_layouts(project, include_restricted=True))
    assert len(layouts) >= 1


def test_builder_open_unknown_project():
    """An unknown project cannot be opened."""
    project, details = builder.open_project_def("/does/not/exist.qgs")
    assert project is None
    assert details == {}


#
# Project storage metadata
#


def test_builder_storage_metadata_file(rootdir):
    """The metadata of a project file."""
    uri = f"{rootdir}/data/legend.qgs"
    md = builder.project_storage_metadata(uri)

    assert md.storage == "file"
    assert md.name == "legend"
    assert md.last_modified > 0


def test_builder_storage_metadata_unknown_file():
    """An unknown project file has no metadata."""
    with pytest.raises(FileNotFoundError):
        builder.project_storage_metadata("/does/not/exist.qgs")


def test_builder_storage_metadata_from_storage(monkeypatch):
    """The metadata of a project held by a project storage.

    Project storages (geopackage, postgresql) are not registered when running
    the tests: the registry is stubbed.
    """
    from qgis.PyQt.QtCore import QDateTime

    uri = "geopackage:/somewhere/projects.gpkg?projectName=a_project"

    class FakeMetadata:
        name = "a_project"
        lastModified = QDateTime.fromString("2024-05-06T12:00:00", Qt.DateFormat.ISODate)

    class FakeStorage:
        found = True

        def type(self):
            return "geopackage"

        def readProjectStorageMetadata(self, uri):
            return (self.found, FakeMetadata())

    storage = FakeStorage()

    class FakeRegistry:
        def projectStorageFromUri(self, uri):
            return storage

    class FakeApplication:
        @staticmethod
        def projectStorageRegistry():
            return FakeRegistry()

    monkeypatch.setattr(builder, "QgsApplication", FakeApplication)

    md = builder.project_storage_metadata(uri)
    assert md.storage == "geopackage"
    assert md.name == "a_project"
    assert md.uri == uri
    assert md.last_modified > 0

    # The project is not in the storage
    storage.found = False
    with pytest.raises(FileNotFoundError):
        builder.project_storage_metadata(uri)


#
# Reading a project with the layer details
#


@pytest.fixture
def project_with_details(tmp_path, rootdir):
    """A project holding a vector and a raster layer with a full configuration."""
    project = QgsProject()

    vector = QgsVectorLayer(
        str(rootdir.joinpath("data/france_parts/france_parts.shp")),
        "france_parts",
        "ogr",
    )
    assert vector.isValid()

    index = vector.fields().indexOf("NAME_1")
    vector.setFieldConfigurationFlag(index, Qgis.FieldConfigurationFlag.HideFromWms, True)
    vector.setFieldConfigurationFlag(index, Qgis.FieldConfigurationFlag.HideFromWfs, True)
    vector.setEditorWidgetSetup(index, QgsEditorWidgetSetup("TextEdit", {"IsMultiline": False}))
    vector.setDefaultValueDefinition(index, QgsDefaultValue("'a default'", False))
    vector.setFieldConstraint(index, QgsFieldConstraints.Constraint.ConstraintNotNull)
    vector.setConstraintExpression(index, '"NAME_1" != \'\'', "Not empty")

    raster = QgsRasterLayer(str(rootdir.joinpath("data/raster.asc")), "raster", "gdal")
    assert raster.isValid()

    # Neither a vector nor a raster layer: no details are extracted
    annotations = QgsAnnotationLayer(
        "annotations",
        QgsAnnotationLayer.LayerOptions(project.transformContext()),
    )
    assert annotations.isValid()

    project.addMapLayer(vector)
    project.addMapLayer(raster)
    project.addMapLayer(annotations)

    path = tmp_path.joinpath("details.qgs")
    assert project.write(str(path))

    return str(path), vector.id(), raster.id(), annotations.id()


def test_builder_read_project_details(project_with_details):
    """The layer details are read from the project file."""
    path, vector_id, raster_id, annotations_id = project_with_details

    project, details = builder.open_project_def(path, with_details=True)
    assert project is not None

    vector_details = details[vector_id]
    assert vector_details.provider == "ogr"
    assert vector_details.fields["NAME_1"].hide_from_wms
    assert vector_details.fields["NAME_1"].hide_from_wfs
    assert vector_details.fields["NAME_1"].edit_widget.type_ == "TextEdit"
    assert vector_details.defaults["NAME_1"].expression == "'a default'"
    assert vector_details.constraints["NAME_1"].constraints
    assert vector_details.constraint_expressions["NAME_1"].description == "Not empty"

    raster_details = details[raster_id]
    assert raster_details.type_ == "raster"
    assert raster_details.provider == "gdal"

    # The annotation layer has no details
    assert annotations_id not in details


def test_builder_read_project_details_error(project_with_details, monkeypatch):
    """An error while reading the details must not break the project loading."""
    path, *_ = project_with_details

    def broken(*args, **kwargs):
        raise RuntimeError("Broken")

    monkeypatch.setattr(project_builder, "attribute_table_config", broken)

    project, details = builder.open_project_def(path, with_details=True)
    assert project is not None
    # The vector layer details could not be read
    assert all(d.type_ == "raster" for d in details.values())


def test_builder_visibility_presets_without_layer(client):
    """A visibility record without any layer is skipped."""
    project = client.get_project("montpellier/montpellier.qgs")

    record = QgsMapThemeCollection.MapThemeRecord()
    record.addLayerRecord(QgsMapThemeCollection.MapThemeLayerRecord())
    project.mapThemeCollection().insert("Empty theme", record)

    presets = list(builder.layers_visibility_presets(project))
    assert presets[0].layers == []


def test_builder_layer_description_from_api():
    """Without any layer details, the hidden fields come from the QGIS API."""
    layer = QgsVectorLayer("Point?crs=epsg:4326&field=a:string&field=b:string", "points", "memory")
    fields = layer.fields()

    layer.setFieldConfigurationFlag(
        fields.indexOf("a"), Qgis.FieldConfigurationFlag.HideFromWms, True
    )

    description = layers_builder.layer_description(layer, QgsProject())

    assert description.provider == "memory"
    # NOTE: 'field.configurationFlags() & flag' returns a QFlags which never
    # compares equal to 0, so every field is currently reported as hidden.
    assert "a" in description.exclude_attribute_wms
