"""Tests for the server contexts."""

import json
import sys

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

import pytest

from lizmap_server import context
from lizmap_server.context.common import (
    ContextABC,
    DataclassEncoder,
    ProjectCacheError,
    ServerMetadata,
    model_dump_json,
    to_iso8601,
)


def test_context_to_iso8601():
    """Timestamps and datetimes must be converted to ISO 8601."""
    dt = datetime(2024, 5, 6, 12, 0, 0, tzinfo=timezone.utc)
    assert to_iso8601(dt) == "2024-05-06T12:00:00.000+00:00"

    # A POSIX timestamp is accepted too
    assert to_iso8601(dt.timestamp()) == "2024-05-06T12:00:00.000+00:00"


def test_context_dataclass_encoder():
    """Dataclasses must be serializable as JSON."""
    md = ServerMetadata(name="Test", version="1.0.0", is_stable=True)
    assert json.loads(model_dump_json({"md": md}))["md"]["name"] == "Test"

    with pytest.raises(TypeError):
        json.dumps({"obj": object()}, cls=DataclassEncoder)


def test_context_project_cache_error():
    """The project cache error keeps the code and the message."""
    error = ProjectCacheError(410, "Gone")
    assert error.code == 410
    assert error.msg == "Gone"
    assert str(error) == "Gone"


def test_context_abstract_methods():
    """The abstract methods of the context must be callable from a subclass."""

    class MyContext(ContextABC):
        @property
        def name(self):
            return super().name

        @property
        def git_repository_url(self):
            return super().git_repository_url

        @property
        def documentation_url(self):
            return super().documentation_url

        def load_project_def(self, md, *, with_details, with_layouts):
            return super().load_project_def(md, with_details=with_details, with_layouts=with_layouts)

        def collect_projects(self, location):
            return super().collect_projects(location)

        def resolve_path(self, location):
            return super().resolve_path(location)

        def installed_plugins(self, keys, unknown_default=None):
            return super().installed_plugins(keys, unknown_default)

        @property
        def metadata(self):
            return super().metadata

    ctx = MyContext()
    assert ctx.name is None
    assert ctx.git_repository_url is None
    assert ctx.documentation_url is None
    assert ctx.load_project_def(None, with_details=False, with_layouts=False) is None
    assert ctx.collect_projects("/data") is None
    assert ctx.resolve_path("/data") is None
    assert ctx.installed_plugins(()) is None
    assert ctx.metadata is None


#
# Native (FCGI) context
#


def test_context_native_urls():
    """The native context must return the QGIS urls."""
    ctx = context.create_server_context()
    assert ctx.name == "FCGI"
    assert ctx.git_repository_url.startswith("https://")
    assert ctx.documentation_url.startswith("https://")
    assert ctx.metadata is None


def test_context_native_load_project_def(rootdir):
    """The native context accepts a path, a file url and a remote url."""
    from lizmap_server.context.native import Context

    ctx = Context()

    uri = f"{rootdir}/data/montpellier/montpellier.qgs"

    project, _ = ctx.load_project_def(uri, with_details=False, with_layouts=False)
    assert project is not None

    project, _ = ctx.load_project_def(urlsplit(f"file://{uri}"), with_details=False, with_layouts=False)
    assert project is not None

    # Not a local file, the url is passed as is to QGIS and cannot be loaded
    project, details = ctx.load_project_def(
        urlsplit("postgresql://user@host/db?project=foo"),
        with_details=False,
        with_layouts=False,
    )
    assert project is None
    assert details == {}

    with pytest.raises(ValueError):
        ctx.load_project_def(42, with_details=False, with_layouts=False)


def test_context_native_installed_plugins(monkeypatch):
    """The native context must read the metadata of the active server plugins."""
    from lizmap_server.context import native

    monkeypatch.setattr(native, "server_active_plugins", ["Lizmap_server", "atlasprint"])

    def _plugin_metadata(name, key):
        if name == "atlasprint":
            # Found with the plugin name as is
            return {"version": "3.4.5"}.get(key, "")
        if name != "lizmap_server":
            # Only found with the lower case plugin name
            return "__error__"
        return {"version": "1.2.3"}.get(key, "")

    monkeypatch.setattr(native, "pluginMetadata", _plugin_metadata)

    ctx = native.Context()
    plugins = dict(ctx.installed_plugins(("version", "author"), unknown_default="unknown"))
    assert plugins == {
        "Lizmap_server": {"version": "1.2.3", "author": "unknown"},
        "atlasprint": {"version": "3.4.5", "author": "unknown"},
    }


def test_context_native_collect_and_resolve(rootdir):
    """The native context delegates to the default implementation."""
    from lizmap_server.context.native import Context

    ctx = Context()
    assert len(list(ctx.collect_projects("/data"))) > 0

    url = ctx.resolve_path("/data/legend")
    assert url is not None
    assert url.path == f"{rootdir}/data/legend"


