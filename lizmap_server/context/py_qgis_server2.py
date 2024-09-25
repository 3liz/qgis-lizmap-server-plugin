
from functools import cached_property
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from py_qgis_contrib.core.qgis import QgisPluginService
from py_qgis_cache import CacheEntry, CacheManager, ProjectMetadata
from py_qgis_cache import CheckoutStatus as Co

from qgis.core import QgsProject

from .common import (
    CatalogItem,
    ContextABC,
    ProjectCacheError,
    ServerMetadata,
    to_iso8601,
)

SERVER_CONTEXT_NAME = 'py-qgis-server2'


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
                # Since layer's data may not exists
                # anymore
                raise ProjectCacheError(410, f"Requested removed project: {uri}")
        return rv

    def catalog(self, search_path: Optional[str] = None) -> List[CatalogItem]:
        """ Return the catalog of projects
        """
        return [
            CatalogItem(
                uri=md.uri,
                name=md.name,
                storage=md.storage,
                last_modified=to_iso8601(md.last_modified),
                public_uri=public_path,
            ) for md, public_path in self._cm.collect_projects(search_path)
        ]

    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """ return installed plugins metadata
        """
        srvc = QgisPluginService.get_service()

        for plugin in srvc.plugins:
            md = plugin.metadata
            yield (
                plugin,
                {k: (md.get(k) or md.get(k.lower(), unknown_default)) for k in keys},
            )

    @cached_property
    def metadata(self) -> ServerMetadata:
        """ Return server metadata
        """
        from importlib import metadata
        version = metadata.version('py_qgis_cache')
        return ServerMetadata(
            name=SERVER_CONTEXT_NAME,
            version=version,
            is_stable=not any(x in version for x in ("pre", "alpha", "beta", "rc", "dev")),
        )