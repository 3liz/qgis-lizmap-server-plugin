""" Native QGIS context
"""
from itertools import chain
from pathlib import Path
from typing import (
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
)

from qgis.core import QgsProject
from qgis.utils import pluginMetadata, server_active_plugins

from .common import (
    CatalogItem,
    ContextABC,
    ProjectCacheError,
    ServerMetadata,
    to_iso8601,
)

SERVER_CONTEXT_NAME = 'FCGI'


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

    @property
    def search_paths(self) -> List[str]:
        """ Return search paths for projects
        """
        return []

    def project(self, uri: str) -> QgsProject:
        """ Return the project specified by `uri`
        """
        # TODO Fix me
        raise ProjectCacheError(403, f"Project not found in cache: {uri}")

    def catalog(self, search_path: Optional[str] = None) -> List[CatalogItem]:
        """ Return the catalog of projects

            location is a relative path to the root uri
        """
        location = Path(search_path or '.')

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
                    last_modified=to_iso8601(st.st_mtime),
                    public_uri=str(p),
                )

        return list(_items())

    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """ return installed plugins metadata
        """
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
        """ Return server metadata
        """
        return None
