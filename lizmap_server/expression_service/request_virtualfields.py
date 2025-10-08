#
# Request VIRTUALFIELDS
#
import json
import traceback

from typing import (
    Dict,
    Optional,
    Tuple,
)

from qgis.core import (
    QgsDistanceArea,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsJsonExporter,
    QgsJsonUtils,
    QgsProject,
)
from qgis.server import (
    QgsServerInterface,
    QgsServerResponse,
)

from lizmap_server.core import (
    find_vector_layer,
    get_server_fid,
)
from lizmap_server.exception import ExpressionServiceError
from lizmap_server.tools import to_bool
from lizmap_server import logger

from .models import (
    ALLOWED_SAFE_EXPRESSIONS,
    NOT_ALLOWED_EXPRESSION,
)


def virtual_fields(
    params: Dict[str, str],
    response: QgsServerResponse,
    project: QgsProject,
    server_iface: QgsServerInterface,
):
    """Get virtual fields for features

    In parameters:
        LAYER=wms-layer-name
        VIRTUALS={"key1": "first expression", "key2": "second expression"}
        // optionals
        SAFE_VIRTUALS={"key1": "first expression", "key2": "second expression"}
        FILTER=An expression to filter layer
        FIELDS=list of requested field separated by comma
        WITH_GEOMETRY=False
        LIMIT=number of features to return or nothing to return all
        SORTING_ORDER=asc or desc, default = asc
        SORTING_FIELD=field name to sort by
    """
    layer_name = params.get("LAYER", "")
    if not layer_name:
        raise ExpressionServiceError(
            "Bad request", "Invalid 'VirtualFields' REQUEST: LAYER parameter is mandatory", 400
        )

    # get layer
    layer = find_vector_layer(layer_name, project)
    # layer not found
    if not layer:
        raise ExpressionServiceError(
            "Bad request", f"Invalid LAYER parameter for 'VirtualFields': {layer_name} provided", 400
        )

    # get virtuals
    virtuals = params.get("VIRTUALS", "")
    if not virtuals:
        raise ExpressionServiceError(
            "Bad request", "Invalid 'VirtualFields' REQUEST: VIRTUALS parameter is mandatory", 400
        )

    vir_json = check_json_virtuals("VIRTUALS", virtuals)

    safe_virtuals = params.get("SAFE_VIRTUALS")
    safe_vir_json = check_json_virtuals("SAFE_VIRTUALS", safe_virtuals)
    # TODO, check that subset of safe virtuals does not overlap with virtuals

    # create expression context
    exp_context = QgsExpressionContext()
    exp_context.appendScope(QgsExpressionContextUtils.globalScope())
    exp_context.appendScope(QgsExpressionContextUtils.projectScope(project))
    exp_context.appendScope(QgsExpressionContextUtils.layerScope(layer))

    # create distance area context
    distance_area = QgsDistanceArea()
    distance_area.setSourceCrs(layer.crs(), project.transformContext())
    distance_area.setEllipsoid(project.ellipsoid())

    # parse virtuals
    exp_map = {}
    exp_parser_errors = []
    for field, expression in vir_json.items():
        exp, error = check_expression(expression, distance_area, project)
        if error:
            exp_parser_errors.append(error)
            continue

        exp.prepare(exp_context)
        exp_map[field] = exp

    for field, expression in safe_vir_json.items():
        exp, error = check_expression(expression, distance_area, project)
        if error:
            exp_parser_errors.append(error)
            continue

        for member in exp.referencedFunctions():
            if member not in ALLOWED_SAFE_EXPRESSIONS:
                allowed = ",".join(ALLOWED_SAFE_EXPRESSIONS)
                logger.warning(
                    f"Project {project.fileName()}, "
                    f"layer {layer_name}, "
                    f"input expression '{expression}' has been discarded from evaluation, "
                    f"replaced by '{NOT_ALLOWED_EXPRESSION}'. "
                    f"Only '{allowed}' are allowed.",
                )
                exp = QgsExpression(NOT_ALLOWED_EXPRESSION)

        exp.prepare(exp_context)
        exp_map[field] = exp

    # expression parser errors found
    if exp_parser_errors:
        raise ExpressionServiceError(
            "Bad request",
            "Invalid VIRTUALS or SAFE_VIRTUALS for 'VirtualFields':\n{}".format("\n".join(exp_parser_errors)),
            400,
        )

    req = QgsFeatureRequest()

    # get filter
    req_filter = params.get("FILTER", "")
    if req_filter:
        req_exp = QgsExpression(req_filter)
        req_exp.setGeomCalculator(distance_area)
        req_exp.setDistanceUnits(project.distanceUnits())
        req_exp.setAreaUnits(project.areaUnits())

        if req_exp.hasParserError():
            raise ExpressionServiceError(
                "Bad request",
                "Invalid FILTER for 'VirtualFields' Error \"{}\": {}".format(
                    req_filter, req_exp.parserErrorString()
                ),
                400,
            )

        if not req_exp.isValid():
            raise ExpressionServiceError(
                "Bad request",
                f"Invalid FILTER for 'VirtualFields' Expression not valid \"{req_filter}\"",
                400,
            )

        req_exp.prepare(exp_context)
        req = QgsFeatureRequest(req_exp, exp_context)

    # set limit
    req_limit = params.get("LIMIT", "-1")
    try:
        req.setLimit(int(req_limit))
    except ValueError:
        raise ExpressionServiceError(
            "Bad request", f"Invalid LIMIT for 'VirtualFields': \"{req_limit}\"", 400
        )

    # set orderby
    req_sorting_order_param = params.get("SORTING_ORDER", "").lower()

    if req_sorting_order_param in ("asc", "desc"):
        # QGIS expects a boolean to know how to sort
        req_sorting_field = params.get("SORTING_FIELD", "")
        order_by_clause = QgsFeatureRequest.OrderByClause(req_sorting_field, req_sorting_order_param == "asc")
        req.setOrderBy(QgsFeatureRequest.OrderBy([order_by_clause]))
    elif req_sorting_order_param != "":
        raise ExpressionServiceError(
            "Bad request", f"Invalid SORTING_ORDER for 'VirtualFields': \"{req_sorting_order_param}\"", 400
        )

    # With geometry
    with_geom = to_bool(params.get("WITH_GEOMETRY"))
    if not with_geom:
        req.setFlags(QgsFeatureRequest.Flag.NoGeometry)

    # Fields
    pk_attributes = layer.primaryKeyAttributes()
    attribute_list = list(pk_attributes)
    fields = layer.fields()
    r_fields = [f.strip() for f in params.get("FIELDS", "").split(",") if f]
    for f in r_fields:
        attribute_list.append(fields.indexOf(f))

    # set extra subset string provided by access control plugins
    subset_sql = layer.subsetString()
    extra_sql = server_iface.accessControls().extraSubsetString(layer)
    if extra_sql:
        layer.setSubsetString(f"({subset_sql}) AND ({extra_sql})" if subset_sql else extra_sql)

    # response
    response.setStatusCode(200)
    response.setHeader("Content-Type", "application/json")
    response.write('{ "type": "FeatureCollection","features":[')
    response.flush()

    json_exporter = QgsJsonExporter(layer)
    if attribute_list:
        json_exporter.setAttributes(attribute_list)

    separator = ""
    for feat in layer.getFeatures(req):
        fid = layer_name + "." + get_server_fid(feat, pk_attributes)

        extra: dict = {}

        # Update context
        exp_context.setFeature(feat)
        exp_context.setFields(feat.fields())

        # Evaluate expressions for virtual fields
        errors = {}
        for field, exp in exp_map.items():
            value = exp.evaluate(exp_context)
            if exp.hasEvalError():
                extra[field] = None
                errors[field] = exp.evalErrorString()
            else:
                extra[field] = json.loads(QgsJsonUtils.encodeValue(value))
                errors[field] = exp.expression()

        response.write(separator + json_exporter.exportFeature(feat, extra, fid))
        response.flush()
        separator = ",\n"
    response.write("]}")

    # reset subset string before ending request
    if extra_sql:
        layer.setSubsetString(subset_sql)


