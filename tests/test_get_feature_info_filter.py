"""Tests for the GetFeatureInfo filter internals."""

import json
import xml.etree.ElementTree as ET

import pytest

from qgis.core import (
    QgsAttributeEditorField,
    QgsEditFormConfig,
    QgsEditorWidgetSetup,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    edit,
)
from qgis.PyQt.QtCore import QByteArray

from lizmap_server.get_feature_info import GetFeatureInfoFilter

XML = """<GetFeatureInfoResponse>
 <Layer name="other_layer">
  <Feature id="1">
   <Attribute name="code" value="z"/>
  </Feature>
 </Layer>
 <NotALayer name="ignored"/>
 <Layer name="points">
  <Feature id="1">
   <Attribute name="code" value="a"/>
  </Feature>
  <Feature id="2">
   <Attribute name="code" value="b"/>
  </Feature>
  <NotAFeature/>
 </Layer>
</GetFeatureInfoResponse>
"""


class FakeRequestHandler:
    """Minimal duck typing of a QgsRequestHandler."""

    def __init__(self, params=None, body=b""):
        self._params = params if params is not None else {}
        self._body = QByteArray(body)
        self.headers = {}

    def parameterMap(self):
        return self._params

    def body(self):
        return self._body

    def clear(self):
        self._body = QByteArray()

    def setResponseHeader(self, name, value):
        self.headers[name] = value

    def appendBody(self, body):
        self._body.append(body)

    def content(self):
        return bytes(self._body).decode()


class FakeServerInterface:
    """Minimal duck typing of a QgsServerInterface."""

    def __init__(self, handler, config_path):
        self._handler = handler
        self._config_path = str(config_path)

    def requestHandler(self):
        return self._handler

    def configFilePath(self):
        return self._config_path


#
# XML parsing
#


def test_gfi_parse_xml():
    """Only the layers and the features with an id are returned."""
    assert list(GetFeatureInfoFilter.parse_xml(XML)) == [
        ("other_layer", "1"),
        ("points", "1"),
        ("points", "2"),
    ]


def _maptips(xml: str) -> dict:
    """Return the maptip of each feature of the XML."""
    root = ET.fromstring(xml)
    maptips = {}
    for layer in root.findall("Layer"):
        for feature in layer.findall("Feature"):
            for attribute in feature.findall("Attribute"):
                if attribute.get("name") == "maptip":
                    maptips[(layer.get("name"), feature.get("id"))] = attribute.get("value")
    return maptips


def test_gfi_append_maptip():
    """The maptip is added to the requested layer and feature only."""
    result = GetFeatureInfoFilter.append_maptip(XML, "points", 2, "A maptip")

    assert _maptips(result) == {("points", "2"): "A maptip"}

    # An unknown layer or feature leaves the XML untouched
    assert _maptips(GetFeatureInfoFilter.append_maptip(XML, "unknown", 1, "A maptip")) == {}
    assert _maptips(GetFeatureInfoFilter.append_maptip(XML, "points", 42, "A maptip")) == {}


def test_gfi_replace_existing_maptip():
    """An existing maptip attribute is replaced."""
    xml = """<GetFeatureInfoResponse>
     <Layer name="points">
      <Feature id="1">
       <Attribute name="maptip" value="Old"/>
      </Feature>
     </Layer>
    </GetFeatureInfoResponse>
    """
    result = GetFeatureInfoFilter.append_maptip(xml, "points", 1, "New")
    assert _maptips(result) == {("points", "1"): "New"}


#
# Feature list
#


@pytest.fixture
def project():
    """A clean QGIS project."""
    instance = QgsProject.instance()
    instance.clear()
    yield instance
    instance.clear()


def _layer(tmp_path, name="points"):
    """A geopackage layer with a drag&drop form."""
    memory = QgsVectorLayer("Point?crs=epsg:4326&field=code:string", name, "memory")
    with edit(memory):
        for value in ("a", "b"):
            feature = QgsFeature(memory.fields())
            feature.setGeometry(QgsGeometry.fromWkt("POINT(1 1)"))
            feature.setAttributes([value])
            assert memory.addFeature(feature)

    path = tmp_path.joinpath(f"{name}.gpkg")
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    error, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
        memory, str(path), memory.transformContext(), options
    )
    assert error == QgsVectorFileWriter.WriterError.NoError

    layer = QgsVectorLayer(f"{path}|layername={name}", name, "ogr")
    assert layer.isValid()

    # A drag & drop form with a single field
    config = layer.editFormConfig()
    config.setLayout(QgsEditFormConfig.EditorLayout.TabLayout)
    root = config.invisibleRootContainer()
    root.addChildElement(QgsAttributeEditorField("code", layer.fields().indexOf("code"), root))
    layer.setEditFormConfig(config)

    return layer


