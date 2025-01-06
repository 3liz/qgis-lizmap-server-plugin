__copyright__ = 'Copyright 2022, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import os
import sys
import traceback
import warnings

from typing import Union

from qgis.core import Qgis
from qgis.PyQt import Qt
from qgis.PyQt.QtCore import QRegularExpression
from qgis.PyQt.QtGui import QFontDatabase
from qgis.server import (
    QgsServerOgcApi,
    QgsServerOgcApiHandler,
)

from lizmap_server.exception import ServiceError
from lizmap_server.tools import check_environment_variable, to_bool
from lizmap_server.tos_definitions import (
    BING_KEY,
    GOOGLE_KEY,
    strict_tos_check,
)

from .context import create_server_context

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from osgeo import gdal

from .logger import Logger


PLUGIN_METADATA_KEYS = (
    # 'name' is not the folder name in the 'expected_list' variable,
    # it can be different
    'name',
    'version',
    'commitNumber',
    'commitSha1',
    'dateTime',
    'repository',
    'homepage',
)

DATA_PLOTLY = "DataPlotly"
EXPECTED_PLUGINS = (
    'wfsOutputExtension',
    # 'cadastre', very specific for the French use-case
    'lizmap_server',
    'atlasprint',
    # waiting a little for these one
    # 'tilesForServer',
    # DATA_PLOTLY,  # Special case for this one, depending on the hosting infrastructure
)

EXPECTED_SERVICES = ('WMS', 'WFS', 'WCS', 'WMTS', 'EXPRESSION', 'LIZMAP')


class ServerInfoHandler(QgsServerOgcApiHandler):

    def __init__(self):
        super().__init__()
        self._context = create_server_context()
        Logger.info(f"Server information handler using context '{self._context.name}'")

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
            self._handleRequest(context)
        except Exception:
            Logger.critical(traceback.format_exc())
            raise

    def _handleRequest(self, context):
        if not check_environment_variable():
            raise ServiceError("Bad request error", "Invalid request", 404)

        server_metadata = self._context.metadata

        plugins = dict(self._context.installed_plugins(PLUGIN_METADATA_KEYS))

        for expected in EXPECTED_PLUGINS:
            if expected not in plugins:
                plugins[expected] = {
                    'version': 'Not found',
                    'name': expected,
                }

        # Lizmap Cloud allocated ressources
        allocated_ressources = os.getenv("LZM_ALLOCATION_MODE", "")
        if allocated_ressources != "" and DATA_PLOTLY not in plugins.keys():
            if allocated_ressources == "shared":
                version = 'Not available on the "Basic" Lizmap Cloud plan'
            else:
                # allocated_ressources == "dedicated"
                version = 'Not installed'

            plugins[DATA_PLOTLY] = {
                'version': version,
                'name': DATA_PLOTLY,
                'homepage': 'https://github.com/ghtmtt/DataPlotly/blob/master/README.md',
            }

        # 3.28 : Firenze
        # 3.30 : 's-Hertogenbosch
        human_version, human_name = Qgis.QGIS_VERSION.split('-', 1)

        services_available = []
        for service in EXPECTED_SERVICES:
            if context.serverInterface().serviceRegistry().getService(service):
                services_available.append(service)

        if Qgis.devVersion() != 'exported':
            commit_id = Qgis.devVersion()
        else:
            commit_id = ''

        # noinspection PyBroadException
        try:
            # Format the tag according to QGIS git repository
            tag = f"final-{human_version.replace('.', '_')}"  # final-3_16_0
        except Exception:
            tag = ""

        if server_metadata:
            qgis_server_meta = dict(
                found=True,
                name=server_metadata.name,
                version=server_metadata.version,
                build_id=server_metadata.build_id,
                commit_id=server_metadata.commit_id,
                stable=server_metadata.is_stable,
                git_repository_url=self._context.git_repository_url,
                documentation_url=self._context.documentation_url,
            )
        else:
            qgis_server_meta = dict(found=False, version="not used")

        data = {
            # Only the "qgis_server" section is forwarded in LWC source code
            'qgis_server': {
                'metadata': {
                    'version': human_version,  # 3.16.0
                    'tag': tag,  # final-3_16_0
                    'name': human_name,  # Hannover
                    'commit_id': commit_id,  # 288d2cacb5 if it's a dev version
                    'version_int': Qgis.QGIS_VERSION_INT,  # 31600
                },
                'py_qgis_server': qgis_server_meta,
                'external_providers_tos_checks': {
                    GOOGLE_KEY.lower(): strict_tos_check(GOOGLE_KEY),
                    BING_KEY.lower(): strict_tos_check(BING_KEY),
                },
                # 'support_custom_headers': self.support_custom_headers(),
                'services': services_available,
                'plugins': plugins,
                'fonts': QFontDatabase().families(),
            },
            'environment': {
                'gdal': gdal.VersionInfo('VERSION_NUM'),
                'python': sys.version,
                'qt': Qt.QT_VERSION_STR,
            },
        }
        self.write(data, context)

    def support_custom_headers(self) -> Union[None, bool]:
        """ Check if this QGIS Server supports custom headers.

         Returns None if the check is not requested with the GET parameter CHECK_CUSTOM_HEADERS

         If requested, returns boolean if X-Check-Custom-Headers is found in headers.
         """
        handler = self.serverIface().requestHandler()

        params = handler.parameterMap()
        if not to_bool(params.get('CHECK_CUSTOM_HEADERS')):
            return None

        headers = handler.requestHeaders()
        return headers.get('X-Check-Custom-Headers') is not None

    def parameters(self, context):
        from qgis.server import QgsServerQueryStringParameter
        return [
            QgsServerQueryStringParameter(
                "CHECK_CUSTOM_HEADERS",
                False,
                QgsServerQueryStringParameter.Type.String,
                "If we check custom headers",
            ),
        ]
