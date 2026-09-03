"""Tests for the error paths of the EXPRESSION service."""

from urllib.parse import quote

import pytest

from qgis.core import QgsExpression
from qgis.server import (
    QgsBufferServerRequest,
    QgsBufferServerResponse,
    QgsServerRequest,
)

from .utils import PROJECT_FILE, _build_query_string, _check_request

LAYER = "france_parts"


def _query(**kwargs) -> str:
    params = {"SERVICE": "EXPRESSION", "MAP": PROJECT_FILE}
    params.update(kwargs)
    return _build_query_string(params)


def _bad_request(client, **kwargs):
    rv = client.get(_query(**kwargs), PROJECT_FILE)
    body = _check_request(rv, http_code=400)
    assert body["status"] == "fail"
    assert body["code"] == "Bad request"
    return body


#
# Service
#


def test_expression_unknown_request(client):
    """An unknown REQUEST must be rejected."""
    body = _bad_request(client, REQUEST="Unknown")
    assert body["message"] == "Invalid REQUEST parameter 'UNKNOWN'"


def test_expression_method_not_allowed(client):
    """Only GET and POST are supported."""
    from lizmap_server.exception import ExpressionServiceError
    from lizmap_server.expression_service import ExpressionService

    service = ExpressionService(client.server.serverInterface())
    assert service.name() == "EXPRESSION"
    assert service.version() == "1.0.0"
    assert service.allowMethod(QgsServerRequest.Method.GetMethod)
    assert not service.allowMethod(QgsServerRequest.Method.DeleteMethod)

    request = QgsBufferServerRequest(
        _query(REQUEST="Evaluate", LAYER=LAYER),
        QgsServerRequest.Method.DeleteMethod,
        {},
        None,
    )
    response = QgsBufferServerResponse()
    project = client.get_project(PROJECT_FILE)

    with pytest.raises(ExpressionServiceError) as excinfo:
        service.executeRequest(request, response, project)

    assert excinfo.value.response_code == 405


def test_expression_internal_error(client, monkeypatch):
    """An unexpected error must be reported as an internal error."""
    from lizmap_server.expression_service import service

    def broken(*args, **kwargs):
        raise RuntimeError("Something went wrong")

    monkeypatch.setattr(service, "evaluate", broken)

    rv = client.get(_query(REQUEST="Evaluate", LAYER=LAYER), PROJECT_FILE)
    body = _check_request(rv, http_code=500)
    assert body["code"] == "Internal server error"
    assert body["message"] == "Internal 'lizmap' service error"


#
# Evaluate
#


def test_expression_evaluate_malformed_expressions(client):
    """A malformed EXPRESSIONS json must be rejected."""
    body = _bad_request(client, REQUEST="Evaluate", LAYER=LAYER, EXPRESSIONS="{not json}")
    assert body["message"] == "Invalid 'Evaluate' REQUEST EXPRESSIONS: malformed JSON"


def test_expression_evaluate_scalar_expressions(client):
    """EXPRESSIONS which is neither a list nor an object evaluates nothing."""
    rv = client.get(_query(REQUEST="Evaluate", LAYER=LAYER, EXPRESSIONS="1"), PROJECT_FILE)
    body = _check_request(rv)
    assert body["status"] == "success"
    assert body["results"] == [{}]


def test_expression_evaluate_invalid_expression(client, monkeypatch):
    """An expression which is not valid must be reported."""
    from lizmap_server.expression_service import request_evaluate

    class NeverValid(QgsExpression):
        def isValid(self):
            return False

    monkeypatch.setattr(request_evaluate, "QgsExpression", NeverValid)

    body = _bad_request(
        client,
        REQUEST="Evaluate",
        LAYER=LAYER,
        EXPRESSIONS='{{"a":"{}"}}'.format(quote("1 + 1", safe="")),
    )
    assert "Expression not valid" in body["message"]


