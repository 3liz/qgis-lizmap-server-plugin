from functools import cached_property

from itertools import chain
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from pyqgisserver.config import confservice
from pyqgisserver.plugins import plugin_list, plugin_metadata
from pyqgisserver.qgscache.cachemanager import CacheType, get_cacheservice
from qgis.core import QgsProject

from .common import (
    CatalogItem,
    ContextABC,
    ProjectCacheError,
    ServerMetadata,
    to_iso8601,
)

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

    @property
    def search_paths(self) -> List[str]:
        """ Return search paths for projects
        """
        return []

    def project(self, uri: str) -> QgsProject:
        """ Return the project specified by `uri`
        """
        details = self._cm.peek(uri)
        if details:
            return details.project

        # Find by filename
        for cache_t in (CacheType.LRU, CacheType.STATIC):
            for _, d in self._cm.items(cache_t):
                if d.project.fileName() == uri:
                    return d.project

        raise ProjectCacheError(403, f"Project not found in cache: {uri}")

    def catalog(self, search_path: Optional[str] = None) -> List[CatalogItem]:
        """ Return the catalog of projects

            location is a relative path to the root uri
        """
        rootdir = Path(confservice['projects.cache']['rootdir'])
        location = rootdir.joinpath(search_path.removesuffix('/')) if search_path else rootdir

        if not location.is_dir():
            return []

        def _items():
            glob_pattern = '**/*.%s'
            files = chain(*(location.glob(glob_pattern % sfx) for sfx in ('qgs', 'qgz')))
            for p in files:
                st = p.stat()
                yield CatalogItem(
                    uri=str(p),
                    name=p.stem,
                    storage='file',
                    last_modified=to_iso8601(st.mtime),
                    public_uri=f"/{p.relative_to(rootdir)}",
                )

        return list(_items())

    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """ return installed plugins metadata
        """
        for plugin in plugin_list():
            md = plugin_metadata(plugin)['general']
            yield (
                plugin,
                {k: (md.get(k) or md.get(k.lower(), unknown_default)) for k in keys},
            )

    @cached_property
    def metadata(self) -> ServerMetadata:
        """ Return server metadata
        """
        from pyqgisserver.version import __manifest__, __version__
        return ServerMetadata(
            name=SERVER_CONTEXT_NAME,
            version=__version__,
            build_id=__manifest__.get('buildid'),
            commit_id=__manifest__.get('commitid'),
            is_stable=not any(x in __version__ for x in ("pre", "alpha", "beta", "rc")),
        )
