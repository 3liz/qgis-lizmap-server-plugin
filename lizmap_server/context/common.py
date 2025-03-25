import json

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union

from qgis.core import QgsProject


def to_iso8601(dt: Union[float, datetime]) -> str:
    if isinstance(dt, float):
        dt = datetime.fromtimestamp(dt)
    return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds')


class DataclassEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


@dataclass
class CatalogItem:
    uri: str
    name: str
    storage: str
    last_modified: str
    public_uri: str


@dataclass(frozen=True)
class ServerMetadata:
    name: str
    version: str
    is_stable: bool
    build_id: Optional[int] = None
    commit_id: Optional[int] = None


def model_dump_json(o: Dict) -> str:
    return json.dumps(o, cls=DataclassEncoder)


class ProjectCacheError(Exception):
    def __init__(self, code: int, msg: Optional[str] = None):
        super().__init__(msg)
        self.msg = msg
        self.code = code


class ContextABC(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """ Return context name
        """
        ...

    @property
    @abstractmethod
    def git_repository_url(self) -> str:
        """ Return Git repository URL
        """
        ...

    @property
    @abstractmethod
    def documentation_url(self) -> str:
        """ Return documentation URL
        """
        ...

    @property
    @abstractmethod
    def search_paths(self) -> List[str]:
        """ Return search paths for projects
        """
        ...

    @abstractmethod
    def project(self, uri: str) -> QgsProject:
        """ Return the project specified by `uri`
        """
        ...

    @abstractmethod
    def catalog(self, search_path: Optional[str] = None) -> List[CatalogItem]:
        """ Return the projects catalog
        """
        ...

    @abstractmethod
    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """ return installed plugin metadata
        """
        ...

    @property
    @abstractmethod
    def metadata(self) -> Optional[ServerMetadata]:
        """ Return server metadata if the server
            is not a native (FCGI) server
        """
        ...
