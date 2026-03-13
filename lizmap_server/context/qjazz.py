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

from qjazz_core.qgis import QgisPluginService
from qjazz_core import logger
from qjazz_cache.prelude import CacheEntry, CacheManager, ProjectMetadata
from qjazz_cache.prelude import CheckoutStatus as Co


from .common import (
    ContextABC,
    ServerMetadata,
)

if TYPE_CHECKING:
    from typing import TypeVar

    LayerDetails = TypeVar("LayerDetails")


SERVER_CONTEXT_NAME = "QJazz"


class Context(ContextABC):
    def __init__(self):
        self._cm = CacheManager.get_service()

    def _checkout(self, uri: str) -> Tuple[ProjectMetadata | CacheEntry, Co]:
        return self._cm.checkout(
            self._cm.resolve_path(uri, allow_direct=False),
        )

    @property
    def name(self) -> str:
        return SERVER_CONTEXT_NAME

    @property
    def git_repository_url(self) -> str:
        return "https://github.com/3liz/qjazz"

    @property
    def documentation_url(self) -> str:
        return ""

    def load_project_def(
        self,
        md: Any,
        *,
        with_details: bool,
        with_layouts: bool,
    ) -> Tuple[Optional[QgsProject], Dict[str, "LayerDetails"]]:

        from ..api import builder

        if isinstance(md, Url):
            md = md.geturl()

        if isinstance(md, str):
            match self._checkout(md):
                case Co.REMOVED | Co.NOTFOUND:
                    return None, {}
                case _:
                    pass
        elif not isinstance(md, ProjectMetadata):
            raise ValueError(f"QJazz: Invalid project locator: {md}")

        details: dict[str, "LayerDetails"] = {}

        def load(uri: str) -> QgsProject:
            nonlocal details
            project, details = builder.open_project_def(  # type: ignore [assignment]
                uri,
                with_details=with_details,
                with_layouts=with_layouts,
            )
            if not project:
                logger.error(f"Failed to load project {uri}")
                raise FileNotFoundError(uri)
            return project

        handler = self._cm.get_protocol_handler(md.scheme)
        try:
            project = handler.load_project(md, load)
        except FileNotFoundError:
            return None, {}

        return project, details

    def collect_projects(self, location: str) -> Iterator[tuple[Any, str]]:
        """Collect all projects from 'location'"""
        return self._cm.collect_projects(location)

    def resolve_path(self, location: str) -> Optional[Url]:
        """Return the url corresponding to the public path"""
        try:
            return self._cm.resolve_path(location)
        except CacheManager.ResourceNotAllowed:
            return None

    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """return installed plugins metadata"""
        service = QgisPluginService.get_service()

        for plugin in service.plugins:
            md = plugin.metadata["general"]
            logger.trace("== PLUGIN METADATA(%s): %s", plugin.name, md)
            yield (
                plugin.path.name,
                {k: (md.get(k) or md.get(k.lower(), unknown_default)) for k in keys},
            )

    @cached_property
    def metadata(self) -> ServerMetadata:
        """Return server metadata"""
        from importlib import metadata
        from qjazz_core import manifest

        commit = manifest.get_manifest().commit_id

        version = metadata.version("qjazz-contrib")
        return ServerMetadata(
            name=SERVER_CONTEXT_NAME,
            commit_id=commit,
            version=version,
            is_stable=not any(x in version for x in ("pre", "alpha", "beta", "rc", "dev")),
        )
