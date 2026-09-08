"""Expression validation"""

import re

from qgis.core import (
    QgsDistanceArea,
    QgsExpression,
    QgsExpressionContext,
    QgsProject,
)


from .models import FORBIDDEN_EXPRESSIONS


def check_expression(
    expression_str: str,
    distance_area: QgsDistanceArea,
    project: QgsProject,
) -> tuple[QgsExpression | None, str]:
    """Check if an expression as a string has an error or not."""
    expression = QgsExpression(expression_str)
    expression.setGeomCalculator(distance_area)
    expression.setDistanceUnits(project.distanceUnits())
    expression.setAreaUnits(project.areaUnits())

    if expression.hasParserError():
        return None, f'Error "{expression_str}": {expression.parserErrorString()}'

    if not expression.isValid():
        return None, f'Expression not valid "{expression_str}"'

    unauthorized = check_authorized_expression_functions(expression)
    if unauthorized:
        return None, unauthorized

    return expression, ""


def check_authorized_expression_functions(exp: QgsExpression) -> str | None:
    """Return Http error 400 if the expression is not allowed"""
    for member in exp.referencedFunctions():
        if member in FORBIDDEN_EXPRESSIONS:
            return f"Expression function '{member}' is not allowed"

    return None


EXPRESSION_RE = re.compile(r"\[%(.*?)%\]", re.MULTILINE | re.DOTALL)


class ReplaceExpressionError(Exception):
    pass


class ForbiddenExpressionError(ReplaceExpressionError):
    pass


# NOTE: `QgsExpression.replaceExpressionText` is NOT acceptable:
# - Silence errors
# - Cannot check for unauthorized expression functions


def safe_replace_expression_text(
    expression_str: str,
    context: QgsExpressionContext,
    distance_area: QgsDistanceArea | None,
) -> str:
    """A safe replacement for qgsExpression::replaceExpressionText

    The original version silence errors and prevent checking for allowed
    safe expression function.
    """

    def replace(m: re.Match) -> str:
        exp_str = m.group().removeprefix("[%").removesuffix("%]").strip()
        exp = QgsExpression(exp_str)

        if exp.hasParserError():
            raise ReplaceExpressionError(f'Error "{exp_str}": {exp.parserErrorString()}')

        if not exp.isValid():
            raise ReplaceExpressionError(f'Expression not valid "{exp_str}"')

        unauthorized = check_authorized_expression_functions(exp)
        if unauthorized is not None:
            raise ForbiddenExpressionError(unauthorized)

        if distance_area is not None:
            exp.setGeomCalculator(distance_area)

        result = exp.evaluate(context)
        if exp.hasEvalError():
            raise ReplaceExpressionError(f"Expression '{exp_str}' evaluation error: {exp.evalErrorString()}")

        match result:
            case str():
                return result
            case None:
                return ""
            case _:
                return f"{result}"

    # Replace all expressions from the string
    return EXPRESSION_RE.sub(replace, expression_str)
