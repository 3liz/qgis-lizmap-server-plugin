#
# Request REPLACEEXPRESSIONTEXT
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
    Qgis,
    QgsDistanceArea,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsJsonExporter,
    QgsJsonUtils,
    QgsProject,
)
from qgis.PyQt.QtCore import QMetaType, QTextCodec, QVariant
from qgis.server import (
    QgsServerInterface,
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


def replace_expression_text(
    params: Dict[str, str],
    response: QgsServerResponse,
    project: QgsProject,
    server_iface: QgsServerInterface,
) -> None:
    """Replace expression texts against layer or features

    In parameters:
        LAYER=wms-layer-name
        STRING=A string with expression between [% and %]
        or
        STRINGS=["first string with expression", "second string with expression"]
        or
        STRINGS={"key1": "first string with expression", "key2": "second string with expression"}
        // optionals
        FEATURE={"type": "Feature", "geometry": {}, "properties": {}}
        or
        FEATURES=[{"type": "Feature", "geometry": {}, "properties": {}}, {"type": "Feature", "geometry": {},
        "properties": {}}]
        or
        FEATURES=ALL to get Replace expression texts for all features of the layer
        FORM_SCOPE=boolean to add formScope based on provided features
        FORMAT=GeoJSON to get response as GeoJSON
    """
    layer_name = params.get("LAYER", "")
    if not layer_name:
        raise ExpressionServiceError(
            "Bad request", "Invalid 'ReplaceExpressionText' REQUEST: LAYER parameter is mandatory", 400
        )

    # get layer
    layer = find_vector_layer(layer_name, project)
    # layer not found
    if not layer:
        raise ExpressionServiceError(
            "Bad request", f"Invalid LAYER parameter for 'ReplaceExpressionText': {layer_name} provided", 400
        )

    # get strings
    strings = params.get("STRINGS", "")
    if not strings:
        the_string = params.get("STRING", "")
        if not the_string:
            raise ExpressionServiceError(
                "Bad request",
                "Invalid 'ReplaceExpressionText' REQUEST: STRING or STRINGS parameter is mandatory",
                400,
            )
        strings = f'["{the_string}"]'

    # try to load expressions list or dict
    try:
        str_json = json.loads(strings)
    except Exception:
        logger.critical(f"JSON loads strings '{strings}' exception:\n{traceback.format_exc()}")
        raise ExpressionServiceError(
            "Bad request",
            f"Invalid 'ReplaceExpressionText' REQUEST: STRINGS '{strings}' are not well formed",
            400,
        )

    # set extra subset string provided by access control plugins
    subset_sql = layer.subsetString()
    extra_sql = server_iface.accessControls().extraSubsetString(layer)
    if extra_sql:
        layer.setSubsetString(f"({subset_sql}) AND ({extra_sql})" if subset_sql else extra_sql)

    # get features
    features = params.get("FEATURES", "")
    if not features:
        feature = params.get("FEATURE", "")
        if feature:
            features = "[" + feature + "]"

    # create expression context
    exp_context = QgsExpressionContext()
    exp_context.appendScope(QgsExpressionContextUtils.globalScope())
    exp_context.appendScope(QgsExpressionContextUtils.projectScope(project))
    exp_context.appendScope(QgsExpressionContextUtils.layerScope(layer))

    # create distance area context
    da = QgsDistanceArea()
    da.setSourceCrs(layer.crs(), project.transformContext())
    da.setEllipsoid(project.ellipsoid())

    # organized strings
    str_map = {}
    str_items: Iterable[Tuple[Any, Any]]
    if isinstance(str_json, list):
        str_items = enumerate(str_json)
    elif isinstance(str_json, dict):
        str_items = str_json.items()
    else:
        str_items = ()

    for k, s in str_items:
        str_map[k] = s

    # create the body
    body: "Body" = {
        "status": "success",
        "results": [],
        "errors": [],
        "features": 0,
    }

    # without features just replace expression string with layer context
    if not features:
        result = {}
        for k, s in str_map.items():
            value = QgsExpression.replaceExpressionText(s, exp_context, da)
            result[k] = json.loads(QgsJsonUtils.encodeValue(value))
        body["results"].append(result)
        write_json_response(body, response)
        # reset subset string before ending request
        if extra_sql:
            layer.setSubsetString(subset_sql)
        return

    # Check features
    if features.upper() == "ALL":
        feature_fields = layer.fields()
        feature_list = layer.getFeatures()
    else:
        try:
            geojson = json.loads(features)
        except Exception:
            # reset subset string before raising error
            if extra_sql:
                layer.setSubsetString(subset_sql)
            logger.critical(f"JSON loads features '{features}' exception:\n{traceback.format_exc()}")
            raise ExpressionServiceError(
                "Bad request", f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed", 400
            )

        if not geojson or not isinstance(geojson, list) or len(geojson) == 0:
            # reset subset string before raising error
            if extra_sql:
                layer.setSubsetString(subset_sql)
            raise ExpressionServiceError(
                "Bad request", f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed", 400
            )

        if ("type" not in geojson[0]) or geojson[0]["type"] != "Feature":
            # reset subset string before raising error
            if extra_sql:
                layer.setSubsetString(subset_sql)
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

    # features not well-formed
    if not feature_list:
        # reset subset string before raising error
        if extra_sql:
            layer.setSubsetString(subset_sql)
        raise ExpressionServiceError(
            "Bad request",
            ("Invalid FEATURES for 'ReplaceExpressionText': not GeoJSON features array provided\n{}").format(
                features
            ),
            400,
        )

    # Extend layer fields with this provided in GeoJSON Features
    feat_fields = QgsFields(layer.fields())
    feat_fields.extend(feature_fields)

    # form scope
    add_form_scope = to_bool(params.get("FORM_SCOPE"))

    geojson_output = params.get("FORMAT", "").upper() == "GEOJSON"
    if geojson_output:
        exporter = QgsJsonExporter()
        exporter.setSourceCrs(layer.crs())
        geojson_fields = QgsFields()
        for k in str_map:
            if Qgis.versionInt() < 33800:
                field = QgsField(str(k), QVariant.String)
            else:
                field = QgsField(str(k), QMetaType.Type.QString)
            geojson_fields.append(field)
    else:
        exporter = None
        geojson_fields = None

    # loop through provided features to replace expression strings
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

        # replace expression strings with the new feature
        result = {}
        for k, s in str_map.items():
            value = QgsExpression.replaceExpressionText(s, exp_context, da)
            result[k] = json.loads(QgsJsonUtils.encodeValue(value))
        if geojson_output:
            feature = QgsFeature(geojson_fields, f.id())
            feature.setGeometry(f.geometry())
            feature.setAttributes(list(result.values()))
            body["results"].append(exporter.exportFeature(feature))
        else:
            body["results"].append(result)

    if geojson_output:
        response.setStatusCode(200)
        response.setHeader("Content-Type", "application/vnd.geo+json; charset=utf-8")
        response.write(
            ",\n".join(
                [
                    '{"type": "FeatureCollection"',
                    '"features": [' + ",\n".join(body["results"]) + "]}",
                ]
            ),
        )
    else:
        write_json_response(body, response)

    # reset subset string before ending request
    if extra_sql:
        layer.setSubsetString(subset_sql)
