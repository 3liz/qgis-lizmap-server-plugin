
from . import logger

#
# Check availability of dependencies
#

from qgis.server import QgsServerInterface

from .tools import check_environment_variable

def register_lizmap_api(server_iface: QgsServerInterface):
    try:
        from pydantic import __version__ as pydantic_version
    except ImportError:
        pydantic_version = None  # type: ignore [assignment]

    try:
        from pydantic_extra_types import __version__ as pydantic_extra_types_version
    except ImportError:
        pydantic_extra_types_version = None # type: ignore [assignment]

    # Do not register if not enabled
    if not check_environment_variable():
        logger.warning("Lizmap api endpoint disabled")
        return

    if pydantic_version and pydantic_extra_types_version:
        from .api.handler import LizmapApi

        logger.info("Lizmap api endpoint enabled")
        service_registry = server_iface.serviceRegistry()
        service_registry.registerApi(LizmapApi(server_iface))
    else:
        from .legacy_server_info_handler import register_server_info_handler

        logger.warning(
            "Pydantic is not installed but it is required for activatiting the full lizmap api.\n"
            "Only server info api will be available."
        )
        register_server_info_handler(server_iface)


