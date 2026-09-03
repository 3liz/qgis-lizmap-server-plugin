"""Tests for the OpenAPI document generation and the schema helpers."""

import json

import pytest

from pydantic import TypeAdapter

from lizmap_server.api import handlers, swagger  # (importing handlers registers the models)
from lizmap_server.api.schemas import ProjectDescription
from lizmap_server.api.schemas.models import (
    JsonModel,
    fix_nullable_schema,
    fix_optional_schema,
    one_of,
    remove_auto_title,
)
from lizmap_server.api.schemas.relations import Relation


def test_swagger_one_of():
    """'anyOf' must be replaced by 'oneOf'."""
    schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
    one_of(schema)
    assert schema == {"oneOf": [{"type": "string"}, {"type": "integer"}]}

    # Nothing to do
    schema = {"type": "string"}
    one_of(schema)
    assert schema == {"type": "string"}


def test_swagger_fix_optional_schema():
    """The 'anyOf' of an optional field must be flattened."""
    schema = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
    fix_optional_schema(schema)
    assert schema == {"type": "string"}

    schema = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    fix_nullable_schema(schema)
    assert schema == {"type": "string", "nullable": True}


def test_swagger_remove_auto_title():
    """The auto generated titles must be removed from the schema."""
    schema = {
        "type": "object",
        "properties": {
            "some_field": {"title": "Some Field", "type": "string"},
            "other": {"title": "A custom title", "type": "string"},
            "choice": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {"inner": {"title": "Inner", "type": "string"}},
                    },
                ],
            },
        },
        "$defs": {
            "sub_model": {
                "title": "Sub Model",
                "type": "object",
                "properties": {"nested": {"title": "Nested", "type": "integer"}},
            },
        },
    }
    remove_auto_title(schema)

    props = schema["properties"]
    assert "title" not in props["some_field"]
    assert props["other"]["title"] == "A custom title"
    assert "title" not in props["choice"]["oneOf"][0]["properties"]["inner"]
    assert "title" not in schema["$defs"]["sub_model"]
    assert "title" not in schema["$defs"]["sub_model"]["properties"]["nested"]

    # Nothing matches
    schema = {"type": "string"}
    remove_auto_title(schema)
    assert schema == {"type": "string"}


def test_swagger_json_model_schema():
    """The json model must remove the auto generated titles."""
    schema = ProjectDescription.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_swagger_relation_schema():
    """The relation schema must be usable."""
    relation = Relation(
        id="relation_id",
        name="A relation",
        referencing_layer="layer_a",
        referencing_field="field_a",
        referenced_field="field_b",
        strength="Association",
    )
    dump = json.loads(relation.model_dump_json())
    assert dump["id"] == "relation_id"
    assert dump["referencingLayer"] == "layer_a"

    assert "properties" in Relation.model_json_schema()


def test_swagger_model_registration():
    """Only pydantic models and annotated types may be registered."""

    class SomeModel(JsonModel):
        foo: str

    registered = len(swagger._MODELS)
    try:
        assert swagger.model(SomeModel) is SomeModel
        assert swagger._MODELS[-1] == ("SomeModel", SomeModel)
    finally:
        del swagger._MODELS[registered:]

    with pytest.raises(ValueError):
        swagger.model("not a model")


def test_swagger_schemas():
    """The definitions must be built from the registered models."""
    definitions = swagger.schemas()
    assert "ProjectSummaries" in definitions
    assert "ProjectDescription" in definitions

    # Definitions extracted from a TypeAdapter based model
    adapter_names = [name for name, model in swagger._MODELS if isinstance(model, TypeAdapter)]
    for name in adapter_names:
        assert name in definitions


def test_swagger_paths():
    """The paths must be extracted from the handlers docstrings."""
    paths = swagger.paths(handlers.routes.ROUTES)
    assert "/api/v1/projects/list" in paths
    assert paths["/api/v1/projects/list"]["get"]["summary"] == "List projects from PATH"


def test_swagger_paths_invalid_yaml():
    """An invalid yaml docstring must raise a swagger error."""
    from qgis.server import QgsServerRequest

    from lizmap_server.api.routes import RouteDef, build_route

    def handler():
        """
        summary: "unbalanced
          - [
        """

    route = RouteDef(
        me=QgsServerRequest.Method.GetMethod,
        route=build_route("/foo"),
        fn=handler,
        method="get",
        path="/foo",
        doc=True,
    )

    with pytest.raises(swagger.SwaggerError):
        swagger.paths([route])


def test_swagger_document():
    """The whole OpenAPI document must be generated."""
    doc = swagger.document(
        api_version="1",
        tags=[
            swagger.Tag(name="project", description="Project's informations"),
            swagger.Tag(name="layout", description="Project's layout"),
        ],
    )

    content = json.loads(doc.model_dump_json(indent=4))
    assert content["openapi"] == swagger.OAPI_VERSION
    assert content["info"]["version"] == "1"
    assert content["info"]["title"] == swagger.OAPI_TITLE
    assert "/api/v1/projects/list" in content["paths"]
    assert "ProjectSummaries" in content["definitions"]


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_swagger_main(capsys):
    """The module may be run to generate the OpenAPI document."""
    import runpy

    runpy.run_module("lizmap_server.api.swagger", run_name="__main__")

    content = json.loads(capsys.readouterr().out)
    assert content["openapi"] == swagger.OAPI_VERSION
    assert content["info"]["version"] == "1"
    assert [tag["name"] for tag in content["tags"]] == ["project", "layout"]
