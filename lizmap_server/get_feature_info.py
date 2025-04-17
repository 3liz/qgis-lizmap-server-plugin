__copyright__ = "Copyright 2021, 3Liz"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"

import json
import os
import xml.etree.ElementTree as ET

from collections import namedtuple
from pathlib import Path
from typing import Generator, List, Tuple, Union

from qgis.core import (
    Qgis,
    QgsDistanceArea,
    QgsEditFormConfig,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsProject,
    QgsRelationManager,
)
from qgis.server import QgsServerFeatureId, QgsServerFilter, QgsServerProjectUtils

from lizmap_server.core import find_vector_layer
from lizmap_server.logger import Logger, exception_handler
from lizmap_server.tools import to_bool
from lizmap_server.tooltip import Tooltip

"""
QGIS Server filter for the GetFeatureInfo according to CFG config.
"""

Result = namedtuple('Result', ['layer', 'feature_id', 'expression'])


class GetFeatureInfoFilter(QgsServerFilter):

    @classmethod
    def parse_xml(cls, string: str) -> Generator[Tuple[str, str], None, None]:
        """ Generator for layer and feature found in the XML GetFeatureInfo. """
        root = ET.fromstring(string)
        for layer in root:
            for feature in layer:
                if feature.attrib.get('id'):
                    yield layer.attrib['name'], feature.attrib['id']

    @classmethod
    def append_maptip(cls, string: str, layer_name: str, feature_id: Union[str, int], maptip: str) -> str:
        """ Edit the XML GetFeatureInfo by adding a maptip for a given layer and feature ID. """
        root = ET.fromstring(string)
        for layer in root:

            if layer.tag.upper() != 'LAYER':
                # The XML can be <BoundingBox />
                continue

            if layer.attrib['name'] != layer_name:
                continue

            for feature in layer:
                # feature_id can be int if QgsFeature.id() is used
                # Otherwise it's string from QgsServerFeatureId
                if feature.attrib['id'] != str(feature_id):
                    continue

                item = feature.find("Attribute[@name='maptip']")
                if item is not None:
                    item.attrib['value'] = maptip
                else:
                    item = ET.Element('Attribute')
                    item.attrib['name'] = "maptip"
                    item.attrib['value'] = maptip
                    feature.append(item)

        xml_lines = ET.tostring(root, encoding='utf8', method='xml').decode("utf-8").split('\n')
        xml_string = '\n'.join(xml_lines[1:])
        return xml_string.strip()

    @classmethod
    def feature_list_to_replace(
            cls,
            cfg: dict,
            project: QgsProject,
            relation_manager: QgsRelationManager,
            xml: str,
            css_framework: str,
    ) -> List[Result]:
        """ Parse the XML and check for each layer according to the Lizmap CFG file. """
        features = []
        for layer_name, feature_id in GetFeatureInfoFilter.parse_xml(xml):
            layer = find_vector_layer(layer_name, project)
            if not layer:
                Logger.info(f"Skipping the layer '{layer_name}' because it's not a vector layer")
                continue

            if layer_name != layer.name():
                Logger.info("Request on layer shortname '{}' and layer name '{}'".format(
                    layer_name, layer.name()))

            layers = cfg.get('layers')
            if not layers:
                Logger.critical(f"No 'layers' section in the CFG file {project.fileName()}.cfg")
                continue

            layer_config = layers.get(layer.name())
            if not layer_config:
                Logger.critical(
                    "No layer configuration for layer {} in the CFG file {}.cfg".format(
                        layer.name(), project.fileName()))
                continue

            if not to_bool(layer_config.get('popup')):
                continue

            if layer_config.get('popupSource') != 'form':
                continue

            config = layer.editFormConfig()
            if config.layout() != QgsEditFormConfig.EditorLayout.TabLayout:
                Logger.warning(
                    'The CFG is requesting a form popup, but the layer is not a form drag&drop layout')
                continue

            root = config.invisibleRootContainer()

            # Need to eval the html_content
            html_content = Tooltip.create_popup_node_item_from_form(
                layer, root, 0, [], '', relation_manager, css_framework == 'BOOTSTRAP5')
            html_content = Tooltip.create_popup(html_content)

            # If CSS_FRAMEWORK is empty (empty string), it means :
            # LWC <= 3.7.X
            # LWC between 3.8.0 and 3.8.6 included
            # We include so the CSS
            # Starting from 3.8.7, the CSS is included into LWC itself
            # Because the Lizmap server 2.13.0 is a hard dependency to LWC 3.8.7, the CSS will be obviously provided by
            # LWC core, so no call to Tooltip::css_3_8_6() on the server side, only in desktop.
            if css_framework == '':
                # Maybe we can avoid the CSS on all features ?
                html_content += Tooltip.css()

            features.append(Result(layer, feature_id, html_content))
            Logger.info(
                "The popup has been replaced for feature ID '{}' in layer '{}'".format(
                    feature_id, layer_name))
        return features

    @exception_handler
    def responseComplete(self):
        """ Intercept the GetFeatureInfo and add the form maptip if needed. """
        logger = Logger()
        request = self.serverInterface().requestHandler()
        # request: QgsRequestHandler
        params = request.parameterMap()

        if params.get('SERVICE', '').upper() != 'WMS':
            return

        if params.get('REQUEST', '').upper() != 'GETFEATUREINFO':
            return

        if params.get('INFO_FORMAT', '').upper() != 'TEXT/XML':
            logger.info(
                "Lizmap is only processing INFO_FORMAT=TEXT/XML, not '{}'.".format(
                    params.get('INFO_FORMAT', '').upper()))
            return

        project_path = Path(self.serverInterface().configFilePath())
        if not project_path.exists():
            logger.info(
                'The QGIS project {} does not exist as a file, not possible to process with Lizmap this '
                'request GetFeatureInfo'.format(self.serverInterface().configFilePath()))
            return

        config_path = Path(self.serverInterface().configFilePath() + '.cfg')
        if not config_path.exists():
            logger.info(
                'The QGIS project {} is not a Lizmap project, not possible to process with Lizmap this '
                'request GetFeatureInfo'.format(self.serverInterface().configFilePath()))
            return

        # str() because the plugin must be compatible Python 3.5
        with open(str(config_path), encoding='utf-8') as cfg_file:
            cfg = json.loads(cfg_file.read())

        project = QgsProject.instance()
        relation_manager = project.relationManager()

        xml = request.body().data().decode("utf-8")

        css_framework = params.get('CSS_FRAMEWORK', '')

        # noinspection PyBroadException
        try:
            features = self.feature_list_to_replace(cfg, project, relation_manager, xml, css_framework)
        except Exception as e:
            if to_bool(os.getenv("CI")):
                logger.log_exception(e)
                raise

            logger.critical(
                "Error while reading the XML response GetFeatureInfo for project {}, returning default "
                "response".format(project_path))
            logger.log_exception(e)
            return

        if not features:
            # The user has clicked in a random area on the map or no interesting LAYERS,
            # no features are returned.
            logger.info(
                f"No features found in the XML from QGIS Server for project {project_path}",
            )
            return

        logger.info(
            "Replacing the maptip from QGIS by the drag and drop expression for {} features on {}".format(
                len(features), ','.join([result.layer.name() for result in features])),
        )

        # Let's evaluate each expression popup
        exp_context = QgsExpressionContext()
        exp_context.appendScope(QgsExpressionContextUtils.globalScope())
        exp_context.appendScope(QgsExpressionContextUtils.projectScope(project))

        # retrieve geometry from getFeatureInfo project server properties
        geometry_result = QgsServerProjectUtils.wmsFeatureInfoAddWktGeometry(project)

        # noinspection PyBroadException
        try:
            for result in features:
                distance_area = QgsDistanceArea()
                distance_area.setSourceCrs(result.layer.crs(), project.transformContext())
                distance_area.setEllipsoid(project.ellipsoid())
                exp_context.appendScope(QgsExpressionContextUtils.layerScope(result.layer))

                expression = QgsServerFeatureId.getExpressionFromServerFid(
                    result.feature_id, result.layer.dataProvider())
                if expression:
                    expression_request = QgsFeatureRequest(QgsExpression(expression))
                    if not geometry_result:
                        expression_request.setFlags(QgsFeatureRequest.Flag.NoGeometry)
                    feature = QgsFeature()
                    result.layer.getFeatures(expression_request).nextFeature(feature)
                else:
                    # If not expression, the feature ID must be integer
                    feature = result.layer.getFeature(int(result.feature_id))

                if not feature.isValid():
                    logger.warning(
                        "The feature {} for layer {} is not valid, skip replacing this XML "
                        "GetFeatureInfo, continue to the next feature".format(
                            result.feature_id, result.layer.id()),
                    )
                    continue

                exp_context.setFeature(feature)
                exp_context.setFields(feature.fields())

                value = QgsExpression.replaceExpressionText(result.expression, exp_context, distance_area)
                if not value:
                    logger.warning(
                        "The GetFeatureInfo result for feature {} in layer {} is not valid, skip replacing "
                        "this XML GetFeatureInfo, , continue to the next feature".format(
                            result.feature_id, result.layer.id()),
                    )
                    continue

                if Qgis.versionInt() < 33800:
                    layer_name = result.layer.shortName()
                else:
                    layer_name = result.layer.serverProperties().shortName()

                if not layer_name:
                    layer_name = result.layer.name()
                logger.info(
                    "Replacing feature '{}' in layer '{}' for the GetFeatureInfo by the drag&drop form".format(
                        result.feature_id, layer_name))
                xml = self.append_maptip(xml, layer_name, result.feature_id, value)

            # Safeguard, it shouldn't happen
            if not xml:
                logger.critical(
                    "The new XML for the GetFeatureInfo is empty. Let's return the default previous XML")
                return

            # When we are fine, we really replace the XML of the response
            request.clear()
            request.setResponseHeader('Content-Type', 'text/xml')
            request.appendBody(bytes(xml, 'utf-8'))
            logger.info(f"GetFeatureInfo replaced for project {project_path}")

        except Exception as e:
            if to_bool(os.getenv("CI")):
                logger.log_exception(e)
                raise

            logger.critical(
                "Error while rewriting the XML response GetFeatureInfo, returning default response")
            logger.log_exception(e)
            return
