import sys
import traceback

from typing import (
    Dict,
    Iterator,
    Sequence,
    Tuple,
    cast,
)
from urllib.parse import quote

from qgis.PyQt.QtCore import QUrl
from qgis.core import QgsProject
from qgis.server import (
    QgsServerApi,
    QgsServerApiContext,
    QgsServerInterface,
)

from ..tools import plugin_path
from ..server_info import server_info

from . import builder
from . import logger
from . import routes

from .errors import HTTPError
from .models import Link
from .request import HTTPRequestDelegate

from .schemas import (
    JsonModel,
    LayerDetails,
    LayoutDescription,
    LayoutSummary,
    ProjectDescription,
    ProjectSummary,
)

from .landingpage import v1

from . import swagger

#
# Routes
#


class ProjectSummaryResponse(ProjectSummary):
    links: Sequence[Link]


def project_summary(project: QgsProject, links: Sequence[Link]) -> ProjectSummaryResponse:
    """Returns project summary"""
    return ProjectSummaryResponse(
        title=project.title() or project.baseName(),
        version=project.lastSaveVersion().text(),
        save_date_time=builder.project_last_save_datetime(project),
        links=links,
    )


class ProjectSummaries(JsonModel):
    projects: Sequence[ProjectSummaryResponse]
    links: Sequence[Link]


swagger.model(ProjectSummary)
swagger.model(ProjectDescription)
swagger.model(LayerDetails)



@routes.get(v1("projects/list/{PATH:.*}"))
def get_projects(request: HTTPRequestDelegate, **match_info):
    """
    summary: List projects
    description: |
        List available projects
    tags:
        - project
    responses:
        "200":
            description: >
                The list of project summaries
            content:
                application/json:
                    schema:
                        $ref: '#/definitions/ProjectSummaries'
    """
    location = f"/{match_info.get('PATH')}"

    context = request.server_context

    def collect_projects() -> Iterator[ProjectSummary]:
        logger.debug(f"Collecting projects at '{location}'")
        for md, url in context.collect_projects(location):
            project, _ = context.load_project_def(md, with_details=False, with_layouts=False)
            if not project:
                logger.error(f"Failed to open project at {md}")
                continue
            yield project_summary(
                project,
                [
                    Link.makelink(
                        request,
                        rel="related",
                        path=v1(f"projects/description?p={url}"),
                    ),
                ],
            )

    request.write_json(
        ProjectSummaries(
            projects=list(collect_projects()),
            links=[Link.makelink(request, rel="self", path=v1("projects/list/"))],
        )
    )


def load_project_def(
    request: HTTPRequestDelegate,
    *,
    with_layouts: bool,
    with_details: bool,
) -> Tuple[str, QgsProject, Dict[str, LayerDetails]]:
    location = request.query.get("p")
    if not location:
        raise HTTPError(400, reason="Missing project 'p' parameters")

    context = request.server_context

    project: QgsProject = None
    url = context.resolve_path(location)
    if url:
        project, details = context.load_project_def(
            url,
            with_layouts=with_layouts,
            with_details=with_details,
        )

    if not project:
        raise HTTPError(404, reason="Not found")

    return location, project, details


@routes.get(v1("projects/description"))
def get_project_description(request: HTTPRequestDelegate, **match_info):
    """
    summary: Project description
    description: |
        Return a project description
    parameters:
      - in: query
        name: map
        schema:
            type: string
        required: true
        description: The project path
    tags:
        - project
    responses:
        "200":
            description: >
                The project's description
            content:
                application/json:
                    schema:
                        $ref: '#/definitions/ProjectDescription'
        "404":
            description: >
                The project does not exists
            content:
                application/json:
                    schema:
                        #ref: '#/definitions/ErrorResponse'
    """
    _, project, details = load_project_def(request, with_layouts=True, with_details=False)

    layers = {
        id_: builder.layer_description(
            layer,
            project,
            details,
        )
        for id_, layer in project.mapLayers().items()
    }

    request.write_json(builder.project_description(project, layers))


@routes.get(v1("projects/layers/{Id}"))
def get_project_layers(request: HTTPRequestDelegate, **match_info):
    """
    summary: Project's layer details
    description: |
        Return the project layers details for layer {Id}
    parameters:
      - in: path
        name: Id
        schema:
            type: string
        required: true
        description: Project's layer id
      - in: query
        name: p
        schema:
            type: string
        required: true
        description: The project path
    tags:
        - project
    responses:
        "200":
            description: >
                The project's layer details
            content:
                application/json:
                    schema:
                        $ref: '#/definitions/LayerDetails'
        "404":
            description: >
                The layer does not exists
            content:
                application/json:
                    schema:
                        #ref: '#/definitions/ErrorResponse'
    """
    loc, _, details = load_project_def(request, with_layouts=False, with_details=True)
    layer_id = match_info["Id"]

    layer_details = cast("LayerDetails", details.get(layer_id))
    if not layer_details:
        raise HTTPError(404, reason="Layer not found")

    layer_details.links = [  # type: ignore [union-attr]
        Link.makelink(request, rel="self", path=v1(f"projects/layers/{layer_id}?p={loc}")),
    ]
    request.write_json(layer_details)


