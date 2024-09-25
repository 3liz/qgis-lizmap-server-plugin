import sys

from .common import ContextABC as ServerContext  # noqa
from .common import logger, model_dump_json, to_iso8601  # noqa


def create_server_context() -> ServerContext:
    """ Create the appropriate server context
    """
    m = sys.modules['lizmap_server']
    # Check if module has been loaded by
    # a py-qgis-server instance
    if hasattr(m, '_is_py_qgis_server'):
        from .py_qgis_server import Context
    elif hasattr(m, '_is_py_qgis_server2'):
        from .py_qgis_server2 import Context   # type: ignore [assignment]
    else:
        from .native import Context  # type: ignore [assignment]

    context: ServerContext = Context()
    logger.info("Using %s context", context.name)
    return context
