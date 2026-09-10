from typing import (
    TypedDict,
)


class Body(TypedDict):
    status: str
    results: list
    errors: list
    features: int


# A curated list of QgsExpression functions that
# are unsafe to be called from the server in any case
FORBIDDEN_EXPRESSIONS = {
    "base_file_name",
    "decode_uri",
    "env",
    "eval",
    "eval_template",
    "exif",
    "exif_geotag",
    "file_exists",
    "file_name",
    "file_path",
    "file_size",
    "file_suffix",
    "is_directory",
    "is_file",
    "layer_property",
    "sqlite_fetch_and_increment",
}

# While list usable with SAFE_VIRTUALS parameters
SAFE_EXPRESSIONS = {
    "area",
    "$area",
    "display_expression",
    "format_date",
    "now",
    "represent_values",
    "round",
}
