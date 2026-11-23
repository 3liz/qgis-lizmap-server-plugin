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

# Functions reading the features of other layers, without the access control
# of these layers (filter by login, Lizmap ACL...). They are not allowed in the
# expressions sent by the client to filter the features, e.g. the FILTER of
# the VirtualFields request. They are still allowed in the project expressions.
CROSS_LAYER_EXPRESSIONS = {
    "aggregate",
    "get_feature",
    "get_feature_by_id",
    "load_layer",
    "overlay_contains",
    "overlay_crosses",
    "overlay_disjoint",
    "overlay_equals",
    "overlay_intersects",
    "overlay_nearest",
    "overlay_touches",
    "overlay_within",
    "relation_aggregate",
}

# While list usable with SAFE_VIRTUALS parameters
SAFE_EXPRESSIONS = {
    "area",
    "$area",
    "display_expression",
    "format_date",
    "now",
    "represent_value",
    "round",
}