#
# Alternate contexts
#
# The 'py-qgis-server' and 'QJazz' packages are not available when running the
# tests: the modules they provide are stubbed so that the contexts may be
# exercised anyway.
#


def _module(name: str, **attrs) -> ModuleType:
    mod = ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


@pytest.fixture
def clear_context_cache():
    """Reset the cached server context."""
    context.create_server_context.cache_clear()
    yield
    context.create_server_context.cache_clear()


@pytest.fixture
def py_qgis_server_stubs(monkeypatch):
    """Stub of the 'pyqgisserver' package."""

    def plugin_list():
        return ("wfsOutputExtension", "lizmap_server")

    def plugin_metadata(name):
        return {"general": {"version": "1.0.0", "author": "3Liz"}}

    root = _module("pyqgisserver")
    plugins = _module("pyqgisserver.plugins", plugin_list=plugin_list, plugin_metadata=plugin_metadata)
    qgscache = _module("pyqgisserver.qgscache")
    cachemanager = _module(
        "pyqgisserver.qgscache.cachemanager",
        get_cacheservice=lambda: object(),
    )
    version = _module(
        "pyqgisserver.version",
        __version__="1.9.0",
        __manifest__={"buildid": 42, "commitid": 1234},
    )

    for name, mod in (
        ("pyqgisserver", root),
        ("pyqgisserver.plugins", plugins),
        ("pyqgisserver.qgscache", qgscache),
        ("pyqgisserver.qgscache.cachemanager", cachemanager),
        ("pyqgisserver.version", version),
    ):
        monkeypatch.setitem(sys.modules, name, mod)

    # Ensure the context module is imported again with the stubs
    monkeypatch.delitem(sys.modules, "lizmap_server.context.py_qgis_server", raising=False)
    yield
    sys.modules.pop("lizmap_server.context.py_qgis_server", None)


def test_context_py_qgis_server(py_qgis_server_stubs, clear_context_cache, rootdir, monkeypatch):
    """The py-qgis-server context must be selected and usable."""
    monkeypatch.setattr(sys.modules["lizmap_server"], "_is_py_qgis_server", True, raising=False)

    ctx = context.create_server_context()
    assert ctx.name == "Py-QGIS-Server"
    assert ctx.git_repository_url == "https://github.com/3liz/py-qgis-server"
    assert ctx.documentation_url == "https://docs.3liz.org/py-qgis-server/"

    md = ctx.metadata
    assert md.name == "Py-QGIS-Server"
    assert md.version == "1.9.0"
    assert md.build_id == 42
    assert md.commit_id == 1234
    assert md.is_stable is True

    # 'Author' is not defined but its lower case version is
    plugins = dict(ctx.installed_plugins(("version", "Author", "email"), unknown_default="unknown"))
    assert plugins["lizmap_server"] == {"version": "1.0.0", "Author": "3Liz", "email": "unknown"}

    # Project loading and path resolution are the default ones
    uri = f"{rootdir}/data/montpellier/montpellier.qgs"
    project, _ = ctx.load_project_def(urlsplit(f"file://{uri}"), with_details=False, with_layouts=False)
    assert project is not None

    project, details = ctx.load_project_def(
        urlsplit("postgresql://user@host/db?project=foo"),
        with_details=False,
        with_layouts=False,
    )
    assert project is None and details == {}

    # A plain path is accepted too
    project, _ = ctx.load_project_def(uri, with_details=False, with_layouts=False)
    assert project is not None

    with pytest.raises(ValueError):
        ctx.load_project_def(42, with_details=False, with_layouts=False)

    assert len(list(ctx.collect_projects("/data"))) > 0
    assert ctx.resolve_path("/data/legend") is not None


