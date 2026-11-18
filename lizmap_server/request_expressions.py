"""Check the expressions sent in the OGC requests.

QGIS Server evaluates some parameters as QGIS expressions: the WFS EXP_FILTER,
the functions of the OGC filters (WFS FILTER or POST body) and the expressions
between [% and %] of the labels of a WMS GetPrint request. These expressions
can be sent by anyone, and some functions read the server environment or the
features of other layers, without their access control.
"""

import html
import re

from typing import (
    Dict,
    Optional,
)
from urllib.parse import unquote_plus

from .expression_service.models import CROSS_LAYER_EXPRESSIONS, FORBIDDEN_EXPRESSIONS

# Functions not allowed in the expressions of the OGC requests
FORBIDDEN_REQUEST_FUNCTIONS = FORBIDDEN_EXPRESSIONS | CROSS_LAYER_EXPRESSIONS

# The longest names first, so that a name is not matched by one of its prefixes
_FUNCTION_NAMES = "|".join(
    re.escape(name) for name in sorted(FORBIDDEN_REQUEST_FUNCTIONS, key=len, reverse=True)
)

# What can be put between a function name and its parenthesis in a QGIS expression:
# whitespaces and comments
_SEPARATOR = r"(?:\s|/\*.*?\*/|--[^\n]*(?:\n|$))*"

# A call of a forbidden function in a QGIS expression. The function names are case
# insensitive. A string literal containing such a call is also matched: it is
# rejected too, which is safer than parsing the expression in the same way as QGIS.
FUNCTION_CALL_RE = re.compile(rf"\b({_FUNCTION_NAMES}){_SEPARATOR}\(", re.IGNORECASE | re.DOTALL)

# A forbidden function in an OGC filter, e.g. <ogc:Function name="aggregate">
OGC_FUNCTION_RE = re.compile(
    rf"<(?:[\w.-]+:)?Function\b[^>]*\bname\s*=\s*([\"'])\s*({_FUNCTION_NAMES})\s*\1",
    re.IGNORECASE,
)

# The expressions of a text, as replaced by QGIS in the labels
EXPRESSION_BLOCK_RE = re.compile(r"\[%(.*?)%\]", re.DOTALL)

# Services which are not checked: they check their own expressions
UNCHECKED_SERVICES = ("EXPRESSION", "LIZMAP")


def forbidden_function_in_expression(expression: str) -> Optional[str]:
    """Find a forbidden function called in a QGIS expression.

    :param expression: The QGIS expression, e.g. the EXP_FILTER parameter.
    :returns: The name of the first forbidden function found, or None.
    """
    match = FUNCTION_CALL_RE.search(expression)
    return match.group(1).lower() if match else None


def forbidden_function_in_text(text: str) -> Optional[str]:
    """Find a forbidden function in a text which may contain expressions or OGC filters.

    The expressions between [% and %] are evaluated by QGIS in the labels of the
    layouts, and the functions of the OGC filters are evaluated as QGIS functions.
    The XML entities are decoded first, as an XML parser would do.

    :param text: The text, e.g. a parameter value or the body of a request.
    :returns: The name of the first forbidden function found, or None.
    """
    # Functions of the OGC filters
    match = OGC_FUNCTION_RE.search(html.unescape(text))
    if match:
        return match.group(2).lower()

    # Expressions of the labels
    for block in EXPRESSION_BLOCK_RE.finditer(text):
        name = forbidden_function_in_expression(block.group(1))
        if name:
            return name

    return None


def forbidden_function_in_request(params: Dict[str, str], body: str = "") -> Optional[str]:
    """Find a forbidden function in the parameters and the body of an OGC request.

    :param params: The request parameters.
    :param body: The request body, e.g. a WFS GetFeature XML document.
    :returns: The name of the first forbidden function found, or None.
    """
    # The services with their own checks are not checked here
    upper_params = {key.upper(): value for key, value in params.items()}
    if upper_params.get("SERVICE", "").upper() in UNCHECKED_SERVICES:
        return None

    # The EXP_FILTER is a QGIS expression, or a list of expressions
    name = forbidden_function_in_expression(upper_params.get("EXP_FILTER", ""))
    if name:
        return name

    # Any parameter can be a label of a layout or an OGC filter
    for value in upper_params.values():
        name = forbidden_function_in_text(value)
        if name:
            return name

    # The body is also checked as an URL encoded form
    if body:
        return forbidden_function_in_text(body) or forbidden_function_in_text(unquote_plus(body))

    return None