def test_expression_evaluate_eval_error(client):
    """An expression failing at evaluation must be reported in the errors."""
    rv = client.get(
        _query(
            REQUEST="Evaluate",
            LAYER=LAYER,
            EXPRESSIONS='{{"a":"{}"}}'.format(quote("to_int('abc')", safe="")),
        ),
        PROJECT_FILE,
    )
    body = _check_request(rv)
    assert body["results"] == [{"a": None}]
    assert body["errors"][0]["a"] == "Cannot convert 'abc' to int"


def test_expression_evaluate_eval_error_with_feature(client):
    """An expression failing at evaluation on a feature must be reported."""
    feature = '{"type":"Feature", "geometry": null, "properties": {"prop0": "value0"}}'
    rv = client.get(
        _query(
            REQUEST="Evaluate",
            LAYER=LAYER,
            EXPRESSIONS='{{"a":"{}"}}'.format(quote("to_int('abc')", safe="")),
            FEATURE=feature,
        ),
        PROJECT_FILE,
    )
    body = _check_request(rv)
    assert body["features"] == 1
    assert body["results"] == [{"a": None}]
    assert body["errors"][0]["a"] == "Cannot convert 'abc' to int"


def test_expression_evaluate_features_not_a_list(client):
    """FEATURES must be a non empty list."""
    body = _bad_request(
        client,
        REQUEST="Evaluate",
        LAYER=LAYER,
        EXPRESSIONS='{{"a":"{}"}}'.format(quote("1", safe="")),
        FEATURES='{"type": "Feature"}',
    )
    assert "are not well formed" in body["message"]


def test_expression_evaluate_no_feature_parsed(client, monkeypatch):
    """Features which cannot be parsed must be reported."""
    from lizmap_server.expression_service import request_evaluate

    monkeypatch.setattr(request_evaluate, "QgsJsonUtils_stringToFeatureList", lambda *args: [])

    body = _bad_request(
        client,
        REQUEST="Evaluate",
        LAYER=LAYER,
        EXPRESSIONS='{{"a":"{}"}}'.format(quote("1", safe="")),
        FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "not GeoJSON features array provided" in body["message"]


#
# ReplaceExpressionText
#


def test_expression_replace_malformed_strings(client):
    """A malformed STRINGS json must be rejected."""
    body = _bad_request(client, REQUEST="ReplaceExpressionText", LAYER=LAYER, STRINGS="{not json}")
    assert "are not well formed" in body["message"]


def test_expression_replace_scalar_strings(client):
    """STRINGS which is neither a list nor an object replaces nothing."""
    rv = client.get(_query(REQUEST="ReplaceExpressionText", LAYER=LAYER, STRINGS="1"), PROJECT_FILE)
    body = _check_request(rv)
    assert body["results"] == [{}]


def test_expression_replace_features_not_a_list(client):
    """FEATURES must be a non empty list."""
    body = _bad_request(
        client,
        REQUEST="ReplaceExpressionText",
        LAYER=LAYER,
        STRINGS='["{}"]'.format(quote("[% 1 + 1 %]", safe="")),
        FEATURES='{"type": "Feature"}',
    )
    assert "are not well formed" in body["message"]


def test_expression_replace_no_feature_parsed(client, monkeypatch):
    """Features which cannot be parsed must be reported."""
    from lizmap_server.expression_service import request_replaceexpressiontext

    monkeypatch.setattr(
        request_replaceexpressiontext, "QgsJsonUtils_stringToFeatureList", lambda *args: None
    )

    body = _bad_request(
        client,
        REQUEST="ReplaceExpressionText",
        LAYER=LAYER,
        STRINGS='["{}"]'.format(quote("[% 1 + 1 %]", safe="")),
        FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "not GeoJSON features array provided" in body["message"]


#
# VirtualFields
#


def test_expression_virtual_fields_missing_layer(client):
    """The LAYER parameter is mandatory."""
    body = _bad_request(client, REQUEST="VirtualFields")
    assert body["message"] == "Invalid 'VirtualFields' REQUEST: LAYER parameter is mandatory"


def test_expression_virtual_fields_unknown_layer(client):
    """The layer must exist in the project."""
    body = _bad_request(client, REQUEST="VirtualFields", LAYER="UNKNOWN")
    assert body["message"].startswith("Invalid LAYER parameter for 'VirtualFields'")


def test_expression_virtual_fields_missing_virtuals(client):
    """The VIRTUALS parameter is mandatory."""
    body = _bad_request(client, REQUEST="VirtualFields", LAYER=LAYER)
    assert body["message"] == "Invalid 'VirtualFields' REQUEST: VIRTUALS parameter is mandatory"


def test_expression_virtual_fields_virtuals_not_an_object(client):
    """The VIRTUALS parameter must be a json object."""
    body = _bad_request(client, REQUEST="VirtualFields", LAYER=LAYER, VIRTUALS="[1]")
    assert "not well formed" in body["message"]


def test_expression_virtual_fields_expression_errors(client):
    """Invalid expressions must be reported."""
    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS='{{"a":"{}"}}'.format(quote("foobar(", safe="")),
    )
    assert "Invalid VIRTUALS or SAFE_VIRTUALS" in body["message"]

    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS='{{"a":"{}"}}'.format(quote("1", safe="")),
        SAFE_VIRTUALS='{{"b":"{}"}}'.format(quote("foobar(", safe="")),
    )
    assert "Invalid VIRTUALS or SAFE_VIRTUALS" in body["message"]


