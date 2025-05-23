__copyright__ = 'Copyright 2021, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import json
import os

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from qgis.core import (
    Qgis,
    QgsFeature,
    QgsMapLayer,
    QgsProject,
    QgsVectorLayer,
)
from qgis.server import QgsRequestHandler, QgsServerResponse

from lizmap_server.logger import Logger
from lizmap_server.tools import to_bool


def write_json_response(data: Dict[str, str], response: QgsServerResponse, code: int = 200) -> None:
    """ Write data as JSON response. """
    response.setStatusCode(code)
    response.setHeader("Content-Type", "application/json")
    Logger.info(f"Sending JSON response : {data}")
    response.write(json.dumps(data))


def find_vector_layer_from_params(params, project):
    """ Trying to find the layer in the URL in the given project. """
#         params: Dict[str, str], project: QgsProject) -> tuple[bool, Union[QgsMapLayer, None]]:
    layer_name = params.get('LAYER', params.get('layer', ''))

    if not layer_name:
        return False, None

    layer = find_vector_layer(layer_name, project)

    if not layer:
        return False, None

    return True, layer


def find_layer(layer_name: str, project: QgsProject) -> Optional[QgsMapLayer]:
    """ Find layer with name, short name or layer ID. """
    found = None
    for layer in project.mapLayers().values():

        # check name
        if layer.name() == layer_name:
            found = layer
            break

        # check short name
        if Qgis.versionInt() < 33800 and layer.shortName() == layer_name:
            found = layer
            break
        elif Qgis.versionInt() >= 33800 and layer.serverProperties().shortName() == layer_name:
            found = layer
            break

        # check layer id
        if layer.id() == layer_name:
            found = layer
            break

    if not found:
        Logger.warning(
            f"The layer '{layer_name}' has not been found in the project '{project.fileName()}'")
        return None

    found: QgsMapLayer
    if not found.isValid():
        Logger.warning(
            f"The layer '{layer_name}' has been found but it is not valid in the project "
            f"'{project.fileName()}'",
        )
    return found


def find_vector_layer(layer_name: str, project: QgsProject) -> Optional[QgsVectorLayer]:
    """ Find vector layer with name, short name or layer ID. """
    layer = find_layer(layer_name, project)
    if not layer:
        return None

    if not layer.type() == QgsMapLayer.LayerType.VectorLayer:
        return None

    return layer


def get_server_fid(feature: QgsFeature, pk_attributes: list) -> str:
    """ Build server feature ID. """
    if not pk_attributes:
        return str(feature.id())

    return '@@'.join([str(feature.attribute(pk)) for pk in pk_attributes])


def get_lizmap_config(qgis_project_path: str) -> Union[Dict, None]:
    """ Get the lizmap config based on QGIS project path """

    logger = Logger()

    # Check QGIS project path
    if not os.path.exists(qgis_project_path):
        # QGIS Project path does not exist as a file
        # No Lizmap config
        return None

    # Get Lizmap config path
    config_path = qgis_project_path + '.cfg'
    if not os.path.exists(config_path):
        # Lizmap config path does not exist
        logger.info("Lizmap config does not exist")
        # No Lizmap config
        return None

    last_modified = Path(config_path).stat().st_mtime
    logger.info(f"Fetching {config_path} cfg file with last modified timestamp : {last_modified}")
    return _get_lizmap_config(config_path, last_modified)


@lru_cache(maxsize=100)
def _get_lizmap_config(config_path: str, last_modified: float) -> Union[Dict, None]:
    """ Get the lizmap config based on QGIS project path with cache. """
    # Last modified is only for LRU cache
    _ = last_modified
    logger = Logger()

    # Get Lizmap config
    with open(config_path) as cfg_file:
        # noinspection PyBroadException
        try:
            cfg = json.loads(cfg_file.read())
            if not cfg:
                # Lizmap config is empty
                logger.warning("Lizmap config is empty")
                return None
            return cfg
        except Exception as e:
            # Lizmap config is not a valid JSON file
            logger.critical("Lizmap config not well formed")
            logger.log_exception(e)
            return None


def get_lizmap_layers_config(config: Dict) -> Union[Dict, None]:
    """ Get layers Lizmap config """

    if not config:
        return None

    logger = Logger()

    # Check Lizmap config layers
    if 'layers' not in config or not config['layers']:
        # Lizmap config has no options
        logger.warning("Lizmap config has no layers")
        return None

    # Get Lizmap config layers to check it
    cfg_layers = config['layers']

    # Check that layers lizmap config is dict
    if not isinstance(cfg_layers, dict):
        logger.warning("Layers lizmap config is not dict")
        return None

    # return Lizmap config layers
    return cfg_layers


