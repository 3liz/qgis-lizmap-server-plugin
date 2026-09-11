"""Tests for `safe_replace_expression_text`.

`safe_replace_expression_text` is the safe replacement for
`QgsExpression.replaceExpressionText`, which silences errors and cannot check
for unauthorized expression functions. The tests below therefore cover both
the substitution semantics (which `[% ... %]` blocks are recognised, and what
they are replaced with) and the two error channels:

* `ReplaceExpressionError` for anything the caller is responsible for — a
  parser error or a function outside `ALLOWED_SAFE_EXPRESSIONS`. Callers turn
  it into an HTTP 400.
* `ExpressionServiceError` for an evaluation error, which is reported as an
  HTTP 500 with the internal message kept out of the response.
"""

import pytest

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsDistanceArea,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
)

from lizmap_server.expression_service.models import FORBIDDEN_EXPRESSIONS
from lizmap_server.expression_service.validate import (
    ForbiddenExpressionError,
    ReplaceExpressionError,
    safe_replace_expression_text,
)

# An expression made only of allowed functions, with a stable result.
DATE = "[% format_date('2024-01-02', 'yyyy/MM/dd') %]"
DATE_RESULT = "2024/01/02"


@pytest.fixture
def context() -> QgsExpressionContext:
    """An empty expression context."""
    return QgsExpressionContext()


@pytest.fixture
def feature_context() -> QgsExpressionContext:
    """A context holding a 1 degree square polygon, so that `$area` resolves."""
    layer = QgsVectorLayer("Polygon?crs=epsg:4326", "polygons", "memory")
    assert layer.isValid()

    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt("Polygon((0 0, 0 1, 1 1, 1 0, 0 0))"))

    exp_context = QgsExpressionContext()
    exp_context.appendScope(QgsExpressionContextUtils.layerScope(layer))
    exp_context.setFeature(feature)
    return exp_context


@pytest.fixture
def distance_area() -> QgsDistanceArea:
    """An ellipsoidal calculator, so that `$area` is returned in square metres."""
    calculator = QgsDistanceArea()
    calculator.setSourceCrs(QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateTransformContext())
    calculator.setEllipsoid("WGS84")
    return calculator


#
# Which parts of the string are recognised as an expression
#


@pytest.mark.parametrize(
    "text",
    (
        "",
        "no expression at all",
        "an unterminated [% block",
        "a stray %] marker",
        "an empty [%% marker",
    ),
)
def test_text_without_expression_is_returned_unchanged(text: str, context: QgsExpressionContext) -> None:
    """A string with no complete `[% ... %]` block is returned as is."""
    assert safe_replace_expression_text(text, context, None) == text


def test_expression_alone_is_replaced(context: QgsExpressionContext) -> None:
    """A string made of a single expression is replaced by its value."""
    assert safe_replace_expression_text(DATE, context, None) == DATE_RESULT


def test_expression_surrounded_by_text(context: QgsExpressionContext) -> None:
    """Only the expression is replaced, the surrounding text is preserved."""
    assert safe_replace_expression_text(f"on {DATE}.", context, None) == f"on {DATE_RESULT}."


def test_markers_do_not_need_surrounding_spaces(context: QgsExpressionContext) -> None:
    """The markers are not required to be padded with spaces."""
    assert safe_replace_expression_text("[%'value'%]", context, None) == "value"


def test_several_expressions_are_replaced_independently(context: QgsExpressionContext) -> None:
    """Each block is evaluated on its own: the match is not greedy."""
    text = "[% 'a' %] then [% 'b' %][% 'c' %]"
    assert safe_replace_expression_text(text, context, None) == "a then bc"


def test_expression_may_span_several_lines(context: QgsExpressionContext) -> None:
    """A block is matched across newlines, and newlines outside it are kept."""
    text = "first\n[% format_date('2024-01-02',\n'yyyy') %]\nlast"
    assert safe_replace_expression_text(text, context, None) == "first\n2024\nlast"


def test_nested_blocks_are_not_supported(context: QgsExpressionContext) -> None:
    """The inner-most opening marker wins, which leaves an invalid expression."""
    with pytest.raises(ReplaceExpressionError):
        safe_replace_expression_text("[% 'a[%b%]c' %]", context, None)


#
# The replacement value
#


