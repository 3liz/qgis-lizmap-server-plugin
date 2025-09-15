from functools import cached_property
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from qjazz_core.qgis import QgisPluginService
from qjazz_core import logger
from qjazz_cache.prelude import CacheEntry, CacheManager, ProjectMetadata
from qjazz_cache.prelude import CheckoutStatus as Co

from qgis.core import QgsProject

from .common import (
    ContextABC,
    ProjectCacheError,
    ServerMetadata,
)


SERVER_CONTEXT_NAME = 'QJazz'


class Context(ContextABC):

    def __init__(self):
        self._cm = CacheManager.get_service()

    def _checkout(self, uri: str) -> Tuple[ProjectMetadata | CacheEntry, Co]:
        return self._cm.checkout(
            self._cm.resolve_path(uri, allow_direct=True),
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

    @property
    def search_paths(self) -> List[str]:
        """ Return search paths for projects
        """
        return list(self._cm.conf.search_paths)

    def project(self, uri: str) -> Optional[QgsProject]:
        """ Return the project in cache specified by `uri`
        """
        md, co_status = self._checkout(uri)

        rv = None

        match co_status:
            case Co.UNCHANGED | Co.NEEDUPDATE:
                rv = md.project
            case Co.NEW:
                raise ProjectCacheError(403, f"Requested project not in cache: {uri}")
            case Co.NOTFOUND:
                # Unexistent project
                raise ProjectCacheError(404, f"Requested project not found: {uri}")
            case Co.REMOVED:
                # Do not return a removed project
                # Since layer's data may not exist
                # anymore
                raise ProjectCacheError(410, f"Requested removed project: {uri}")

        return rv

    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """ return installed plugins metadata
        """
        service = QgisPluginService.get_service()

        for plugin in service.plugins:
            md = plugin.metadata['general']
            logger.trace("== PLUGIN METADATA(%s): %s", plugin.name, md)
            yield (
                plugin.path.name,
                {k: (md.get(k) or md.get(k.lower(), unknown_default)) for k in keys},
            )

    @cached_property
    def metadata(self) -> ServerMetadata:
        """ Return server metadata
        """
        from importlib import metadata
        from qjazz_core import manifest

        commit = manifest.get_manifest().commit_id

        version = metadata.version('qjazz-contrib')
        return ServerMetadata(
            name=SERVER_CONTEXT_NAME,
            commit_id=commit,
            version=version,
            is_stable=not any(x in version for x in ("pre", "alpha", "beta", "rc", "dev")),
        )
