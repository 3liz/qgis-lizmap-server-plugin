#
# Request GETFEATUREWITHFORMSCOPE
#
import json
import traceback

from typing import (
    Dict,
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
from qgis.PyQt.QtCore import QTextCodec
from qgis.server import (
    QgsServerResponse,
)

from lizmap_server.core import (
    find_vector_layer,
    get_server_fid,
)
from lizmap_server.exception import ExpressionServiceError
from lizmap_server.tools import to_bool
from lizmap_server import logger


def get_feature_with_form_scope(
    params: Dict[str, str], response: QgsServerResponse, project: QgsProject
) -> None:
    """Get filtered features with a form scope

    In parameters:
        LAYER=wms-layer-name
        FILTER=An expression to filter layer
        FORM_FEATURE={"type": "Feature", "geometry": {}, "properties": {}}
        // optionals
        PARENT_FEATURE={"type": "Feature", "geometry": {}, "properties": {}}
        FIELDS=list of requested field separated by comma
        WITH_GEOMETRY=False
    """
    layer_name = params.get("LAYER", "")
    if not layer_name:
        raise ExpressionServiceError(
            "Bad request", "Invalid 'GetFeatureWithFormScope' REQUEST: LAYER parameter is mandatory", 400
        )

    # get layer
    layer = find_vector_layer(layer_name, project)
    # layer not found
    if not layer:
        raise ExpressionServiceError(
            "Bad request", f"Invalid LAYER parameter for 'VirtualField': {layer_name} provided", 400
        )

    # get filter
    exp_filter = params.get("FILTER", "")
    if not exp_filter:
        raise ExpressionServiceError(
            "Bad request", "Invalid 'GetFeatureWithFormScope' REQUEST: FILTER parameter is mandatory", 400
        )

    # get form feature
    form_feature = params.get("FORM_FEATURE", "")
    if not form_feature:
        raise ExpressionServiceError(
            "Bad request",
            "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE parameter is mandatory",
            400,
        )

    # Check features
    try:
        geojson = json.loads(form_feature)
    except Exception:
        logger.critical(f"JSON loads form feature '{form_feature}' exception:\n{traceback.format_exc()}")
        raise ExpressionServiceError(
            "Bad request",
            "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE '{}' are not well formed".format(
                form_feature
            ),
            400,
        )

    if not geojson or not isinstance(geojson, dict):
        raise ExpressionServiceError(
            "Bad request",
            "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE '{}' are not well formed".format(
                form_feature
            ),
            400,
        )

    if ("type" not in geojson) or geojson["type"] != "Feature":
        raise ExpressionServiceError(
            "Bad request",
            (
                "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE '{}' are not well formed: type "
                "not defined or not Feature."
            ).format(form_feature),
            400,
        )

    # try to load form feature
    # read fields
    form_feature_fields = QgsJsonUtils.stringToFields(form_feature, QTextCodec.codecForName("UTF-8"))
    # read features
    form_feature_list = QgsJsonUtils.stringToFeatureList(
        form_feature, form_feature_fields, QTextCodec.codecForName("UTF-8")
    )

    # features not well formed
    if not form_feature_list:
        raise ExpressionServiceError(
            "Bad request",
            ("Invalid FORM_FEATURE for 'GetFeatureWithFormScope': not GeoJSON feature provided\n{}").format(
                form_feature
            ),
            400,
        )

    if len(form_feature_list) != 1:
        raise ExpressionServiceError(
            "Bad request",
            ("Invalid FORM_FEATURE for 'GetFeatureWithFormScope': not GeoJSON feature provided\n{}").format(
                form_feature
            ),
            400,
        )

    # Get the form feature
    form_feat = form_feature_list[0]

    # get parent feature
    parent_feature = params.get("PARENT_FEATURE", "")
    parent_feat = None
    if parent_feature:
        # Check parent feature
        try:
            geojson = json.loads(parent_feature)
        except Exception:
            logger.critical(
                f"JSON loads form feature '{parent_feature}' exception:\n{traceback.format_exc()}"
            )
            raise ExpressionServiceError(
                "Bad request",
                "Invalid 'GetFeatureWithFormScope' REQUEST: PARENT_FEATURE '{}' are not well formed".format(
                    parent_feature
                ),
                400,
            )

        if not geojson or not isinstance(geojson, dict):
            raise ExpressionServiceError(
                "Bad request",
                "Invalid 'GetFeatureWithFormScope' REQUEST: PARENT_FEATURE '{}' are not well formed".format(
                    parent_feature
                ),
                400,
            )

        if geojson.get("type") != "Feature":
            raise ExpressionServiceError(
                "Bad request",
                (
                    "Invalid 'GetFeatureWithFormScope' REQUEST: PARENT_FEATURE '{}' are not well formed: type "
                    "not defined or not Feature."
                ).format(parent_feature),
                400,
            )

        # try to load parent feature
        # read fields
        parent_feature_fields = QgsJsonUtils.stringToFields(parent_feature, QTextCodec.codecForName("UTF-8"))
        # read features
        parent_feature_list = QgsJsonUtils.stringToFeatureList(
            parent_feature, parent_feature_fields, QTextCodec.codecForName("UTF-8")
        )

        if not parent_feature_list or len(parent_feature_list) != 1:
            raise ExpressionServiceError(
                "Bad request",
                (
                    "Invalid PARENT_FEATURE for 'GetFeatureWithFormScope': not GeoJSON feature provided\n{}"
                ).format(parent_feature),
                400,
            )

        # Get the form feature
        parent_feat = parent_feature_list[0]

    # create expression context
    exp_context = QgsExpressionContext()
    exp_context.appendScope(QgsExpressionContextUtils.globalScope())
    exp_context.appendScope(QgsExpressionContextUtils.projectScope(project))
    exp_context.appendScope(QgsExpressionContextUtils.layerScope(layer))
    exp_context.appendScope(QgsExpressionContextUtils.formScope(form_feat))
    if parent_feat:
        exp_context.appendScope(QgsExpressionContextUtils.parentFormScope(parent_feat))

    # create distance area context
    da = QgsDistanceArea()
    da.setSourceCrs(layer.crs(), project.transformContext())
    da.setEllipsoid(project.ellipsoid())

    # Get filter expression
    exp_f = QgsExpression(exp_filter)
    exp_f.setGeomCalculator(da)
    exp_f.setDistanceUnits(project.distanceUnits())
    exp_f.setAreaUnits(project.areaUnits())

    if exp_f.hasParserError():
        raise ExpressionServiceError(
            "Bad request",
            "Invalid FILTER for 'GetFeatureWithFormScope': "
            f"Error \"{exp_filter}\": {exp_f.parserErrorString()}",
            400,
        )

    if not exp_f.isValid():
        raise ExpressionServiceError(
            "Bad request",
            f"Invalid FILTER for 'GetFeatureWithFormScope': Expression not valid \"{exp_filter}\"",
            400,
        )

    exp_f.prepare(exp_context)

    req = QgsFeatureRequest(exp_f, exp_context)

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
        response.write(separator + json_exporter.exportFeature(feat, {}, fid))
        response.flush()
        separator = ",\n"
    response.write("]}")