CFG = {
    "layers": {
        "points": {
            "popup": "True",
            "popupSource": "form",
        },
    },
}


def _feature_list(project, cfg, xml):
    return GetFeatureInfoFilter.feature_list_to_replace(
        cfg,
        project,
        project.relationManager(),
        xml,
        "BOOTSTRAP5",
    )


def test_gfi_feature_list(project, tmp_path):
    """The features with a form popup are returned."""
    layer = _layer(tmp_path)
    project.addMapLayer(layer)

    results = _feature_list(project, CFG, XML)
    assert len(results) == 2
    assert all(r.layer is layer for r in results)
    assert "popup_lizmap_dd" in results[0].expression


def test_gfi_feature_list_css(project, tmp_path):
    """The CSS is included for the older Lizmap Web Client versions."""
    layer = _layer(tmp_path)
    project.addMapLayer(layer)

    results = GetFeatureInfoFilter.feature_list_to_replace(
        CFG, project, project.relationManager(), XML, ""
    )
    assert "<style>" in results[0].expression


def test_gfi_feature_list_not_a_vector_layer(project):
    """A layer which is not a vector layer is skipped."""
    assert _feature_list(project, CFG, XML) == []


def test_gfi_feature_list_without_layers_section(project, tmp_path):
    """A CFG file without any 'layers' section is skipped."""
    project.addMapLayer(_layer(tmp_path))
    assert _feature_list(project, {}, XML) == []


def test_gfi_feature_list_layer_not_configured(project, tmp_path):
    """A layer without any configuration is skipped."""
    project.addMapLayer(_layer(tmp_path))
    assert _feature_list(project, {"layers": {"another": {}}}, XML) == []


def test_gfi_feature_list_without_popup(project, tmp_path):
    """A layer without any popup is skipped."""
    project.addMapLayer(_layer(tmp_path))
    cfg = {"layers": {"points": {"popup": "False"}}}
    assert _feature_list(project, cfg, XML) == []


def test_gfi_feature_list_not_a_form_popup(project, tmp_path):
    """A layer whose popup is not a form is skipped."""
    project.addMapLayer(_layer(tmp_path))
    cfg = {"layers": {"points": {"popup": "True", "popupSource": "auto"}}}
    assert _feature_list(project, cfg, XML) == []


def test_gfi_feature_list_not_a_drag_and_drop_form(project, tmp_path):
    """A layer without a drag&drop form layout is skipped."""
    layer = _layer(tmp_path)
    config = layer.editFormConfig()
    config.setLayout(QgsEditFormConfig.EditorLayout.GeneratedLayout)
    layer.setEditFormConfig(config)
    project.addMapLayer(layer)

    assert _feature_list(project, CFG, XML) == []


#
# responseComplete
#


PARAMS = {
    "SERVICE": "WMS",
    "REQUEST": "GETFEATUREINFO",
    "INFO_FORMAT": "TEXT/XML",
}


@pytest.fixture
def make_filter(client, tmp_path, project):
    """Build a GetFeatureInfo filter with a Lizmap project."""

    def _make(cfg=CFG, params=None, xml=XML, with_project=True, with_cfg=True):
        qgs = tmp_path.joinpath("project.qgs")
        if with_project:
            qgs.write_text("")
        if with_cfg:
            tmp_path.joinpath("project.qgs.cfg").write_text(json.dumps(cfg))

        handler = FakeRequestHandler(params if params is not None else dict(PARAMS), xml.encode())
        gfi = GetFeatureInfoFilter(client.server.serverInterface())
        gfi.serverInterface = lambda: FakeServerInterface(handler, qgs)
        return gfi, handler

    return _make


@pytest.mark.parametrize(
    "params",
    [
        {"SERVICE": "WFS"},
        {"REQUEST": "GETCAPABILITIES"},
        {"INFO_FORMAT": "TEXT/HTML"},
    ],
)
def test_gfi_skipped_requests(make_filter, params, tmp_path):
    """Only the XML GetFeatureInfo requests are processed."""
    gfi, handler = make_filter(params={**PARAMS, **params})

    assert gfi.responseComplete() is None
    assert handler.content() == XML


