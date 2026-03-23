"""Legacy server info handler to use as fallback
when requirements are not availables.
"""

import traceback


from qgis.PyQt.QtCore import QRegularExpression
from qgis.server import (
    QgsServerInterface,
    QgsServerOgcApi,
    QgsServerOgcApiHandler,
)

from .tools import version
from .context import create_server_context
from .server_info import server_info

from . import logger

class ServerInfoHandler(QgsServerOgcApiHandler):
    def __init__(self):
        super().__init__()
        self._context = create_server_context()
        logger.info(f"Server information handler using context '{self._context.name}'")

    def path(self):
        return QRegularExpression("server.json")

    def summary(self):
        return "Server information"

    def description(self):
        return "Get info about the current QGIS server"

    def operationId(self):
        return "server"

    def linkTitle(self):
        return "Handler Lizmap API server info"

    def linkType(self):
        return QgsServerOgcApi.data

    def handleRequest(self, context):
        #
        # Catch exception so that we have a
        # stacktrace, otherwise only the error is output
        # but without the stacktrace.
        #
        try:
            self.write(
                server_info(self._context, context.serverInterface()),
                context,
            )
        except Exception:
            logger.critical(traceback.format_exc())
            raise


def register_server_info_handler(server_iface: QgsServerInterface):
    """Register legacy lizmap api endpoint"""

    service_registry = server_iface.serviceRegistry()

    # Register API
    lizmap_api = QgsServerOgcApi(server_iface, "/lizmap", "Lizmap", "The Lizmap API endpoint", version())
    service_registry.registerApi(lizmap_api)
    lizmap_api.registerHandler(ServerInfoHandler())
    logger.info('API "/lizmap" loaded with the server info handler')