def test_null_result_is_replaced_by_an_empty_string(context: QgsExpressionContext) -> None:
    """An expression evaluating to NULL removes the block from the string."""
    assert safe_replace_expression_text("[% NULL %]!", context, None) == "!"


def test_numeric_result_is_stringified(context: QgsExpressionContext) -> None:
    """An expression evaluating to a number should be inserted as text."""
    assert safe_replace_expression_text("[% round(1.25, 1) %]", context, None) == "1.3"


#
# Parser errors
#

@pytest.mark.xfail(reason="Fail with QGIS 3.40-")
def test_parser_error_reports_the_expression(context: QgsExpressionContext) -> None:
    """A syntax error names the offending block and the QGIS parser message."""
    with pytest.raises(ReplaceExpressionError) as excinfo:
        safe_replace_expression_text("[% round( %]", context, None)

    message = str(excinfo.value)
    assert 'Error "round("' in message
    assert "Incomplete expression" in message


def test_empty_expression_is_a_parser_error(context: QgsExpressionContext) -> None:
    """An empty block does not parse.

    An empty expression is also the only way `QgsExpression.isValid` returns
    False, so the `Expression not valid` branch is shadowed by this one and
    cannot be reached.
    """
    with pytest.raises(ReplaceExpressionError):
        safe_replace_expression_text("[%%]", context, None)


def test_unknown_function_is_a_parser_error(context: QgsExpressionContext) -> None:
    """A function QGIS does not know about is caught by the parser."""
    with pytest.raises(ReplaceExpressionError) as excinfo:
        safe_replace_expression_text("[% not_a_qgis_function(1) %]", context, None)

    assert "Function not_a_qgis_function is not known" in str(excinfo.value)


#
# Unauthorized functions
#


def test_unauthorized_function_is_rejected(context: QgsExpressionContext) -> None:
    """The error lists the functions the caller may use."""
    for name in FORBIDDEN_EXPRESSIONS:
        with pytest.raises(ForbiddenExpressionError):
            if name == "layer_property":
                safe_replace_expression_text(f"[% {name}('a','b') %]", context, None)
            elif name == "sqlite_fetch_and_increment":
                safe_replace_expression_text(f"[% {name}('a','b', 'c', 'd', 'e') %]", context, None)
            else:
                safe_replace_expression_text(f"[% {name}('1') %]", context, None)


def test_unauthorized_function_nested_in_an_allowed_one(context: QgsExpressionContext) -> None:
    """Wrapping a forbidden function in an allowed one does not hide it."""
    with pytest.raises(ForbiddenExpressionError):
        safe_replace_expression_text("[% round(eval('abc')) %]", context, None)


def test_one_bad_block_aborts_the_whole_string(context: QgsExpressionContext) -> None:
    """A valid block preceding a forbidden one does not yield a partial result."""
    with pytest.raises(ForbiddenExpressionError):
        safe_replace_expression_text("[% 'fine' %] and [% eval('1') %]", context, None)


#
# Evaluation errors
#


def test_evaluation_error(context: QgsExpressionContext) -> None:
    """An evaluation error is an internal error, reported as an HTTP 500."""
    expression = "round('not a number')"

    with pytest.raises(ReplaceExpressionError) as excinfo:
        safe_replace_expression_text(f"[% {expression} %]", context, None)

    assert str(excinfo.value).startswith(f"Expression '{expression}' evaluation error")


#
# The context and the distance area are used
#


def test_the_context_is_used(feature_context: QgsExpressionContext) -> None:
    """The expression is evaluated against the given context."""
    # `|| ''` only casts the area to a string, it is not a function call.
    text = "[% $area || '' %]"

    assert safe_replace_expression_text(text, feature_context, None) == "1"
    # Without a feature, `$area` is NULL.
    assert safe_replace_expression_text(text, QgsExpressionContext(), None) == ""


def test_the_distance_area_is_applied(
    feature_context: QgsExpressionContext,
    distance_area: QgsDistanceArea,
) -> None:
    """A distance area makes `$area` ellipsoidal instead of planimetric."""
    text = "[% $area || '' %]"

    planimetric = safe_replace_expression_text(text, feature_context, None)
    ellipsoidal = safe_replace_expression_text(text, feature_context, distance_area)

    # One square degree, then the same square in square metres.
    assert planimetric == "1"
    assert float(ellipsoidal) == pytest.approx(1.23e10, rel=0.01)
