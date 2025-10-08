from typing import (
    TypedDict,
)


class Body(TypedDict):
    status: str
    results: list
    errors: list
    features: int


# Some expressions which can be evaluated on the server
ALLOWED_SAFE_EXPRESSIONS = {
    'area',
    '$area',
    'display_expression',
    'format_date',
    'now',
    'represent_value',
    'round',
}

NOT_ALLOWED_EXPRESSION = "'not allowed'"
