"""Route definition as templated path

Ex: '/srv/accounts/{client}/data'

Will create a pattern matching and a formatter for matching and retrieving
parameters.

Partial match (i.e pattern found at the beginning) or exact match are supported.

* A '{ident}' form  is a path component with no separator.
* A '{ident:<re>} is a regular expression pattern.

For example, "/srv/{NAME}/data]{PATH:.*}" will match "/srv/foo/data/end/of/path" with
NAME=='foo' and PATH='end/of/path'
"""

import re

from dataclasses import dataclass
from pathlib import PurePosixPath

from typing import (
    Callable,
    Dict,
    Final,
    Optional,
    Pattern,
    Protocol,
    Tuple,
    TYPE_CHECKING,
)

from qgis.server import (
    QgsServerRequest,
)

from .conditions import assert_postcondition
from .errors import HTTPMethodNotAllowed, HTTPNotFound

from . import logger

if TYPE_CHECKING:
    from .request import HTTPRequestDelegate

#
# Routes
#

ROUTE_RE: Final[Pattern[str]] = re.compile(r"(\{[_a-zA-Z][^{}]*(?:\{[^{}]*\}[^{}]*)*\})")
PATH_SEP: Final[str] = re.escape("/")


class Route(Protocol):
    @property
    def is_dynamic(self) -> bool: ...

    def match(self, path: str) -> Optional[Dict[str, str]]:
        """Partial match

        Check if location starts with the corresponding pattern
        """
        ...

    def full_match(self, path: str) -> Optional[Dict[str, str]]:
        """Exact match"""
        ...

    def resolve_path(self, path: PurePosixPath) -> Optional[Tuple[Dict[str, str], str]]: ...


class StaticRoute(Route):
    is_dynamic: Final[bool] = False

    def __init__(self, location: str):
        self._location = location

    def match(self, path: str) -> Optional[Dict[str, str]]:
        return {} if self._location.startswith(path) else None

    def full_match(self, path: str) -> Optional[Dict[str, str]]:
        return {} if self._location == path else None

    def resolve_path(self, path: PurePosixPath) -> Optional[Tuple[Dict[str, str], str]]:
        if path.is_relative_to(self._location):
            return {}, self._location

        return None


class DynamicRoute(Route):
    is_dynamic: Final[bool] = True

    DYN = re.compile(r"\{(?P<var>[_a-zA-Z][_a-zA-Z0-9]*)\}")
    DYN_WITH_RE = re.compile(r"\{(?P<var>[_a-zA-Z][_a-zA-Z0-9]*):(?P<re>.+)\}")
    GOOD = r"[^{}/]+"

    def __init__(self, location: str):
        self._location = location

        # Build the dynamic pattern
        pattern = ""
        formatter = ""

        for part in ROUTE_RE.split(location):
            pmatch = self.DYN.fullmatch(part)
            if pmatch:
                pattern += "(?P<{}>{})".format(pmatch.group("var"), self.GOOD)
                formatter += "{" + pmatch.group("var") + "}"
                continue

            pmatch = self.DYN_WITH_RE.fullmatch(part)
            if pmatch:
                pattern += "(?P<{var}>{re})".format(**pmatch.groupdict())
                formatter += "{" + pmatch.group("var") + "}"
                continue

            if "{" in part or "}" in part:
                raise ValueError(f"Invalid path '{location}'['{part}']")

            formatter += part
            pattern += re.escape(part)

        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Bad pattern '{pattern}': {exc}") from None

        assert_postcondition(compiled.pattern.startswith(PATH_SEP))
        assert_postcondition(formatter.startswith("/"))
        self._pattern = compiled
        self._formatter = formatter

    def match(self, location: str) -> Optional[Dict[str, str]]:
        pmatch = self._pattern.match(location)
        return pmatch.groupdict() if pmatch else None

    def full_match(self, location: str) -> Optional[Dict[str, str]]:
        """Full match"""
        pmatch = self._pattern.fullmatch(location)
        return pmatch.groupdict() if pmatch else None

    def resolve_path(self, path: PurePosixPath) -> Optional[Tuple[Dict[str, str], str]]:
        """Resolve relative path"""
        args = self.match(str(path))
        if args:
            location = self._formatter.format_map(args)
            if path.is_relative_to(location):
                return (args, location)

        return None


#
# Route definition
#

METHODS = {
    "head": QgsServerRequest.HeadMethod,
    "put": QgsServerRequest.PutMethod,
    "get": QgsServerRequest.GetMethod,
    "post": QgsServerRequest.PostMethod,
    "patch": QgsServerRequest.PatchMethod,
    "delete": QgsServerRequest.DeleteMethod,
}


class HandlerFn(Protocol):
    def __call__(self, request: "HTTPRequestDelegate", **kwargs) -> None: ...


@dataclass
class RouteDef:
    me: QgsServerRequest.Method
    route: Route
    fn: HandlerFn
    method: str
    path: str
    doc: bool


ROUTES: list[RouteDef] = []


def build_route(location: str) -> Route:
    if not ("{" in location or "}" in location or ROUTE_RE.search(location)):
        return StaticRoute(location)
    return DynamicRoute(location)


def find_route(me: QgsServerRequest.Method, path: str) -> tuple[RouteDef, dict[str, str]]:
    candidate = None
    for r in ROUTES:
        if r.me == me:
            candidate = r
            values = r.route.full_match(path)
            if values is not None:
                return (r, values)

    if not candidate:
        raise HTTPMethodNotAllowed

    raise HTTPNotFound()


def route(method: str, path: str, *, doc: bool = True) -> Callable[[HandlerFn], HandlerFn]:
    me = METHODS[method]
    route = build_route(path)

    logger.debug(f"Adding route: {path} [{method}]")

    def inner(fn: HandlerFn) -> HandlerFn:
        ROUTES.append(
            RouteDef(
                me=me,
                route=route,
                fn=fn,
                method=method,
                path=path,
                doc=doc,
            )
        )
        return fn

    return inner


def get(path: str, **kwargs) -> Callable[[HandlerFn], HandlerFn]:
    return route("get", path, **kwargs)


def post(path: str, **kwargs) -> Callable[[HandlerFn], HandlerFn]:
    return route("post", path, **kwargs)
