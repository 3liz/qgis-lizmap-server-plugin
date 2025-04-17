__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import json
import traceback

from typing import Dict

from qgis.core import (
    Qgis,
    QgsDistanceArea,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsJsonExporter,
    QgsJsonUtils,
    QgsProject,
)
from qgis.PyQt.QtCore import QMetaType, QTextCodec, QVariant
from qgis.server import (
    QgsRequestHandler,
    QgsServerRequest,
    QgsServerResponse,
    QgsService,
)

from lizmap_server.core import (
    find_vector_layer,
    get_lizmap_groups,
    get_lizmap_user_login,
    get_server_fid,
    write_json_response,
)
from lizmap_server.definitions.safe_expressions import ALLOWED_SAFE_EXPRESSIONS, NOT_ALLOWED_EXPRESSION
from lizmap_server.exception import ExpressionServiceError
from lizmap_server.logger import Logger
from lizmap_server.tools import to_bool


class ExpressionService(QgsService):

    def name(self) -> str:
        """ Service name
        """
        return 'EXPRESSION'

    def version(self) -> str:
        """ Service version
        """
        return "1.0.0"

    # def allowMethod(self, method: QgsServerRequest.Method) -> bool:
    #     """ Check supported HTTP methods
    #     """
    #     return method in (
    #         QgsServerRequest.GetMethod, QgsServerRequest.PostMethod)

    def executeRequest(self, request: QgsServerRequest, response: QgsServerResponse,
                       project: QgsProject) -> None:
        """ Execute a 'EXPRESSION' request
        """

        # Set lizmap variables
        request_handler = QgsRequestHandler(request, response)
        groups = get_lizmap_groups(request_handler)
        user_login = get_lizmap_user_login(request_handler)
        custom_var = project.customVariables()
        custom_var['lizmap_user'] = user_login
        custom_var['lizmap_user_groups'] = list(groups)  # QGIS can't store a tuple
        project.setCustomVariables(custom_var)

        params = request.parameters()

        # noinspection PyBroadException
        try:
            reqparam = params.get('REQUEST', '').upper()

            try:
                bytes(request.data()).decode()
            except Exception:
                raise ExpressionServiceError(
                    "Bad request error",
                    f"Invalid POST DATA for '{reqparam}'",
                    400)

            if reqparam == 'EVALUATE':
                self.evaluate(params, response, project)
            elif reqparam == 'REPLACEEXPRESSIONTEXT':
                self.replace_expression_text(params, response, project)
            elif reqparam == 'GETFEATUREWITHFORMSCOPE':
                self.get_feature_with_form_scope(params, response, project)
            elif reqparam == 'VIRTUALFIELDS':
                self.virtual_fields(params, response, project)
            else:
                raise ExpressionServiceError(
                    "Bad request error",
                    "Invalid REQUEST parameter: must be one of 'Evaluate', 'ReplaceExpressionText', "
                    "'GetFeatureWithFormScope', 'VirtualFields'; found '{}'".format(reqparam),
                    400)

        except ExpressionServiceError as err:
            err.formatResponse(response)
        except Exception as e:
            Logger.log_exception(e)
            err = ExpressionServiceError("Internal server error", "Internal 'lizmap' service error")
            err.formatResponse(response)

    # EXPRESSION Service request methods
    @staticmethod
    def evaluate(params: Dict[str, str], response: QgsServerResponse, project: QgsProject) -> None:
        """ Evaluate expressions against layer or features
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

        logger = Logger()
        layer_name = params.get('LAYER', '')
        if not layer_name:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'Evaluate' REQUEST: LAYER parameter is mandatory",
                400)

        # get layer
        layer = find_vector_layer(layer_name, project)
        # layer not found
        if not layer:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid LAYER parameter for 'Evaluate': {layer_name} provided",
                400)

        # get expressions
        expressions = params.get('EXPRESSIONS', '')
        if not expressions:
            expression = params.get('EXPRESSION', '')
            if not expression:
                raise ExpressionServiceError(
                    "Bad request error",
                    "Invalid 'Evaluate' REQUEST: EXPRESSION or EXPRESSIONS parameter is mandatory",
                    400)
            expressions = f'["{expression}"]'

        # try to load expressions list or dict
        try:
            exp_json = json.loads(expressions)
        except Exception:
            logger.critical(
                f"JSON loads expressions '{expressions}' exception:\n{traceback.format_exc()}")
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid 'Evaluate' REQUEST: EXPRESSIONS '{expressions}' are not well formed",
                400)

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
        exp_map = {}
        exp_parser_errors = []
        exp_items = []
        if isinstance(exp_json, list):
            exp_items = enumerate(exp_json)
        elif isinstance(exp_json, dict):
            exp_items = exp_json.items()
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
                "Bad request error",
                "Invalid EXPRESSIONS for 'Evaluate':\n{}".format('\n'.join(exp_parser_errors)),
                400)

        # get features
        features = params.get('FEATURES', '')
        if not features:
            feature = params.get('FEATURE', '')
            if feature:
                features = '[' + feature + ']'

        # create the body
        body = {
            'status': 'success',
            'results': [],
            'errors': [],
            'features': 0,
        }

        # without features just evaluate expression with layer context
        if not features:
            result = {}
            error = {}
            for k, exp in exp_map.items():
                value = exp.evaluate(exp_context)
                if exp.hasEvalError():
                    result[k] = None
                    error[k] = exp.evalErrorString()
                else:
                    result[k] = json.loads(QgsJsonUtils.encodeValue(value))
            body['results'].append(result)
            body['errors'].append(error)
            write_json_response(body, response)
            return

        # Check features
        try:
            geojson = json.loads(features)
        except Exception:
            logger.critical(
                f"JSON loads features '{features}' exception:\n{traceback.format_exc()}")
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed",
                400)

        if not geojson or not isinstance(geojson, list) or len(geojson) == 0:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed",
                400)

        if 'type' not in geojson[0] or geojson[0]['type'] != 'Feature':
            raise ExpressionServiceError(
                "Bad request error",
                ("Invalid 'Evaluate' REQUEST: FEATURES '{}' are not well formed: type not defined or not "
                 "Feature.").format(features),
                400)

        # try to load features
        # read fields
        feature_fields = QgsJsonUtils.stringToFields(
            '{ "type": "FeatureCollection","features":' + features + '}',
            QTextCodec.codecForName("UTF-8"))
        # read features
        feature_list = QgsJsonUtils.stringToFeatureList(
            '{ "type": "FeatureCollection","features":' + features + '}',
            feature_fields,
            QTextCodec.codecForName("UTF-8"))

        # features not well formed
        if not feature_list:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid FEATURES for 'Evaluate': not GeoJSON features array provided\n{features}",
                400)

        # Extend layer fields with this provided in GeoJSON Features
        feat_fields = QgsFields(layer.fields())
        feat_fields.extend(feature_fields)

        # form scope
        add_form_scope = to_bool(params.get('FORM_SCOPE'))

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
            body['results'].append(result)
            body['errors'].append(error)

        write_json_response(body, response)
        return

    @staticmethod
    def replace_expression_text(
            params: Dict[str, str], response: QgsServerResponse, project: QgsProject) -> None:
        """ Replace expression texts against layer or features

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
        logger = Logger()
        layer_name = params.get('LAYER', '')
        if not layer_name:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'ReplaceExpressionText' REQUEST: LAYER parameter is mandatory",
                400)

        # get layer
        layer = find_vector_layer(layer_name, project)
        # layer not found
        if not layer:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid LAYER parameter for 'ReplaceExpressionText': {layer_name} provided",
                400)

        # get strings
        strings = params.get('STRINGS', '')
        if not strings:
            the_string = params.get('STRING', '')
            if not the_string:
                raise ExpressionServiceError(
                    "Bad request error",
                    "Invalid 'ReplaceExpressionText' REQUEST: STRING or STRINGS parameter is mandatory",
                    400)
            strings = f'["{the_string}"]'

        # try to load expressions list or dict
        try:
            str_json = json.loads(strings)
        except Exception:
            logger.critical(
                f"JSON loads strings '{strings}' exception:\n{traceback.format_exc()}")
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid 'ReplaceExpressionText' REQUEST: STRINGS '{strings}' are not well formed",
                400)

        # get features
        features = params.get('FEATURES', '')
        if not features:
            feature = params.get('FEATURE', '')
            if feature:
                features = '[' + feature + ']'

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
        str_items = []
        if isinstance(str_json, list):
            str_items = enumerate(str_json)
        elif isinstance(str_json, dict):
            str_items = str_json.items()
        for k, s in str_items:
            str_map[k] = s

        # create the body
        body = {
            'status': 'success',
            'results': [],
            'errors': [],
            'features': 0,
        }

        # without features just replace expression string with layer context
        if not features:
            result = {}
            for k, s in str_map.items():
                value = QgsExpression.replaceExpressionText(s, exp_context, da)
                result[k] = json.loads(QgsJsonUtils.encodeValue(value))
            body['results'].append(result)
            write_json_response(body, response)
            return

        # Check features
        if features.upper() == 'ALL':
            feature_fields = layer.fields()
            feature_list = layer.getFeatures()
        else:
            try:
                geojson = json.loads(features)
            except Exception:
                logger.critical(
                    f"JSON loads features '{features}' exception:\n{traceback.format_exc()}")
                raise ExpressionServiceError(
                    "Bad request error",
                    f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed",
                    400)

            if not geojson or not isinstance(geojson, list) or len(geojson) == 0:
                raise ExpressionServiceError(
                    "Bad request error",
                    f"Invalid 'Evaluate' REQUEST: FEATURES '{features}' are not well formed",
                    400)

            if ('type' not in geojson[0]) or geojson[0]['type'] != 'Feature':
                raise ExpressionServiceError(
                    "Bad request error",
                    ("Invalid 'Evaluate' REQUEST: FEATURES '{}' are not well formed: type not defined or not "
                        "Feature.").format(features),
                    400)

            # try to load features
            # read fields
            feature_fields = QgsJsonUtils.stringToFields(
                '{ "type": "FeatureCollection","features":' + features + '}',
                QTextCodec.codecForName("UTF-8"))
            # read features
            feature_list = QgsJsonUtils.stringToFeatureList(
                '{ "type": "FeatureCollection","features":' + features + '}',
                feature_fields,
                QTextCodec.codecForName("UTF-8"))

        # features not well-formed
        if not feature_list:
            raise ExpressionServiceError(
                "Bad request error",
                ("Invalid FEATURES for 'ReplaceExpressionText': not GeoJSON features array "
                 "provided\n{}").format(features),
                400)

        # Extend layer fields with this provided in GeoJSON Features
        feat_fields = QgsFields(layer.fields())
        feat_fields.extend(feature_fields)

        # form scope
        add_form_scope = to_bool(params.get('FORM_SCOPE'))

        geojson_output = params.get('FORMAT', '').upper() == 'GEOJSON'
        if geojson_output:
            exporter = QgsJsonExporter()
            exporter.setSourceCrs(layer.crs())
            geojson_fields = QgsFields()
            for k in str_map.keys():
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
                body['results'].append(exporter.exportFeature(feature))
            else:
                body['results'].append(result)

        if geojson_output:
            response.setStatusCode(200)
            response.setHeader("Content-Type", "application/vnd.geo+json; charset=utf-8")
            response.write(
                ',\n'.join([
                    '{"type": "FeatureCollection"',
                    '"features": [' + ',\n'.join(body['results']) + ']}',
                ]),
            )
        else:
            write_json_response(body, response)
        return

    @staticmethod
    def get_feature_with_form_scope(
            params: Dict[str, str], response: QgsServerResponse, project: QgsProject) -> None:
        """ Get filtered features with a form scope

        In parameters:
            LAYER=wms-layer-name
            FILTER=An expression to filter layer
            FORM_FEATURE={"type": "Feature", "geometry": {}, "properties": {}}
            // optionals
            PARENT_FEATURE={"type": "Feature", "geometry": {}, "properties": {}}
            FIELDS=list of requested field separated by comma
            WITH_GEOMETRY=False
        """
        logger = Logger()
        layer_name = params.get('LAYER', '')
        if not layer_name:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'GetFeatureWithFormScope' REQUEST: LAYER parameter is mandatory",
                400)

        # get layer
        layer = find_vector_layer(layer_name, project)
        # layer not found
        if not layer:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid LAYER parameter for 'VirtualField': {layer_name} provided",
                400)

        # get filter
        exp_filter = params.get('FILTER', '')
        if not exp_filter:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'GetFeatureWithFormScope' REQUEST: FILTER parameter is mandatory",
                400)

        # get form feature
        form_feature = params.get('FORM_FEATURE', '')
        if not form_feature:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE parameter is mandatory",
                400)

        # Check features
        try:
            geojson = json.loads(form_feature)
        except Exception:
            logger.critical(
                f"JSON loads form feature '{form_feature}' exception:\n{traceback.format_exc()}")
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE '{}' are not well formed".format(
                    form_feature),
                400)

        if not geojson or not isinstance(geojson, dict):
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE '{}' are not well formed".format(
                    form_feature),
                400)

        if ('type' not in geojson) or geojson['type'] != 'Feature':
            raise ExpressionServiceError(
                "Bad request error", (
                    "Invalid 'GetFeatureWithFormScope' REQUEST: FORM_FEATURE '{}' are not well formed: type "
                    "not defined or not Feature.").format(form_feature),
                400)

        # try to load form feature
        # read fields
        form_feature_fields = QgsJsonUtils.stringToFields(
            form_feature,
            QTextCodec.codecForName("UTF-8"))
        # read features
        form_feature_list = QgsJsonUtils.stringToFeatureList(
            form_feature,
            form_feature_fields,
            QTextCodec.codecForName("UTF-8"))

        # features not well formed
        if not form_feature_list:
            raise ExpressionServiceError(
                "Bad request error",
                ("Invalid FORM_FEATURE for 'GetFeatureWithFormScope': not GeoJSON feature provided\n"
                 "{}").format(form_feature),
                400)

        if len(form_feature_list) != 1:
            raise ExpressionServiceError(
                "Bad request error",
                ("Invalid FORM_FEATURE for 'GetFeatureWithFormScope': not GeoJSON feature provided\n"
                 "{}").format(form_feature),
                400)

        # Get the form feature
        form_feat = form_feature_list[0]

        # get parent feature
        parent_feature = params.get('PARENT_FEATURE', '')
        parent_feat = None
        if parent_feature:
            # Check parent feature
            try:
                geojson = json.loads(parent_feature)
            except Exception:
                logger.critical(
                    f"JSON loads form feature '{parent_feature}' exception:\n{traceback.format_exc()}")
                raise ExpressionServiceError(
                    "Bad request error",
                    "Invalid 'GetFeatureWithFormScope' REQUEST: PARENT_FEATURE '{}' are not well formed".format(
                        parent_feature),
                    400)

            if not geojson or not isinstance(geojson, dict):
                raise ExpressionServiceError(
                    "Bad request error",
                    "Invalid 'GetFeatureWithFormScope' REQUEST: PARENT_FEATURE '{}' are not well formed".format(
                        parent_feature),
                    400)

            if geojson.get('type') != 'Feature':
                raise ExpressionServiceError(
                    "Bad request error", (
                        "Invalid 'GetFeatureWithFormScope' REQUEST: PARENT_FEATURE '{}' are not well formed: type "
                        "not defined or not Feature.").format(parent_feature),
                    400)

            # try to load parent feature
            # read fields
            parent_feature_fields = QgsJsonUtils.stringToFields(
                parent_feature,
                QTextCodec.codecForName("UTF-8"))
            # read features
            parent_feature_list = QgsJsonUtils.stringToFeatureList(
                parent_feature,
                parent_feature_fields,
                QTextCodec.codecForName("UTF-8"))

            if not parent_feature_list or len(parent_feature_list) != 1:
                raise ExpressionServiceError(
                    "Bad request error", (
                        "Invalid PARENT_FEATURE for 'GetFeatureWithFormScope': not GeoJSON feature provided\n"
                        "{}").format(parent_feature),
                    400)

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
                "Bad request error",
                "Invalid FILTER for 'GetFeatureWithFormScope': Error \"{}\": {}".format(
                    exp_filter, exp_f.parserErrorString()),
                400)

        if not exp_f.isValid():
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid FILTER for 'GetFeatureWithFormScope': Expression not valid \"{}\"".format(
                    exp_filter),
                400)

        exp_f.prepare(exp_context)

        req = QgsFeatureRequest(exp_f, exp_context)

        # With geometry
        with_geom = to_bool(params.get('WITH_GEOMETRY'))
        if not with_geom:
            req.setFlags(QgsFeatureRequest.Flag.NoGeometry)

        # Fields
        pk_attributes = layer.primaryKeyAttributes()
        attribute_list = [i for i in pk_attributes]
        fields = layer.fields()
        r_fields = [f.strip() for f in params.get('FIELDS', '').split(',') if f]
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

        separator = ''
        for feat in layer.getFeatures(req):
            fid = layer_name + '.' + get_server_fid(feat, pk_attributes)
            response.write(separator + json_exporter.exportFeature(feat, {}, fid))
            response.flush()
            separator = ',\n'
        response.write(']}')
        return

    @staticmethod
    def virtual_fields(params: Dict[str, str], response: QgsServerResponse, project: QgsProject) -> None:
        """ Get virtual fields for features

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
        logger = Logger()

        layer_name = params.get('LAYER', '')
        if not layer_name:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'VirtualFields' REQUEST: LAYER parameter is mandatory",
                400)

        # get layer
        layer = find_vector_layer(layer_name, project)
        # layer not found
        if not layer:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid LAYER parameter for 'VirtualFields': {layer_name} provided",
                400)

        # get virtuals
        virtuals = params.get('VIRTUALS', '')
        if not virtuals:
            raise ExpressionServiceError(
                "Bad request error",
                "Invalid 'VirtualFields' REQUEST: VIRTUALS parameter is mandatory",
                400)

        vir_json = ExpressionService.check_json_virtuals('VIRTUALS', virtuals)

        safe_virtuals = params.get('SAFE_VIRTUALS')
        safe_vir_json = ExpressionService.check_json_virtuals('SAFE_VIRTUALS', safe_virtuals)
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
            exp, error = ExpressionService.check_expression(expression, distance_area, project)
            if error:
                exp_parser_errors.append(error)
                continue

            exp.prepare(exp_context)
            exp_map[field] = exp

        for field, expression in safe_vir_json.items():
            exp, error = ExpressionService.check_expression(expression, distance_area, project)
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
                "Bad request error",
                "Invalid VIRTUALS or SAFE_VIRTUALS for 'VirtualFields':\n{}".format('\n'.join(exp_parser_errors)),
                400)

        req = QgsFeatureRequest()

        # get filter
        req_filter = params.get('FILTER', '')
        if req_filter:
            req_exp = QgsExpression(req_filter)
            req_exp.setGeomCalculator(distance_area)
            req_exp.setDistanceUnits(project.distanceUnits())
            req_exp.setAreaUnits(project.areaUnits())

            if req_exp.hasParserError():
                raise ExpressionServiceError(
                    "Bad request error",
                    "Invalid FILTER for 'VirtualFields' Error \"{}\": {}".format(
                        req_filter, req_exp.parserErrorString()),
                    400)

            if not req_exp.isValid():
                raise ExpressionServiceError(
                    "Bad request error",
                    f"Invalid FILTER for 'VirtualFields' Expression not valid \"{req_filter}\"",
                    400)

            req_exp.prepare(exp_context)
            req = QgsFeatureRequest(req_exp, exp_context)

        # set limit
        req_limit = params.get('LIMIT', '-1')
        try:
            req.setLimit(int(req_limit))
        except ValueError:
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid LIMIT for 'VirtualFields': \"{req_limit}\"",
                400)

        # set orderby
        req_sorting_order_param = params.get('SORTING_ORDER', '').lower()

        if req_sorting_order_param in ('asc', 'desc'):
            # QGIS expects a boolean to know how to sort
            req_sorting_field = params.get('SORTING_FIELD', '')
            order_by_clause = QgsFeatureRequest.OrderByClause(req_sorting_field, req_sorting_order_param == 'asc')
            req.setOrderBy(QgsFeatureRequest.OrderBy([order_by_clause]))
        elif req_sorting_order_param != '':
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid SORTING_ORDER for 'VirtualFields': \"{req_sorting_order_param}\"",
                400)

        # With geometry
        with_geom = to_bool(params.get('WITH_GEOMETRY'))
        if not with_geom:
            req.setFlags(QgsFeatureRequest.Flag.NoGeometry)

        # Fields
        pk_attributes = layer.primaryKeyAttributes()
        attribute_list = [i for i in pk_attributes]
        fields = layer.fields()
        r_fields = [f.strip() for f in params.get('FIELDS', '').split(',') if f]
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

        separator = ''
        for feat in layer.getFeatures(req):
            fid = layer_name + '.' + get_server_fid(feat, pk_attributes)

            extra = {}

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
            separator = ',\n'
        response.write(']}')
        return

    @classmethod
    def check_json_virtuals(cls, name: str, virtuals: str) -> dict:
        """ Load virtuals dictionary from string to JSON."""
        if not virtuals:
            return {}

        try:
            virtual_json = json.loads(virtuals)
        except Exception:
            logger = Logger()
            logger.critical(
                f"JSON loads {name} '{virtuals}' exception:\n{traceback.format_exc()}")
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid 'VirtualFields' REQUEST: VIRTUALS '{virtuals}' are not well formed",
                400)

        if not isinstance(virtual_json, dict):
            raise ExpressionServiceError(
                "Bad request error",
                f"Invalid 'VirtualFields' REQUEST: VIRTUALS '{virtuals}' are not well formed",
                400)

        return virtual_json

    @classmethod
    def check_expression(
            cls, expression_str: str, distance_area: QgsDistanceArea, project: QgsProject) -> [QgsExpression, str]:
        """ Check if an expression as a string has an error or not."""
        expression = QgsExpression(expression_str)
        expression.setGeomCalculator(distance_area)
        expression.setDistanceUnits(project.distanceUnits())
        expression.setAreaUnits(project.areaUnits())

        if expression.hasParserError():
            return None, f'Error "{expression_str}": {expression.parserErrorString()}'

        if not expression.isValid():
            return None, f'Expression not valid "{expression_str}"'

        return expression, ''