def get_lizmap_layer_login_filter(config: Dict, layer_name: str) -> Union[Dict, None]:
    """ Get loginFilteredLayers for layer """

    if not config or not isinstance(config, dict):
        return None
    if not layer_name or not isinstance(layer_name, str):
        return None

    logger = Logger()

    # Check Lizmap config loginFilteredLayers
    if 'loginFilteredLayers' not in config or not config['loginFilteredLayers']:
        # Lizmap config has no options
        logger.info("Lizmap config has no loginFilteredLayers")
        return None

    login_filtered_layers = config['loginFilteredLayers']

    # Check loginFilteredLayers for layer
    if layer_name not in login_filtered_layers or not login_filtered_layers[layer_name]:
        # Lizmap config has no options
        logger.info(f"Layer {layer_name} has no loginFilteredLayers")
        return None

    # get loginFilteredLayers for layer to check it
    cfg_layer_login_filter = login_filtered_layers[layer_name]

    # Check loginFilteredLayers for layer is dict
    if not isinstance(cfg_layer_login_filter, dict):
        logger.warning(f"loginFilteredLayers for layer {layer_name} is not dict")
        return None

    if 'layerId' not in cfg_layer_login_filter or \
            'filterAttribute' not in cfg_layer_login_filter or \
            'filterPrivate' not in cfg_layer_login_filter:
        # loginFilteredLayers for layer not well formed
        logger.warning(f"loginFilteredLayers for layer {layer_name} not well formed")
        return None

    return cfg_layer_login_filter


def get_lizmap_groups(handler: QgsRequestHandler) -> Tuple[str]:
    """ Get Lizmap user groups provided by the request """

    # Defined groups
    groups = []
    logger = Logger()

    # Get Lizmap User Groups in request headers
    headers = handler.requestHeaders()
    if headers:
        logger.info("Request headers provided")
        # Get Lizmap user groups defined in request headers
        user_groups = headers.get('X-Lizmap-User-Groups')
        if user_groups is not None:
            groups = [g.strip() for g in user_groups.split(',')]
            logger.info(f"Lizmap user groups in request headers : {','.join(groups)}")
    else:
        logger.info("No request headers provided")

    if len(groups) != 0:
        # noinspection PyTypeChecker
        return tuple(groups)

    logger.info("No lizmap user groups in request headers")

    # Get group in parameters
    params = handler.parameterMap()
    if params:
        # Get Lizmap user groups defined in parameters
        user_groups = params.get('LIZMAP_USER_GROUPS')
        if user_groups is not None:
            groups = [g.strip() for g in user_groups.split(',')]
            logger.info(f"Lizmap user groups in parameters : {','.join(groups)}")

    # noinspection PyTypeChecker
    return tuple(groups)


def get_lizmap_user_login(handler: QgsRequestHandler) -> str:
    """ Get Lizmap user login provided by the request """
    # Defined login
    login = ''

    logger = Logger()

    # Get Lizmap User Login in request headers
    headers = handler.requestHeaders()
    if headers:
        logger.info("Request headers provided")
        # Get Lizmap user login defined in request headers
        user_login = headers.get('X-Lizmap-User')
        if user_login is not None:
            login = user_login
            logger.info(f"Lizmap user login in request headers : {login}")
    else:
        logger.info("No request headers provided")

    if login:
        return login

    logger.info("No lizmap user login in request headers")

    # Get login in parameters
    params = handler.parameterMap()
    if params:
        # Get Lizmap user login defined in parameters
        user_login = params.get('LIZMAP_USER')
        if user_login is not None:
            login = user_login
            logger.info(f"Lizmap user login in parameters : {login}")

    return login


def get_lizmap_override_filter(handler: QgsRequestHandler) -> bool:
    """ Get Lizmap user login provided by the request """
    # Defined override
    override = None

    logger = Logger()

    # Get Lizmap User Login in request headers
    headers = handler.requestHeaders()
    if headers:
        logger.info("Request headers provided")
        # Get Lizmap user login defined in request headers
        override_filter = headers.get('X-Lizmap-Override-Filter')
        if override_filter is not None:
            override = to_bool(override_filter)
            logger.info("Lizmap override filter in request headers")
    else:
        logger.info("No request headers provided")

    if override is not None:
        return override

    logger.info("No lizmap override filter in request headers")

    # Get login in parameters
    params = handler.parameterMap()
    if params:
        # Get Lizmap user login defined in parameters
        override_filter = params.get('LIZMAP_OVERRIDE_FILTER')
        if override_filter is not None:
            override = to_bool(override_filter)
            logger.info("Lizmap override filter in parameters")
        else:
            override = False
            logger.info("No lizmap override filter in parameters")

    return override


def is_editing_context(handler: QgsRequestHandler) -> bool:
    """ Check if headers are defining an editing context. """
    logger = Logger()

    headers = handler.requestHeaders()
    if headers:
        editing_context = headers.get('X-Lizmap-Edition-Context')
        if editing_context is not None:
            result = to_bool(editing_context)
            logger.info(f"Lizmap editing context is found in request headers : {result}")
            return result

    logger.info("No editing context found in request headers")

    params = handler.parameterMap()
    if params:
        result = params.get('LIZMAP_EDITION_CONTEXT')
        if result is not None:
            result = to_bool(result)
            logger.info(f"Lizmap editing context is found in parameters : {result}")
            return result

    logger.info("No lizmap editing context filter in parameters : default value false")
    return False
