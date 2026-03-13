from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    Optional,
    Sequence,
    Tuple,
)
from urllib.parse import SplitResult as Url

from qgis.core import QgsProject

from pyqgisserver.plugins import plugin_list, plugin_metadata
from pyqgisserver.qgscache.cachemanager import get_cacheservice

from .common import (
    ContextABC,
    ServerMetadata,
)


if TYPE_CHECKING:
    from typing import TypeVar

    LayerDetails = TypeVar("LayerDetails")


SERVER_CONTEXT_NAME = "Py-QGIS-Server"


class Context(ContextABC):
    def __init__(self):
        self._cm = get_cacheservice()

    @property
    def name(self) -> str:
        return SERVER_CONTEXT_NAME

    @property
    def git_repository_url(self) -> str:
        return "https://github.com/3liz/py-qgis-server"

    @property
    def documentation_url(self) -> str:
        return "https://docs.3liz.org/py-qgis-server/"

    def load_project_def(
        self,
        md: Any,
        *,
        with_details: bool,
        with_layouts: bool,
    ) -> Tuple[Optional[QgsProject], Dict[str, "LayerDetails"]]:
        from ..api import builder

        if isinstance(md, Url):
            if md.scheme in ("file", ""):
                md = md.path
            else:
                md = md.geturl()
        elif not isinstance(md, str):
            raise ValueError(f"Invalid uri: {md}")

        return builder.open_project_def(
            md,
            with_details=with_details,
            with_layouts=with_layouts,
        )  # type: ignore [return-value]

    def collect_projects(self, location: str) -> Iterator[Tuple[Any, str]]:
        """Collect all projects from 'location'"""
        from ..api import defaults

        return defaults.collect_projects(SERVER_CONTEXT_NAME, location)

    def resolve_path(self, location: str) -> Optional[Url]:
        """Return the url corresponding to the public path"""
        from ..api import defaults

        return defaults.resolve_project_uri(location)

    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """return installed plugins metadata"""
        for plugin in plugin_list():
            md = plugin_metadata(plugin)["general"]
            yield (
                plugin,
                {k: (md.get(k) or md.get(k.lower(), unknown_default)) for k in keys},
            )

    @cached_property
    def metadata(self) -> ServerMetadata:
        """Return server metadata"""
        from pyqgisserver.version import __manifest__, __version__

        return ServerMetadata(
            name=SERVER_CONTEXT_NAME,
            version=__version__,
            build_id=__manifest__.get("buildid"),
            commit_id=__manifest__.get("commitid"),
            is_stable=not any(x in __version__ for x in ("pre", "alpha", "beta", "rc")),
        )
