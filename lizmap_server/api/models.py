from typing_extensions import (
    Self,
)

from .schemas.models import (
    Field,
    JsonModel,
    Nullable,
    Option,
)

from .request import HTTPRequestDelegate


def _href(request: HTTPRequestDelegate, path: str) -> str:
    return request.public_url(f"{path}")


class Link(JsonModel):
    href: str
    rel: str
    mime_type: Nullable[str] = Field(serialization_alias="type")
    title: str = ""
    description: Option[str]
    length: Option[int] = None
    templated: bool = False
    hreflang: Option[str] = None

    @classmethod
    def makelink(
        cls,
        request: HTTPRequestDelegate,
        rel: str,
        path: str,
        mime_type: str = "application/json",
        title: str = "",
        description: Option[str] = None,
    ) -> Self:
        return cls(
            href=_href(request, path),
            rel=rel,
            mime_type=mime_type,
            title=title,
            description=description,
        )
