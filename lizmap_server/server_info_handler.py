__copyright__ = 'Copyright 2022, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import sys
import warnings

from typing import Union

from qgis.core import Qgis
from qgis.PyQt import Qt
from qgis.PyQt.QtCore import QRegularExpression
from qgis.server import QgsServerOgcApi, QgsServerOgcApiHandler

from lizmap_server.exception import ServiceError
from lizmap_server.tools import check_environment_variable

try:
    # Py-QGIS-Server
    # noinspection PyUnresolvedReferences
    from pyqgisserver.plugins import plugin_list, plugin_metadata
    IS_PY_QGIS_SERVER = True
except ImportError:
    # FCGI and others
    from qgis.utils import pluginMetadata, server_active_plugins
    IS_PY_QGIS_SERVER = False

    def plugin_list() -> list:
        """ To match Py-QGIS-Server API."""
        return server_active_plugins

from lizmap_server.tools import to_bool

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from osgeo import gdal


def plugin_metadata_key(name: str, key: str, ) -> str:
    """ Return the version for a given plugin. """
    unknown = 'unknown'
    if IS_PY_QGIS_SERVER:
        metadata = plugin_metadata(name)
        return metadata['general'].get(key, unknown)
    else:
        value = pluginMetadata(name, key)
        if value in ("__error__", ""):
            return unknown
        else:
            return value


def py_qgis_server_version() -> str:
    """ Return the Py-QGIS-Server version or an empty string. """
    # noinspection PyBroadException
    try:
        from pyqgisserver.version import __version__
        return __version__
    except Exception:
        return ''


class ServerInfoHandler(QgsServerOgcApiHandler):

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
        if not check_environment_variable():
            raise ServiceError("Bad request error", "Invalid request", 404)

        keys = ('version', 'commitNumber', 'commitSha1', 'dateTime')
        plugins = dict()
        for plugin in plugin_list():
            plugins[plugin] = dict()
            for key in keys:
                plugins[plugin][key] = plugin_metadata_key(plugin, key)

        expected_list = (
            'wfsOutputExtension',
            'cadastre',
            'lizmap_server',
            'atlasprint',
            # waiting a little for these ones
            # 'tilesForServer',
            # 'DataPlotly',
        )

        for expected in expected_list:
            if expected not in plugins.keys():
                plugins[expected] = {'version': 'not found'}

        qgis_version_split = Qgis.QGIS_VERSION.split('-')

        services_available = []
        expected_services = ('WMS', 'WFS', 'WCS', 'WMTS', 'ATLAS', 'CADASTRE', 'EXPRESSION', 'LIZMAP')
        for service in expected_services:
            if context.serverInterface().serviceRegistry().getService(service):
                services_available.append(service)

        if Qgis.QGIS_VERSION_INT >= 31200 and Qgis.devVersion() != 'exported':
            commit_id = Qgis.devVersion()
        else:
            commit_id = ''

        data = {
            'qgis_server': {
                'metadata': {
                    'version': qgis_version_split[0],  # 3.16.0
                    'name': qgis_version_split[1],  # Hannover
                    'commit_id': commit_id,  # 288d2cacb5 if it's a dev version
                    'version_int': Qgis.QGIS_VERSION_INT,  # 31600
                    'py_qgis_server': IS_PY_QGIS_SERVER,  # bool
                    'py_qgis_server_version': py_qgis_server_version,  # str
                },
                # 'support_custom_headers': self.support_custom_headers(),
                'services': services_available,
                'plugins': plugins,
            },
            'environment': {
                'gdal': gdal.VersionInfo('VERSION_NUM'),
                'python': sys.version,
                'qt': Qt.QT_VERSION_STR,
            }
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
                "If we check custom headers"
            ),
        ]
