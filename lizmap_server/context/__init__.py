import sys

from .common import ContextABC as ServerContext  # noqa
from .common import ProjectCacheError, model_dump_json, to_iso8601  # noqa

from ..logger import Logger


def create_server_context() -> ServerContext:
    """ Create the appropriate server context
    """
    m = sys.modules['lizmap_server']
    # Check if module has been loaded by
    # a py-qgis-server instance
    if hasattr(m, '_is_py_qgis_server'):
        from .py_qgis_server import Context
    elif hasattr(m, '_is_qjazz_server'):
        from .qjazz import Context   # type: ignore [assignment]
    else:
        from .native import Context  # type: ignore [assignment]

    context: ServerContext = Context()
    Logger.info(f"Using {context.name} context")
    return context
