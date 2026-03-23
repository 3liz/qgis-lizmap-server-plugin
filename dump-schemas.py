
from lizmap_server.api.schemas import (
    ProjectDescription,
    ProjectSummary,
    VectorLayerDetails,
    LayoutSummary,
    LayoutDescription,
)

from lizmap_server.api.schemas.models import JsonDict


def dump_schema(name: str, schema: JsonDict):
    
    if not schema: 
        return

    defs = schema.pop('$defs', None)
    with open(f"schemas/{name}.json", 'w') as fp:
        print("Writing", name, "schema") 
        fp.write(json.dumps(schema, indent=2))

    if defs:
        for n, schema in defs.items():
            dump_schema(n, schema)


if __name__ == '__main__':
    import json

    for model in (
        ProjectDescription,
        ProjectSummary,
        VectorLayerDetails,
        LayoutSummary,
        LayoutDescription,
    ):
        schema = model.model_json_schema(ref_template='./{model}.json')
        dump_schema(model.__name__, schema)
