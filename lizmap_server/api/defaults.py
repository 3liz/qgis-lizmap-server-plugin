"""Get default paths for projects

## Define how to search for projects:

* Define LIZMAP_PROJECTS_SEARCH_PATH as the default search route for projects this route will
  be matched against the PATH request.

* Define the LIZMAP_PROJECTS_URL as the projects mapped url for the route specified below.

Note this is not used with QJazz because QJazz has its own configuration for project
retrieval

"""

import functools
import os

from itertools import chain
from pathlib import Path, PurePosixPath
from typing import (
    Any,
    Iterator,
    Optional,
    Union,
    Tuple,
    cast,
)
from urllib.parse import SplitResult as Url, urlsplit

from .conditions import assert_precondition
from .routes import Route, build_route

from . import logger

SEARCH_PATH_ENV = "LIZMAP_PROJECTS_SEARCH_PATH"
PROJECTS_URI_ENV = "LIZMAP_PROJECTS_URI"


def verify_config():
    """Verify configuration

    Raises an error if the configuration is not valid
    """
    if projects_search_path() and not project_uri():
        logger.critical(
            "A LIZMAP_PROJECTS_SEARCH_PATH environment variable is defined but not LIZMAP_PROJECTS_URI",
        )
        raise RuntimeError("Missing LIZMAP_PROJECTS_URI environment variables")


def resolve_project_uri(path: Union[PurePosixPath, str]) -> Optional[Url]:
    """Resolve project path and return a projects uri for
    that path.
    """
    route = projects_search_path()
    if not route:
        return None

    path = PurePosixPath(path)
    assert_precondition(path.is_absolute(), "Search path must be absolute")

    uri = cast("str", project_uri())
    assert_precondition(
        uri is not None,
        "No default projects LIZMAP_PROJECTS_URI template defined",
    )

    result = route.resolve_path(path)
    if not result:
        return None

    args, location = result
    if route.is_dynamic:
        rooturl = urlsplit(uri.format_map(args))
    else:
        rooturl = urlsplit(uri)

    # Get relative path
    path = path.relative_to(location)
    # Check for {path} template in rooturl
    query = rooturl.query.format(path=path)
    if query != rooturl.query:
        url = rooturl._replace(query=query)
    else:
        # Simply append path to the rooturl path
        url = rooturl._replace(path=str(PurePosixPath(rooturl.path, path)))

    return url


def collect_projects(context: str, location: str) -> Iterator[Tuple[Any, str]]:
    """Collect projects from location"""
    url = resolve_project_uri(location)
    if not url:
        return

    scheme = url.scheme or "file"
    if scheme != "file":
        logger.warning(f"{context} context does not support project's scheme '{scheme}'")
    else:
        path = Path(url.path)
        if not path.exists():
            logger.error(f"{path} does not exists")
            return

        if path.is_dir():
            globpattern = "**/*.%s"
            files = chain(*(path.glob(globpattern % sfx) for sfx in ("qgs", "qgz")))
            for p in files:
                yield urlsplit(f"file:{p}"), str(Path(location, p.relative_to(path)))
        else:
            yield url, location


@functools.cache
def projects_search_path() -> Optional[Route]:
    """Returns the default route from the environment

    Used when qjazz cache is not available
    """
    path_template = os.getenv(SEARCH_PATH_ENV)
    if path_template:
        return build_route(path_template)

    return None


@functools.cache
def project_uri() -> Optional[str]:
    """Return the projects url"""
    return os.getenv(PROJECTS_URI_ENV)
