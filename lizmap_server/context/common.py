import json

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import SplitResult as Url

from qgis.core import QgsProject


def to_iso8601(dt: Union[float, datetime]) -> str:
    if isinstance(dt, float):
        dt = datetime.fromtimestamp(dt)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


class DataclassEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


if TYPE_CHECKING:
    from typing import TypeVar

    LayerDetails = TypeVar("LayerDetails")


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
        """Return context name"""
        ...

    @property
    @abstractmethod
    def git_repository_url(self) -> str:
        """Return Git repository URL"""
        ...

    @property
    @abstractmethod
    def documentation_url(self) -> str:
        """Return documentation URL"""
        ...

    @abstractmethod
    def load_project_def(
        self,
        md: Any,
        *,
        with_details: bool,
        with_layouts: bool,
    ) -> Tuple[Optional[QgsProject], Dict[str, "LayerDetails"]]:
        """Load a project definition

        A project definition is project loaded without its layers. It is
        used by the api to build metadata about the project.
        """
        ...

    @abstractmethod
    def collect_projects(self, location: str) -> Iterator[Tuple[Any, str]]:
        """Collect all projects from 'location'"""
        ...

    @abstractmethod
    def resolve_path(self, location: str) -> Optional[Url]:
        """Return the url corresponding to the public path"""
        ...

    @abstractmethod
    def installed_plugins(
        self,
        keys: Sequence[str],
        unknown_default: Optional[str] = None,
    ) -> Iterator[Tuple[str, Dict]]:
        """return installed plugin metadata"""
        ...

    @property
    @abstractmethod
    def metadata(self) -> Optional[ServerMetadata]:
        """Return server metadata if the server
        is not a native (FCGI) server
        """
        ...