#
#  Project's layout
#

swagger.model(LayoutDescription)


@swagger.model
class LayoutSummaries(JsonModel):
    layouts: Sequence[LayoutSummary]


@routes.get(v1("projects/layouts/"))
def get_project_layouts(request: HTTPRequestDelegate, **match_info):
    """
    summary: Project's layout summary
    description: |
        Return the project layout summaries
    parameters:
      - in: query
        name: p
        schema:
            type: string
        required: true
        description: The project path
    tags:
        - layout
    responses:
        "200":
            description: >
                The `roject's layout summaries
            content:
                application/json:
                    schema:
                        $ref: '#/definitions/LayoutSummaries'
        "404":
            description: >
                The project does not exists
            content:
                application/json:
                    schema:
                        #ref: '#/definitions/ErrorResponse'
    """
    uri, project, _ = load_project_def(request, with_layouts=True, with_details=False)

    def layouts() -> Iterator[LayoutSummary]:
        for layout in builder.project_layouts(project):
            layout.links = [  # type: ignore [attr-defined]
                Link.makelink(
                    request,
                    rel="related",
                    path=v1(f"projects/layouts/{quote(layout.name)}?p={uri}"),
                    title=layout.name,
                ),
            ]
            yield layout

    summaries = LayoutSummaries(layouts=list(layouts()))
    summaries.links = [Link.makelink(request, rel="self", path=v1("projects/layouts/"))]  # type: ignore [attr-defined]

    request.write_json(summaries)


@routes.get(v1("projects/layouts/{Name}"))
def get_layout(request: HTTPRequestDelegate, **match_info):
    """
    summary: Project's layout details
    description: |
        Return the project's layout details for layout {Id}
    parameters:
      - in: path
        name: Name
        schema:
            type: string
        required: true
        description: Project's layout name
      - in: query
        name: p
        schema:
            type: string
        required: true
        description: The project path
    tags:
        - layout
    responses:
        "200":
            description: >
                The project's layer details
            content:
                application/json:
                    schema:
                        $ref: '#/definitions/LayoutDescription'
        "404":
            description: >
                The layout or the project does not exists
            content:
                application/json:
                    schema:
                        #ref: '#/definitions/ErrorResponse'
    """
    _, project, _ = load_project_def(request, with_layouts=True, with_details=False)

    layout_name = match_info["Name"]

    layout = builder.project_layout(project, layout_name)
    if not layout:
        raise HTTPError(404, reason="Layout not found")

    request.write_json(layout)


#
# Lizmap server info
#
@routes.get("/server.json", doc=False)
def get_server_info(request: HTTPRequestDelegate, **match_info):
    request.write_json(server_info(request.server_context, request.serverInterface))


#
# Open api
#
@routes.get(v1(""), doc=False)
def openapi(request: HTTPRequestDelegate, **match_info):
    content = plugin_path("api").joinpath("openapi.json").read_bytes()
    request.set_header("Content-Type", "application/json")
    request.set_header("Content-Length", str(len(content)))
    request.write(content)

#
# QgsApi
#

ROOTPATH = "/lizmap"


class LizmapApi(QgsServerApi):
    __instances: list[QgsServerApi] = []  #  noqa RUF012

    def __init__(self, iface: QgsServerInterface):
        super().__init__(iface)
        self.__instances.append(self)

    def name(self) -> str:
        return "Lizmap"

    def description(self) -> str:
        return "Lizmap api endpoint"

    def version(self) -> str:
        from ..tools import version

        return version()

    def rootPath(self) -> str:
        return ROOTPATH

    def accept(self, url: QUrl) -> bool:
        """Override the api to actually match the rootpath"""
        path = url.path()
        return path.startswith(ROOTPATH)

    def executeRequest(self, context: QgsServerApiContext):
        """Execute the request"""
        # Take care that QGIS is header case sensitive
        req = HTTPRequestDelegate(context)
        try:
            route, values = routes.find_route(req.method, req.path.removeprefix(ROOTPATH))
            if req._finished:
                return

            req.set_status(200)

            route.fn(req, **values)

            if not req._finished:
                req.finish()
        except Exception as e:
            if req._finished:
                # Nothing to send, but log for debugging purpose
                logger.error(traceback.format_exc())
                return
            if isinstance(e, HTTPError):
                req.send_error(e.status_code, exc_info=sys.exc_info())
            else:
                logger.error(traceback.format_exc())
                req.send_error(500, reason="Internal error", exc_info=sys.exc_info())
