import configparser
import logging
import os
import sys
import warnings

from pathlib import Path

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


qgis_application = None


@pytest.fixture(scope="session", autouse=True)
def set_env():
    os.environ["QGIS_SERVER_LIZMAP_REVEAL_SETTINGS"] = "TRUE"
    os.environ["CI"] = "True"


def pytest_report_header(config):
    message = (
        f"QGIS : {Qgis.QGIS_VERSION_INT}\n"
        f"Python GDAL : {gdal.VersionInfo('VERSION_NUM')}\n"
        f"Python : {sys.version}\n"
        f"QT : {Qt.QT_VERSION_STR}"
    )
    return message


def pytest_sessionstart(session):
    """Start qgis application"""
    global qgis_application
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

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


@pytest.fixture(scope="session")
def client(request):
    """Return a qgis server instance"""

    class _Client:
        def __init__(self):
            self.fontFamily = QgsFontUtils.standardTestFontFamily()
            QgsFontUtils.loadStandardTestFonts(["All"])

            # Activate debug headers
            os.environ["QGIS_WMTS_CACHE_DEBUG_HEADERS"] = "true"

            rootdir = Path(request.config.rootdir.strpath)

            self.datapath = rootdir.joinpath("data")
            self.server = QgsServer()

            # Load plugins
            load_plugins(self.server.serverInterface(), rootdir.parent)

        def getplugin(self, name: str) -> Any:  # noqa ANN401
            """Return the instance of the plugin"""
            return server_plugins.get(name)

        def getprojectpath(self, name: str) -> Path:
            return self.datapath.joinpath(name)

        def get_project(self, name: str) -> QgsProject:
            projectpath = self.getprojectpath(name)
            if Qgis.QGIS_VERSION_INT >= 32601:
                qgsproject = QgsProject(capabilities=Qgis.ProjectCapabilities())
            else:
                qgsproject = QgsProject()
            if not qgsproject.read(str(projectpath)):
                raise ValueError(f"Error reading project '{projectpath}'")
            return qgsproject

        def get(
            self,
            query: str,
            project: Optional[str] = None,
            headers: Optional[Dict[str, str]] = None,
        ) -> OWSResponse:
            """Return server response from query"""
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
            self,
            query: str,
            project: QgsProject,
            headers: Optional[Dict[str, str]] = None,
        ) -> OWSResponse:
            """Return server response from query"""
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
        major, *ver = ver.split(".")
        major = int(major)
        minor = int(ver[0]) if len(ver) > 0 else 0
        rev = int(ver[1]) if len(ver) > 1 else 0
        if minor >= 99:
            minor = rev = 0
            major += 1
        if rev > 99:
            rev = 99
        return int(f"{major:d}{minor:02d}{rev:02d}")

    version = to_int(Qgis.QGIS_VERSION.split("-")[0])
    minver = to_int(minver) if minver else version
    maxver = to_int(maxver) if maxver else version
    return minver <= version <= maxver


def find_plugins(pluginpath: Path) -> Generator[str, None, None]:
    """Load plugins"""
    for plugin in pluginpath.glob("*"):
        if not plugin.joinpath("__init__.py").exists():
            continue

        metadatafile = plugin.joinpath("metadata.txt")
        if not metadatafile.exists():
            continue

        cp = configparser.ConfigParser()
        with metadatafile.open() as f:
            cp.read_file(f)
        if not cp["general"].getboolean("server"):
            logging.error("%s is not a server plugin", plugin)
            continue

        minver = cp["general"].get("qgisMinimumVersion")
        maxver = cp["general"].get("qgisMaximumVersion")

        if not checkQgisVersion(minver, maxver):
            logging.critical(
                f"Unsupported version for {plugin}:"
                f"\n MinimumVersion: {minver}"
                f"\n MaximumVersion: {maxver}"
                f"\n Qgis version: {Qgis.QGIS_VERSION.split('-')[0]}"
                "\n Discarding",
            )
            continue

        yield plugin.name


server_plugins: Dict[str, Any] = {}


def load_plugins(serverIface: QgsServerInterface, pluginpath: Path) -> None:
    """Start all plugins"""
    logging.info("Initializing plugins from %s", pluginpath)
    sys.path.append(str(pluginpath))

    for plugin in find_plugins(pluginpath):
        try:
            __import__(plugin)

            package = sys.modules[plugin]

            # Initialize the plugin
            server_plugins[plugin] = package.serverClassFactory(serverIface)
            logging.info("Loaded plugin %s", plugin)
        except:
            logging.error("Error loading plugin %s", plugin)
            raise


#
# Logger hook
#


def install_logger_hook(verbose: bool = False) -> None:
    """Install message log hook"""
    from qgis.core import Qgis, QgsApplication

    # Add a hook to qgis  message log
    def writelogmessage(message, tag, level):
        arg = f"{tag}: {message}"
        if level == Qgis.MessageLevel.Warning:
            logging.warning(arg)
        elif level == Qgis.MessageLevel.Critical:
            logging.error(arg)
        elif verbose:
            # Qgis is somehow very noisy
            # log only if verbose is set
            logging.info(arg)

    messageLog = QgsApplication.messageLog()
    messageLog.messageReceived.connect(writelogmessage)
