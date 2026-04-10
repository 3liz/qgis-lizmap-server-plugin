
from . import routes

from .models import Link
from .request import HTTPRequestDelegate

from .schemas import (
    JsonModel,
)

from . import swagger


def v1(path: str) -> str:
    return f"/api/v1/{path}"


#
# Landing page
#

@swagger.model
class LandingPage(JsonModel):
    name: str
    description: str
    links: list[Link]


@routes.get("/")
def landing_page(request: HTTPRequestDelegate, **match_info):
    """
    summary: "Landing page"
    description: >
        Landing page for Lizmap api
    tags:
        - api
    responses:
        "200":
            description: >
                Returns the Landing page data as JSon
            content:
                application/json:
                    schema:
                        $ref: '#/definitions/LandingPage'
    """
    request.write_json(
        LandingPage(
            name="Lizmap API",
            description="Provide informations about projects",
            links = [
                Link.makelink(
                    request,
                    rel="service-desc",
                    title="Api description",
                    path=v1(""),
                ),
                Link.makelink(
                    request,
                    rel="collection",
                    title="Available projects",
                    path=v1("projects/list/{Path}"),
                ),
                Link.makelink(
                    request,
                    rel="section",
                    title="Project's description",
                    path=v1("projects/description?p={Path}"),
                ),
                Link.makelink(
                    request,
                    rel="section",
                    title="Project's layer details",
                    path=v1("projects/layers/{Id}"),
                ),
                Link.makelink(
                    request,
                    rel="collection",
                    title="Project's layouts",
                    path=v1("projects/layouts/"),
                ),
                Link.makelink(
                    request,
                    rel="section",
                    title="Project's layout details",
                    path=v1("projects/layouts/{Name}"),
                ),
                Link.makelink(
                    request,
                    rel="self",
                    title="Landing page",
                    path="/",
                ),
            ]
        )
    )

