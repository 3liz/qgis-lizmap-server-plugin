__copyright__ = 'Copyright 2025, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

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
