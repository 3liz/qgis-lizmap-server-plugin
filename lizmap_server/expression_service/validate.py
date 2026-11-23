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
) -> QgsExpression:
    """Check if an expression as a string has an error or not."""
    expression = QgsExpression(expression_str)
    expression.setGeomCalculator(distance_area)
    expression.setDistanceUnits(project.distanceUnits())
    expression.setAreaUnits(project.areaUnits())

    if expression.hasParserError():
        raise ExpressionError(f'Error "{expression_str}": {expression.parserErrorString()}')

    if not expression.isValid():
        raise ExpressionError(f'Expression not valid "{expression_str}"')

    check_authorized_expression_functions(expression)

    return expression


def check_authorized_expression_functions(exp: QgsExpression):
    """Return Http error 400 if the expression is not allowed"""
    for member in exp.referencedFunctions():
        if member in FORBIDDEN_EXPRESSIONS:
            raise ForbiddenExpressionError(f"Expression function '{member}' is not allowed")


EXPRESSION_RE = re.compile(r"\[%(.*?)%\]", re.MULTILINE | re.DOTALL)


class ExpressionError(Exception):
    pass


class InvalidExpressionError(ExpressionError):
    pass


class EvalExpressionError(ExpressionError):
    pass


class ForbiddenExpressionError(ExpressionError):
    pass


# NOTE: `QgsExpression.replaceExpressionText` is NOT acceptable alone, it is only
# used to format the value of a block once checked:
# - Silence errors
# - Cannot check for unauthorized expression functions


def safe_replace_expression_text(
    expression_str: str,
    context: QgsExpressionContext,
    distance_area: QgsDistanceArea | None,
    errors: list[str] | None = None,
) -> str | None:
    """A safe replacement for qgsExpression::replaceExpressionText

    The original version silence errors and prevent checking for allowed
    safe expression function.

    In strict mode, without an error list, a parser or evaluation error raises
    an exception. Otherwise the error is added to the list and the text has no
    value: None is returned. A forbidden function always raises an exception.

    :param expression_str: The text with expressions between [% and %].
    :param context: The expression context.
    :param distance_area: The calculator of the areas and lengths, or None.
    :param errors: The list receiving the error messages, or None for the strict mode.
    :returns: The text with the expressions replaced by their values, or None if an
        expression is in error in lenient mode.
    """
    # The errors already in the list are not the errors of this text
    errors_count = len(errors) if errors is not None else 0

    def replace(m: re.Match) -> str:
        exp_str = m.group().removeprefix("[%").removesuffix("%]").strip()
        exp = QgsExpression(exp_str)

        # Parser error: raised in strict mode, else listed
        error: ExpressionError | None = None
        if exp.hasParserError():
            error = InvalidExpressionError(f'Error "{exp_str}": {exp.parserErrorString()}')
        elif not exp.isValid():
            error = InvalidExpressionError(f'Expression not valid "{exp_str}"')
        if error is not None:
            if errors is None:
                raise error
            errors.append(str(error))
            return m.group()

        # A forbidden function is never evaluated, even in lenient mode
        check_authorized_expression_functions(exp)

        if distance_area is not None:
            exp.setGeomCalculator(distance_area)

        # Evaluation error: raised in strict mode, else listed
        exp.evaluate(context)
        if exp.hasEvalError():
            error = EvalExpressionError(f"Expression '{exp_str}' evaluation error: {exp.evalErrorString()}")
            if errors is None:
                raise error
            errors.append(str(error))
            return m.group()

        # The checks are done: let QGIS replace this block only, so that the value is
        # formatted as QGIS does (ISO dates, 'true', empty string for a geometry...).
        # The Python value of the result cannot be used: its string is the Python one,
        # e.g. 'PyQt5.QtCore.QDate(2024, 1, 2)' or 'True'.
        if distance_area is not None:
            return QgsExpression.replaceExpressionText(m.group(), context, distance_area)
        return QgsExpression.replaceExpressionText(m.group(), context)

    # Replace all expressions from the string
    text = EXPRESSION_RE.sub(replace, expression_str)

    # Lenient mode: a text with an expression in error has no value
    if errors is not None and len(errors) > errors_count:
        return None
    return text
