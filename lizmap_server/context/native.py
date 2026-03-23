"""Native QGIS context"""

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

from qgis.utils import pluginMetadata, server_active_plugins
from qgis.core import QgsProject

from .common import (
    ContextABC,
    ServerMetadata,
)

SERVER_CONTEXT_NAME = "FCGI"

if TYPE_CHECKING:
    from typing import TypeVar

    LayerDetails = TypeVar("LayerDetails")


class Context(ContextABC):
    @property
    def name(self) -> str:
        return SERVER_CONTEXT_NAME

    @property
    def git_repository_url(self) -> str:
        return "https://github.com/qgis/QGIS"

    @property
    def documentation_url(self) -> str:
        return "https://docs.qgis.org/latest/en/docs/server_manual/"

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

        def _get_key(name, key):
            value = pluginMetadata(name, key)
            if value not in ("__error__", ""):
                return value
            value = pluginMetadata(name.lower(), key)
            if value not in ("__error__", ""):
                return value
            return unknown_default

        for plugin in server_active_plugins:
            yield plugin, {k: _get_key(plugin, k) for k in keys}

    @property
    def metadata(self) -> Optional[ServerMetadata]:
        """Return server metadata"""
        return None
