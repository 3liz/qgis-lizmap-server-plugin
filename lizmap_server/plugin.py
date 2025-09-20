__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from qgis.server import QgsServerInterface, QgsServerOgcApi

from lizmap_server.expression_service import ExpressionService
from lizmap_server.get_feature_info import GetFeatureInfoFilter
from lizmap_server.get_legend_graphic import GetLegendGraphicFilter
from lizmap_server.legend_onoff_filter import (
    LegendOnOffAccessControl,
    LegendOnOffFilter,
)
from lizmap_server.lizmap_accesscontrol import LizmapAccessControlFilter
from lizmap_server.lizmap_filter import LizmapFilter
from lizmap_server.lizmap_service import LizmapService
from lizmap_server.logger import Logger
from lizmap_server.plausible import Plausible
from lizmap_server.server_info_handler import ServerInfoHandler
from lizmap_server.tools import check_environment_variable, version


class LizmapServer:
    """Plugin for QGIS server
    this plugin loads Lizmap filter"""

    def __init__(self, server_iface: QgsServerInterface) -> None:
        self.server_iface = server_iface
        self.logger = Logger()
        self.version = version()
        self.logger.info(f'Init server version "{self.version}"')
        # noinspection PyBroadException
        try:
            self.plausible = Plausible()
            self.plausible.request_stat_event()
        except Exception as e:
            self.logger.log_exception(e)
            self.logger.critical('Error while calling the API stats')

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
        self.logger.info('API "/lizmap" loaded with the server info handler')

        check_environment_variable()

        # Register service
        try:
            service_registry.registerService(ExpressionService())
        except Exception as e:
            self.logger.critical(f'Error loading service "expression" : {e}')
            raise
        self.logger.info('Service "expression" loaded')

        try:
            service_registry.registerService(LizmapService(self.server_iface))
        except Exception as e:
            self.logger.critical(f'Error loading service "lizmap" : {e}')
            raise
        self.logger.info('Service "lizmap" loaded')

        try:
            server_iface.registerFilter(LizmapFilter(self.server_iface), 50)
        except Exception as e:
            self.logger.critical(f'Error loading filter "lizmap" : {e}')
            raise
        self.logger.info('Filter "lizmap" loaded')

        try:
            server_iface.registerAccessControl(LizmapAccessControlFilter(self.server_iface), 100)
        except Exception as e:
            self.logger.critical(f'Error loading access control "lizmap" : {e}')
            raise
        self.logger.info('Access control "lizmap" loaded')

        try:
            server_iface.registerFilter(GetFeatureInfoFilter(self.server_iface), 150)
        except Exception as e:
            self.logger.critical(f'Error loading filter "get feature info" : {e}')
            raise
        self.logger.info('Filter "get feature info" loaded')

        try:
            server_iface.registerFilter(GetLegendGraphicFilter(self.server_iface), 170)
        except Exception as e:
            self.logger.critical(f'Error loading filter "get legend graphic" : {e}')
            raise
        self.logger.info('Filter "get legend graphic" loaded')

        try:
            server_iface.registerFilter(LegendOnOffFilter(self.server_iface), 175)
        except Exception as e:
            self.logger.critical(f'Error loading filter "legend on/off" : {e}')
            raise
        self.logger.info('Filter "legend on/off" loaded')

        try:
            server_iface.registerAccessControl(LegendOnOffAccessControl(self.server_iface), 175)
        except Exception as e:
            self.logger.critical(f'Error loading access control "legend on/off" : {e}')
            raise
        self.logger.info('Access control "legend on/off" loaded')