def test_gfi_without_project_file(make_filter):
    """A project which is not a file is skipped."""
    gfi, _ = make_filter(with_project=False)
    assert gfi.responseComplete() is None


def test_gfi_without_lizmap_config(make_filter):
    """A project without any Lizmap configuration is skipped."""
    gfi, _ = make_filter(with_cfg=False)
    assert gfi.responseComplete() is None


def test_gfi_no_feature(make_filter, project, tmp_path):
    """Without any feature, the response is left untouched."""
    project.addMapLayer(_layer(tmp_path))
    gfi, handler = make_filter(xml="<GetFeatureInfoResponse/>")

    assert gfi.responseComplete() is None
    assert handler.content() == "<GetFeatureInfoResponse/>"


def test_gfi_invalid_widget_config(make_filter, project, tmp_path):
    """An invalid widget configuration returns the default response."""
    layer = _layer(tmp_path)
    index = layer.fields().indexOf("code")
    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("ValueRelation", {}))
    project.addMapLayer(layer)

    gfi, handler = make_filter()

    assert gfi.responseComplete() is None
    assert handler.content() == XML


def test_gfi_error_while_reading(make_filter, project, tmp_path, monkeypatch):
    """An error while reading the XML must be re-raised."""
    project.addMapLayer(_layer(tmp_path))

    def broken(*args, **kwargs):
        raise RuntimeError("Broken")

    monkeypatch.setattr(GetFeatureInfoFilter, "feature_list_to_replace", staticmethod(broken))

    gfi, _ = make_filter()
    with pytest.raises(RuntimeError, match="Broken"):
        gfi.responseComplete()


def test_gfi_replace_maptip(make_filter, project, tmp_path):
    """The maptip is replaced by the drag&drop form."""
    project.addMapLayer(_layer(tmp_path))

    gfi, handler = make_filter()
    gfi.responseComplete()

    assert handler.headers["Content-Type"] == "text/xml"
    assert "popup_lizmap_dd" in handler.content()


def test_gfi_unknown_feature(make_filter, project, tmp_path):
    """A feature which does not exist is skipped."""
    project.addMapLayer(_layer(tmp_path))

    xml = """<GetFeatureInfoResponse>
     <Layer name="points">
      <Feature id="4242">
       <Attribute name="code" value="a"/>
      </Feature>
     </Layer>
    </GetFeatureInfoResponse>
    """
    gfi, handler = make_filter(xml=xml)
    gfi.responseComplete()

    assert "maptip" not in handler.content()


def test_gfi_empty_maptip(make_filter, project, tmp_path, monkeypatch):
    """A maptip which cannot be evaluated is skipped."""
    import lizmap_server.get_feature_info as module

    class EmptyExpression(module.QgsExpression):
        @staticmethod
        def replaceExpressionText(text, context, distance_area):
            return ""

    monkeypatch.setattr(module, "QgsExpression", EmptyExpression)

    project.addMapLayer(_layer(tmp_path))

    gfi, handler = make_filter()
    gfi.responseComplete()

    assert "maptip" not in handler.content()


def test_gfi_empty_xml(make_filter, project, tmp_path, monkeypatch):
    """An empty XML must not replace the response."""
    project.addMapLayer(_layer(tmp_path))

    monkeypatch.setattr(GetFeatureInfoFilter, "append_maptip", staticmethod(lambda *args: ""))

    gfi, handler = make_filter()
    assert gfi.responseComplete() is None
    assert handler.content() == XML


def test_gfi_error_while_rewriting(make_filter, project, tmp_path, monkeypatch):
    """An error while rewriting the XML must be re-raised."""
    project.addMapLayer(_layer(tmp_path))

    def broken(*args, **kwargs):
        raise RuntimeError("Broken")

    monkeypatch.setattr(GetFeatureInfoFilter, "append_maptip", staticmethod(broken))

    gfi, _ = make_filter()
    with pytest.raises(RuntimeError, match="Broken"):
        gfi.responseComplete()


def test_gfi_with_wkt_geometry(make_filter, project, tmp_path):
    """The geometry is kept when the project asks for the WKT geometry."""
    project.addMapLayer(_layer(tmp_path))
    project.writeEntry("WMSAddWktGeometry", "/", "true")

    gfi, handler = make_filter()
    gfi.responseComplete()

    assert "popup_lizmap_dd" in handler.content()
