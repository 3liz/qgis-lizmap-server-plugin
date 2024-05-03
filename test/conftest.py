import configparser
import glob
import logging
import os
import sys
import warnings

from typing import Any, Dict, Generator, Optional

import pytest

from qgis.core import Qgis, QgsApplication, QgsFontUtils, QgsProject
from qgis.PyQt import Qt
from qgis.server import (
    QgsBufferServerRequest,
    QgsBufferServerResponse,
    QgsServer,
    QgsServerInterface,
    QgsServerRequest,
)

from .utils import OWSResponse

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from osgeo import gdal

logging.basicConfig(stream=sys.stderr)
logging.disable(logging.NOTSET)

LOGGER = logging.getLogger('server')
LOGGER.setLevel(logging.DEBUG)


qgis_application = None


def pytest_addoption(parser):
    parser.addoption("--qgis-plugins", metavar="PATH", help="Plugin path", default=None)


plugin_path = None


def pytest_report_header(config):
    message = 'QGIS : {}\n'.format(Qgis.QGIS_VERSION_INT)
    message += 'Python GDAL : {}\n'.format(gdal.VersionInfo('VERSION_NUM'))
    message += 'Python : {}\n'.format(sys.version)
    # message += 'Python path : {}'.format(sys.path)
    message += 'QT : {}'.format(Qt.QT_VERSION_STR)
    return message


def pytest_configure(config):
    global plugin_path
    plugin_path = config.getoption('qgis_plugins')


def pytest_sessionstart(session):
    """ Start qgis application
    """
    global qgis_application
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    # Define this in global environment
    # os.environ['QGIS_DISABLE_MESSAGE_HOOKS'] = 1
    # os.environ['QGIS_NO_OVERRIDE_IMPORT'] = 1
    qgis_application = QgsApplication([], False)
    qgis_application.initQgis()

    # Install logger hook
    install_logger_hook(verbose=True)


# Note from Etienne 22/03/2022
# Switching from 3.10 to 3.16 is crashing when a test is failing
# def pytest_sessionfinish(session, exitstatus):
#     """ End qgis session
#     """
#     global qgis_application
#     qgis_application.exitQgis()
#     del qgis_application


@pytest.fixture(scope='session')
def client(request):
    """ Return a qgis server instance
    """
    class _Client:

        def __init__(self):
            self.fontFamily = QgsFontUtils.standardTestFontFamily()
            QgsFontUtils.loadStandardTestFonts(['All'])

            # Activate debug headers
            os.environ['QGIS_WMTS_CACHE_DEBUG_HEADERS'] = 'true'

            self.datapath = request.config.rootdir.join('data')
            self.server = QgsServer()

            # Load plugins
            load_plugins(self.server.serverInterface())

        def getplugin(self, name: str) -> Any:   # noqa ANN401
            """ Return the instance of the plugin
            """
            return server_plugins.get(name)

        def getprojectpath(self, name: str) -> str:
            return self.datapath.join(name)

        def get_project(self, name: str) -> QgsProject:
            projectpath = self.getprojectpath(name)
            if Qgis.QGIS_VERSION_INT >= 32601:
                qgsproject = QgsProject(capabilities=Qgis.ProjectCapabilities())
            else:
                qgsproject = QgsProject()
            if not qgsproject.read(projectpath.strpath):
                raise ValueError("Error reading project '%s':" % projectpath.strpath)
            return qgsproject

        def get(
                self,
                query: str,
                project: Optional[str] = None,
                headers: Optional[Dict[str, str]] = None,
            ) -> OWSResponse:
            """ Return server response from query
            """
            if headers is None:
                headers = {}
            server_request = QgsBufferServerRequest(query, QgsServerRequest.GetMethod, headers, None)
            response = QgsBufferServerResponse()
            if project is not None and not os.path.isabs(project):
                qgsproject = self.get_project(project)
            else:
                qgsproject = None
            self.server.handleRequest(server_request, response, project=qgsproject)
            return OWSResponse(response)

        def get_with_project(
            self, query: str,
            project: QgsProject,
            headers: Optional[Dict[str, str]] = None,
        ) -> OWSResponse:
            """ Return server response from query
            """
            if headers is None:
                headers = {}

            server_request = QgsBufferServerRequest(query, QgsServerRequest.GetMethod, headers, None)
            response = QgsBufferServerResponse()
            self.server.handleRequest(server_request, response, project=project)
            return OWSResponse(response)

    return _Client()


##
# Plugins
##

def checkQgisVersion(minver: str, maxver: str) -> bool:

    def to_int(ver):
        major, *ver = ver.split('.')
        major = int(major)
        minor = int(ver[0]) if len(ver) > 0 else 0
        rev = int(ver[1]) if len(ver) > 1 else 0
        if minor >= 99:
            minor = rev = 0
            major += 1
        if rev > 99:
            rev = 99
        return int("{:d}{:02d}{:02d}".format(major, minor, rev))

    version = to_int(Qgis.QGIS_VERSION.split('-')[0])
    minver = to_int(minver) if minver else version
    maxver = to_int(maxver) if maxver else version
    return minver <= version <= maxver


def find_plugins(pluginpath: str) -> Generator[str, None, None]:
    """ Load plugins
    """
    for plugin in glob.glob(os.path.join(plugin_path + "/*")):
        if not os.path.exists(os.path.join(plugin, '__init__.py')):
            continue

        metadatafile = os.path.join(plugin, 'metadata.txt')
        if not os.path.exists(metadatafile):
            continue

        cp = configparser.ConfigParser()
        try:
            with open(metadatafile, mode='rt') as f:
                cp.read_file(f)
            if not cp['general'].getboolean('server'):
                logging.critical("%s is not a server plugin", plugin)
                continue

            minver = cp['general'].get('qgisMinimumVersion')
            maxver = cp['general'].get('qgisMaximumVersion')
        except Exception as exc:
            LOGGER.critical("Error reading plugin metadata '%s': %s", metadatafile, exc)
            continue

        if not checkQgisVersion(minver, maxver):
            LOGGER.critical(("Unsupported version for %s:"
                "\n MinimumVersion: %s"
                "\n MaximumVersion: %s"
                "\n Qgis version: %s"
                "\n Discarding") % (plugin, minver, maxver,
                    Qgis.QGIS_VERSION.split('-')[0]))
            continue

        yield os.path.basename(plugin)


server_plugins: Dict[str, Any] = {}


def load_plugins(serverIface: QgsServerInterface) -> None:
    """ Start all plugins
    """
    if not plugin_path:
        return

    LOGGER.info("Initializing plugins from %s", plugin_path)
    sys.path.append(plugin_path)

    for plugin in find_plugins(plugin_path):
        try:
            __import__(plugin)

            package = sys.modules[plugin]

            # Initialize the plugin
            server_plugins[plugin] = package.serverClassFactory(serverIface)
            LOGGER.info("Loaded plugin %s", plugin)
        except:
            LOGGER.error("Error loading plugin %s", plugin)
            raise


#
# Logger hook
#

def install_logger_hook(verbose: bool = False) -> None:
    """ Install message log hook
    """
    from qgis.core import Qgis, QgsApplication

    # Add a hook to qgis  message log
    def writelogmessage(message, tag, level):
        arg = '{}: {}'.format(tag, message)
        if level == Qgis.Warning:
            LOGGER.warning(arg)
        elif level == Qgis.Critical:
            LOGGER.error(arg)
        elif verbose:
            # Qgis is somehow very noisy
            # log only if verbose is set
            LOGGER.info(arg)

    messageLog = QgsApplication.messageLog()
    messageLog.messageReceived.connect(writelogmessage)