def test_expression_virtual_fields_invalid_expression(client, monkeypatch):
    """An expression which is not valid must be reported."""
    from lizmap_server.expression_service import request_virtualfields

    class NeverValid(QgsExpression):
        def isValid(self):
            return False

    monkeypatch.setattr(request_virtualfields, "QgsExpression", NeverValid)

    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS='{{"a":"{}"}}'.format(quote("1", safe="")),
    )
    assert "Expression not valid" in body["message"]


def test_expression_virtual_fields_filter_errors(client):
    """An invalid FILTER must be reported."""
    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS='{{"a":"{}"}}'.format(quote("1", safe="")),
        FILTER=quote("foobar(", safe=""),
    )
    assert body["message"].startswith("Invalid FILTER for 'VirtualFields'")


def test_expression_virtual_fields_invalid_filter(client, monkeypatch):
    """A FILTER which is not valid must be reported."""
    from lizmap_server.expression_service import request_virtualfields

    real_expression = request_virtualfields.QgsExpression

    class NeverValid(real_expression):
        def isValid(self):
            return False

    def _factory(expression):
        # Only the request filter is built from the module level name
        return NeverValid(expression)

    monkeypatch.setattr(request_virtualfields, "QgsExpression", _factory)

    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS="{}",
        FILTER=quote('"NAME_1" = \'Bretagne\'', safe=""),
    )
    assert "Expression not valid" in body["message"]


def test_expression_virtual_fields_invalid_limit(client):
    """The LIMIT must be an integer."""
    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS='{{"a":"{}"}}'.format(quote("1", safe="")),
        LIMIT="not_a_number",
    )
    assert body["message"] == "Invalid LIMIT for 'VirtualFields': \"not_a_number\""


def test_expression_virtual_fields_invalid_sorting_order(client):
    """The SORTING_ORDER must be 'asc' or 'desc'."""
    body = _bad_request(
        client,
        REQUEST="VirtualFields",
        LAYER=LAYER,
        VIRTUALS='{{"a":"{}"}}'.format(quote("1", safe="")),
        SORTING_ORDER="sideways",
    )
    assert body["message"] == "Invalid SORTING_ORDER for 'VirtualFields': \"sideways\""


def test_expression_virtual_fields_eval_error(client):
    """An expression failing at evaluation must be reported per feature."""
    rv = client.get(
        _query(
            REQUEST="VirtualFields",
            LAYER=LAYER,
            VIRTUALS='{{"a":"{}"}}'.format(quote("to_int('abc')", safe="")),
            LIMIT="1",
        ),
        PROJECT_FILE,
    )
    body = _check_request(rv)
    feature = body["features"][0]
    # The expression could not be evaluated: the virtual field is null
    assert feature["properties"]["a"] is None


