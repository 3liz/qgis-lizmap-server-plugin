"""Build OAPI 3.0  description"""

from typing import (
    Annotated,
    Any,
    Sequence,
    get_origin,
    cast,
)

from pydantic import BaseModel, Json, JsonValue, TypeAdapter

from .schemas import JsonModel
from .routes import ROUTES, RouteDef


JsonAdapter: TypeAdapter = TypeAdapter(JsonValue)


def dump_json(v: JsonValue) -> str:
    return JsonAdapter.dump_json(v).decode()


OAPI_VERSION = "3.0.0"
OAPI_TITLE = "Lizmap-server-api"
OAPI_DESCRIPTION = "Lizmap server api for returning server and Qgis project's informations"

Model = type[BaseModel] | TypeAdapter

_MODELS: list[tuple[str, Model]] = []


# Can be used as decorator
def model(model: Any) -> Any:
    if isinstance(model, type) and issubclass(model, BaseModel):
        _MODELS.append((model.__name__, model))
    elif get_origin(model) is Annotated:
        _MODELS.append((model.__metadata__[0], TypeAdapter(model)))
    else:
        raise ValueError(f"Unsupported type {model}")
    return model


#
# OpenApi document
#
class Tag(JsonModel):
    description: str
    name: str


class Info(JsonModel):
    title: str
    description: str
    version: str


class OpenApiDocument(JsonModel):
    openapi: str = OAPI_VERSION
    paths: dict[str, Json]
    definitions: dict[str, Json]
    tags: Sequence[Tag]
    info: Info


def document(tags: list[Tag], api_version: str) -> OpenApiDocument:
    return OpenApiDocument(
        paths={k: dump_json(v) for k, v in paths(ROUTES).items()},
        definitions={k: dump_json(v) for k, v in schemas().items()},
        tags=tags,
        info=Info(
            description=OAPI_DESCRIPTION,
            title=OAPI_TITLE,
            version=api_version,
        ),
    )


def schemas(ref_template: str = "#/definitions/{model}") -> dict[str, JsonValue]:
    """Build schema definitions dictionnary from models"""
    schema_definitions = {}
    for name, model in _MODELS:
        match model:
            case TypeAdapter():
                schema = model.json_schema(ref_template=ref_template)
            case _:
                schema = model.model_json_schema(ref_template=ref_template)
        # Extract subdefinitions
        defs = cast("dict", schema.pop("$defs", {}))

        schema_definitions.update(defs)
        schema_definitions[name] = schema

    return schema_definitions


class SwaggerError(Exception):
    pass


def paths(routes: list[RouteDef]) -> dict:
    """Extract swagger doc from route handlers"""
    import ruamel.yaml

    yaml = ruamel.yaml.YAML()

    paths: dict[str, dict[str, str]] = {}
    for route in routes:
        if not route.doc:
            continue
        try:
            paths.setdefault(route.path, {})[route.method] = yaml.load(route.fn.__doc__)
        except (ruamel.yaml.scanner.ScannerError, ruamel.yaml.parser.ParserError) as err:
            raise SwaggerError(f"Yaml error for {route.fn}: {err}") from None

    return paths


if __name__ == "__main__":
    """Generate OpenAPI JSON schema"""
    from lizmap_server.api import swagger
    from lizmap_server.api import handlers  # noqa F401

    doc = swagger.document(
        api_version="1",
        tags=[
            swagger.Tag(name="project", description="Project's informations"),
            swagger.Tag(name="layout", description="Project's layout"),
        ],
    )

    print(doc.model_dump_json(indent=4))  # noqa T201