@pytest.fixture
def qjazz_stubs(monkeypatch, rootdir):
    """Stub of the 'qjazz' packages."""
    from enum import Enum

    class CheckoutStatus(Enum):
        UNCHANGED = 0
        NEEDUPDATE = 1
        REMOVED = 2
        NOTFOUND = 3
        NEW = 4

    @dataclass
    class ProjectMetadata:
        uri: str
        scheme: str = "file"

    @dataclass
    class CacheEntry:
        md: ProjectMetadata

    class ProtocolHandler:
        def load_project(self, md, loader):
            return loader(md.uri)

    class CacheManager:
        class ResourceNotAllowed(Exception):
            pass

        @classmethod
        def get_service(cls):
            return cls()

        def resolve_path(self, uri, allow_direct=False):
            if uri.startswith("/forbidden"):
                raise CacheManager.ResourceNotAllowed(uri)
            return urlsplit(f"file://{rootdir}{uri}")

        def checkout(self, url):
            if url.path.endswith("unknown.qgs"):
                return ProjectMetadata(uri=url.path), CheckoutStatus.NOTFOUND
            # The project is already in the cache
            return CacheEntry(md=ProjectMetadata(uri=url.path)), CheckoutStatus.UNCHANGED

        def collect_projects(self, location):
            yield ProjectMetadata(uri=f"{rootdir}/data/legend.qgs"), location

        def get_protocol_handler(self, scheme):
            return ProtocolHandler()

    class Plugin:
        def __init__(self, path, metadata):
            self.path = Path(path)
            self.name = self.path.name
            self.metadata = metadata

    class QgisPluginService:
        @staticmethod
        def get_service():
            service = QgisPluginService()
            service.plugins = (
                Plugin("/plugins/lizmap_server", {"general": {"version": "1.0.0", "author": "3Liz"}}),
            )
            return service

    logger_stub = _module(
        "qjazz_core.logger",
        error=lambda *args, **kwargs: None,
        trace=lambda *args, **kwargs: None,
    )

    @dataclass
    class Manifest:
        commit_id: str = "abcdef"

    core = _module("qjazz_core", logger=logger_stub)
    qgis = _module("qjazz_core.qgis", QgisPluginService=QgisPluginService)
    manifest = _module("qjazz_core.manifest", get_manifest=lambda: Manifest())
    cache = _module("qjazz_cache")
    prelude = _module(
        "qjazz_cache.prelude",
        CacheEntry=CacheEntry,
        CacheManager=CacheManager,
        ProjectMetadata=ProjectMetadata,
        CheckoutStatus=CheckoutStatus,
    )

    for name, mod in (
        ("qjazz_core", core),
        ("qjazz_core.logger", logger_stub),
        ("qjazz_core.qgis", qgis),
        ("qjazz_core.manifest", manifest),
        ("qjazz_cache", cache),
        ("qjazz_cache.prelude", prelude),
    ):
        monkeypatch.setitem(sys.modules, name, mod)

    monkeypatch.delitem(sys.modules, "lizmap_server.context.qjazz", raising=False)
    yield prelude
    sys.modules.pop("lizmap_server.context.qjazz", None)


def test_context_qjazz(qjazz_stubs, clear_context_cache, rootdir, monkeypatch):
    """The QJazz context must be selected and usable."""
    monkeypatch.setattr(sys.modules["lizmap_server"], "_is_qjazz_server", True, raising=False)
    monkeypatch.setattr("importlib.metadata.version", lambda name: "1.0.0-rc1")

    ctx = context.create_server_context()
    assert ctx.name == "QJazz"
    assert ctx.git_repository_url == "https://github.com/3liz/qjazz"
    assert ctx.documentation_url == ""

    md = ctx.metadata
    assert md.name == "QJazz"
    assert md.commit_id == "abcdef"
    assert md.is_stable is False

    # 'Author' is not defined but its lower case version is
    plugins = dict(ctx.installed_plugins(("version", "Author", "email"), unknown_default="unknown"))
    assert plugins["lizmap_server"] == {"version": "1.0.0", "Author": "3Liz", "email": "unknown"}

    assert len(list(ctx.collect_projects("/data"))) == 1

    assert ctx.resolve_path("/data/legend.qgs") is not None
    assert ctx.resolve_path("/forbidden/legend.qgs") is None

    # The internal checkout helper
    md, _ = ctx._checkout("/data/legend.qgs")
    assert md.md.uri.endswith("/data/legend.qgs")

    with pytest.raises(ValueError):
        ctx.load_project_def(42, with_details=False, with_layouts=False)


def test_context_qjazz_load_project(qjazz_stubs, clear_context_cache, rootdir, monkeypatch):
    """The QJazz context must load projects from the cache manager."""
    monkeypatch.setattr(sys.modules["lizmap_server"], "_is_qjazz_server", True, raising=False)

    prelude = qjazz_stubs
    ctx = context.create_server_context()

    # From an url, the project is already in the cache manager
    url = urlsplit(f"file://{rootdir}/data/montpellier/montpellier.qgs")
    project, _ = ctx.load_project_def(url, with_details=False, with_layouts=False)
    assert project is not None

    # Project not found in the cache
    project, details = ctx.load_project_def(
        urlsplit(f"file://{rootdir}/data/unknown.qgs"),
        with_details=False,
        with_layouts=False,
    )
    assert project is None and details == {}

    # From a project metadata
    md = prelude.ProjectMetadata(uri=f"{rootdir}/data/montpellier/montpellier.qgs")
    project, _ = ctx.load_project_def(md, with_details=False, with_layouts=False)
    assert project is not None

    # The project cannot be loaded
    project, details = ctx.load_project_def(
        prelude.ProjectMetadata(uri=f"{rootdir}/data/i_do_not_exists.qgs"),
        with_details=False,
        with_layouts=False,
    )
    assert project is None and details == {}