def check_json_virtuals(name: str, virtuals: Optional[str]) -> dict:
    """Load virtuals dictionary from string to JSON."""
    if not virtuals:
        return {}

    try:
        virtual_json = json.loads(virtuals)
    except Exception:
        logger.critical(f"JSON loads {name} '{virtuals}' exception:\n{traceback.format_exc()}")
        raise ExpressionServiceError(
            "Bad request", f"Invalid 'VirtualFields' REQUEST: VIRTUALS '{virtuals}' are not well formed", 400
        )

    if not isinstance(virtual_json, dict):
        raise ExpressionServiceError(
            "Bad request", f"Invalid 'VirtualFields' REQUEST: VIRTUALS '{virtuals}' are not well formed", 400
        )

    return virtual_json


def check_expression(
    expression_str: str,
    distance_area: QgsDistanceArea,
    project: QgsProject,
) -> Tuple[QgsExpression, str]:
    """Check if an expression as a string has an error or not."""
    expression = QgsExpression(expression_str)
    expression.setGeomCalculator(distance_area)
    expression.setDistanceUnits(project.distanceUnits())
    expression.setAreaUnits(project.areaUnits())

    if expression.hasParserError():
        return None, f'Error "{expression_str}": {expression.parserErrorString()}'

    if not expression.isValid():
        return None, f'Expression not valid "{expression_str}"'

    return expression, ""
