#
# Expression request EVALUATE
#
import json
import traceback

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Tuple,
)

from qgis.core import (
    QgsDistanceArea,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFields,
    QgsJsonUtils,
    QgsProject,
)
from qgis.PyQt.QtCore import QTextCodec
from qgis.server import (
    QgsServerResponse,
)

from lizmap_server.core import (
    find_vector_layer,
    write_json_response,
)
from lizmap_server.exception import ExpressionServiceError
from lizmap_server.tools import to_bool
from lizmap_server import logger


if TYPE_CHECKING:
    from .models import Body


def evaluate(params: Dict[str, str], response: QgsServerResponse, project: QgsProject):
    """Evaluate expressions against layer or features
    In parameters:
        LAYER=wms-layer-name
        EXPRESSION=An expression to evaluate
        or
        EXPRESSIONS=["first expression", "second expression"]
        or
        EXPRESSIONS={"key1": "first expression", "key2": "second expression"}
        // optionals
        FEATURE={"type": "Feature", "geometry": {}, "properties": {}}
        or
        FEATURES=[{"type": "Feature", "geometry": {}, "properties": {}}, {"type": "Feature", "geometry": {},
        "properties": {}}]
        FORM_SCOPE=boolean to add formScope based on provided features
    """
    layer_name = params.get("LAYER", "")
    if not layer_name:
        raise ExpressionServiceError(
            "Bad request",
            "Invalid 'Evaluate' REQUEST: LAYER parameter is mandatory",
            400,
        )

    # get layer
    layer = find_vector_layer(layer_name, project)
    # layer not found
    if not layer:
        raise ExpressionServiceError(
            "Bad request",
            f"Invalid LAYER parameter for 'Evaluate': {layer_name} provided",
            400,
        )

    # get expressions
    expressions = params.get("EXPRESSIONS")
    if not expressions:
        # Get single expression parameter
        expression = params.get("EXPRESSION")
        if not expression:
            raise ExpressionServiceError(
                "Bad request",
                "Invalid 'Evaluate' REQUEST: EXPRESSIONS or EXPRESSION parameter is mandatory",
                400,
            )
        expressions = f'["{expression}"]'

    # try to load expressions list or dict
    try:
        exp_json = json.loads(expressions)
    except json.JSONDecodeError:
        logger.critical(f"JSON loads expressions '{expressions}' exception:\n{traceback.format_exc()}")
        raise ExpressionServiceError(
            "Bad request",
            "Invalid 'Evaluate' REQUEST EXPRESSIONS: malformed JSON",
            400,
        )

    # create expression context
    exp_context = QgsExpressionContext()
    exp_context.appendScope(QgsExpressionContextUtils.globalScope())
    exp_context.appendScope(QgsExpressionContextUtils.projectScope(project))
    exp_context.appendScope(QgsExpressionContextUtils.layerScope(layer))

    # create distance area context
    da = QgsDistanceArea()
    da.setSourceCrs(layer.crs(), project.transformContext())
    da.setEllipsoid(project.ellipsoid())

    # parse expressions
    exp_map: dict = {}
    exp_parser_errors: list = []

    exp_items: Iterable[Tuple[Any, Any]]
    if isinstance(exp_json, list):
        exp_items = enumerate(exp_json)
    elif isinstance(exp_json, dict):
        exp_items = exp_json.items()
    else:
        exp_items = ()

    for k, e in exp_items:
        exp = QgsExpression(e)
        exp.setGeomCalculator(da)
        exp.setDistanceUnits(project.distanceUnits())
        exp.setAreaUnits(project.areaUnits())

        if exp.hasParserError():
            exp_parser_errors.append(f'Error "{e}": {exp.parserErrorString()}')
            continue

        if not exp.isValid():
            exp_parser_errors.append(f'Expression not valid "{e}"')
            continue

        exp.prepare(exp_context)
        exp_map[k] = exp

    # expression parser errors found
    if exp_parser_errors:
        raise ExpressionServiceError(
            "Bad request",
            "Invalid EXPRESSIONS for 'Evaluate':\n{}".format("\n".join(exp_parser_errors)),
            400,
        )

    # get features
    features = params.get("FEATURES", "")
    if not features:
        feature = params.get("FEATURE", "")
        if feature:
            features = f"[{feature}]"

    # create the body
    body: "Body" = {
        "status": "success",
        "results": [],
        "errors": [],
        "features": 0,
    }

    # without features just evaluate expression with layer context
    if not features:
        result: dict = {}
        error: dict = {}
        for k, exp in exp_map.items():
            value = exp.evaluate(exp_context)
            if exp.hasEvalError():
                result[k] = None
                error[k] = exp.evalErrorString()
            else:
                result[k] = json.loads(QgsJsonUtils.encodeValue(value))

        body["results"].append(result)
        body["errors"].append(error)
        write_json_response(body, response)
        return

    # Check features
    try:
        geojson = json.loads(features)
    except Exception:
        logger.critical(f"JSON loads features '{features}' exception:\n{traceback.format_exc()}")
        raise ExpressionServiceError(
            "Bad request", f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed", 400
        )

    if not geojson or not isinstance(geojson, list) or len(geojson) == 0:
        raise ExpressionServiceError(
            "Bad request", f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed", 400
        )

    if "type" not in geojson[0] or geojson[0]["type"] != "Feature":
        raise ExpressionServiceError(
            "Bad request",
            (
                "Invalid 'Evaluate' REQUEST: FEATURES '{}' are not well formed: type not defined or not "
                "Feature."
            ).format(features),
            400,
        )

    # try to load features
    # read fields
    feature_fields = QgsJsonUtils.stringToFields(
        '{ "type": "FeatureCollection","features":' + features + "}", QTextCodec.codecForName("UTF-8")
    )
    # read features
    feature_list = QgsJsonUtils.stringToFeatureList(
        '{ "type": "FeatureCollection","features":' + features + "}",
        feature_fields,
        QTextCodec.codecForName("UTF-8"),
    )

    # features not well formed
    if not feature_list:
        raise ExpressionServiceError(
            "Bad request",
            f"Invalid FEATURES for 'Evaluate': not GeoJSON features array provided\n{features}",
            400,
        )

    # Extend layer fields with this provided in GeoJSON Features
    feat_fields = QgsFields(layer.fields())
    feat_fields.extend(feature_fields)

    # form scope
    add_form_scope = to_bool(params.get("FORM_SCOPE"))

    # loop through provided features to evaluate expressions
    for f in feature_list:
        # clone the features with all attributes
        # those defined in layer + fields from GeoJSON Features
        feat = QgsFeature(feat_fields)
        feat.setGeometry(f.geometry())
        for field in f.fields():
            field_name = field.name()
            if feat_fields.indexOf(field_name) != -1:
                feat.setAttribute(field_name, f[field_name])

        # Add form scope to expression context
        if add_form_scope:
            exp_context.appendScope(QgsExpressionContextUtils.formScope(feat))

        exp_context.setFeature(feat)
        exp_context.setFields(feat.fields())

        # Evaluate expressions with the new feature
        result = {}
        error = {}
        for k, exp in exp_map.items():
            if add_form_scope:
                # need to prepare the expression because the context has been updated with a new scope
                exp.prepare(exp_context)
            value = exp.evaluate(exp_context)
            if exp.hasEvalError():
                result[k] = None
                error[k] = exp.evalErrorString()
            else:
                result[k] = json.loads(QgsJsonUtils.encodeValue(value))
                error[k] = exp.expression()
        body["results"].append(result)
        body["errors"].append(error)
        body["features"] += 1

    write_json_response(body, response)
    return