#
# GetFeatureWithFormScope
#


def test_expression_form_scope_missing_filter(client):
    """The FILTER parameter is mandatory."""
    body = _bad_request(client, REQUEST="GetFeatureWithFormScope", LAYER=LAYER)
    assert body["message"] == "Invalid 'GetFeatureWithFormScope' REQUEST: FILTER parameter is mandatory"


def test_expression_form_scope_missing_form_feature(client):
    """The FORM_FEATURE parameter is mandatory."""
    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
    )
    assert (
        body["message"] == "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE parameter is mandatory"
    )


def test_expression_form_scope_form_feature_not_an_object(client):
    """The FORM_FEATURE must be a json object."""
    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE="[1]",
    )
    assert "are not well formed" in body["message"]


def test_expression_form_scope_no_feature_parsed(client, monkeypatch):
    """A form feature which cannot be parsed must be reported."""
    from lizmap_server.expression_service import request_getfeaturewithformscope

    monkeypatch.setattr(
        request_getfeaturewithformscope, "QgsJsonUtils_stringToFeatureList", lambda *args: []
    )

    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "not GeoJSON feature provided" in body["message"]


def test_expression_form_scope_too_many_features(client, monkeypatch):
    """Exactly one form feature is expected."""
    from lizmap_server.expression_service import request_getfeaturewithformscope

    real = request_getfeaturewithformscope.QgsJsonUtils_stringToFeatureList
    monkeypatch.setattr(
        request_getfeaturewithformscope,
        "QgsJsonUtils_stringToFeatureList",
        lambda string, fields: real(string, fields) * 2,
    )

    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "not GeoJSON feature provided" in body["message"]


@pytest.mark.parametrize(
    "parent_feature,message",
    [
        ("[1]", "are not well formed"),
        ('{"type": "FeatureCollection"}', "type not defined or not Feature"),
    ],
)
def test_expression_form_scope_invalid_parent_feature(client, parent_feature, message):
    """The PARENT_FEATURE must be a well formed feature."""
    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
        PARENT_FEATURE=parent_feature,
    )
    assert message in body["message"]


def test_expression_form_scope_no_parent_feature_parsed(client, monkeypatch):
    """A parent feature which cannot be parsed must be reported."""
    from lizmap_server.expression_service import request_getfeaturewithformscope

    real = request_getfeaturewithformscope.QgsJsonUtils_stringToFeatureList
    calls = []

    def _parse(string, fields):
        calls.append(string)
        # The first call is for the form feature
        return real(string, fields) if len(calls) == 1 else []

    monkeypatch.setattr(request_getfeaturewithformscope, "QgsJsonUtils_stringToFeatureList", _parse)

    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
        PARENT_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "Invalid PARENT_FEATURE" in body["message"]


def test_expression_form_scope_filter_errors(client):
    """An invalid FILTER must be reported."""
    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("foobar(", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "Invalid FILTER" in body["message"]


def test_expression_form_scope_invalid_filter(client, monkeypatch):
    """A FILTER which is not valid must be reported."""
    from lizmap_server.expression_service import request_getfeaturewithformscope

    real_expression = request_getfeaturewithformscope.QgsExpression

    class NeverValid(real_expression):
        def isValid(self):
            return False

    monkeypatch.setattr(request_getfeaturewithformscope, "QgsExpression", NeverValid)

    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
    )
    assert "Expression not valid" in body["message"]


def test_expression_form_scope_malformed_parent_feature(client):
    """A malformed PARENT_FEATURE json must be rejected."""
    body = _bad_request(
        client,
        REQUEST="GetFeatureWithFormScope",
        LAYER=LAYER,
        FILTER=quote("1", safe=""),
        FORM_FEATURE='{"type":"Feature", "geometry": null, "properties": {}}',
        PARENT_FEATURE="{not json}",
    )
    assert "are not well formed" in body["message"]
