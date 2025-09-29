

from qgis.server import QgsServerInterface, QgsServerOgcApi

from .expression_service import ExpressionService
from .get_feature_info import GetFeatureInfoFilter
from .get_legend_graphic import GetLegendGraphicFilter
from .legend_onoff_filter import (
    LegendOnOffAccessControl,
    LegendOnOffFilter,
)
from .lizmap_accesscontrol import LizmapAccessControlFilter
from .lizmap_filter import LizmapFilter
from .lizmap_service import LizmapService
from .plausible import Plausible
from .server_info_handler import ServerInfoHandler
from .tools import check_environment_variable, version

from . import logger


class LizmapServer:
    """Plugin for QGIS server
    this plugin loads Lizmap filter"""

    def __init__(self, server_iface: QgsServerInterface):
        self.server_iface = server_iface
        self.version = version()
        logger.info(f'Init server version "{self.version}"')
        # noinspection PyBroadException
        try:
            self.plausible = Plausible()
            self.plausible.request_stat_event()
        except Exception as e:
            logger.log_exception(e)
            logger.critical('Error while calling the API stats')

        service_registry = server_iface.serviceRegistry()

        # Register API
        lizmap_api = QgsServerOgcApi(
            self.server_iface,
            '/lizmap',
            'Lizmap',
            'The Lizmap API endpoint',
            self.version)
        service_registry.registerApi(lizmap_api)
        lizmap_api.registerHandler(ServerInfoHandler())
        logger.info('API "/lizmap" loaded with the server info handler')

        check_environment_variable()

        # Register service
        try:
            service_registry.registerService(ExpressionService(self.server_iface))
        except Exception as e:
            logger.critical(f'Error loading service "expression" : {e}')
            raise
        logger.info('Service "expression" loaded')

        try:
            service_registry.registerService(LizmapService(self.server_iface))
        except Exception as e:
            logger.critical(f'Error loading service "lizmap" : {e}')
            raise
        logger.info('Service "lizmap" loaded')

        try:
            server_iface.registerFilter(LizmapFilter(self.server_iface), 50)
        except Exception as e:
            logger.critical(f'Error loading filter "lizmap" : {e}')
            raise
        logger.info('Filter "lizmap" loaded')

        try:
            server_iface.registerAccessControl(LizmapAccessControlFilter(self.server_iface), 100)
        except Exception as e:
            logger.critical(f'Error loading access control "lizmap" : {e}')
            raise
        logger.info('Access control "lizmap" loaded')

        try:
            server_iface.registerFilter(GetFeatureInfoFilter(self.server_iface), 150)
        except Exception as e:
            logger.critical(f'Error loading filter "get feature info" : {e}')
            raise
        logger.info('Filter "get feature info" loaded')

        try:
            server_iface.registerFilter(GetLegendGraphicFilter(self.server_iface), 170)
        except Exception as e:
            logger.critical(f'Error loading filter "get legend graphic" : {e}')
            raise
        logger.info('Filter "get legend graphic" loaded')

        try:
            server_iface.registerFilter(LegendOnOffFilter(self.server_iface), 175)
        except Exception as e:
            logger.critical(f'Error loading filter "legend on/off" : {e}')
            raise
        logger.info('Filter "legend on/off" loaded')

        try:
            server_iface.registerAccessControl(LegendOnOffAccessControl(self.server_iface), 175)
        except Exception as e:
            logger.critical(f'Error loading access control "legend on/off" : {e}')
            raise
        logger.info('Access control "legend on/off" loaded')
