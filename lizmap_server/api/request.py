from functools import cached_property
from typing import (
    Dict,
    List,
    Optional,
)
from urllib.parse import parse_qs

from qgis.server import (
    QgsServerApiContext,
    QgsServerInterface,
    QgsServerRequest,
)

from pydantic import TypeAdapter, JsonValue

from ..context import create_server_context

from .errors import HTTPError
from .schemas.models import JsonModel
from . import logger


class HTTPRequestDelegate:
    """Wrappper for request/response"""

    def __init__(self, context: QgsServerApiContext):
        self._context = context
        self._response = context.response()
        self._request = context.request()
        self._finished = False

    @cached_property
    def server_context(self):
        return create_server_context()

    @property
    def method(self) -> QgsServerRequest.Method:
        return self._request.method()

    @property
    def request(self) -> QgsServerRequest:
        return self._request

    @property
    def path(self) -> str:
        return self._request.url().path()

    @property
    def host(self) -> str:
        return self._request.url().host()

    @property
    def scheme(self) -> str:
        return self._request.url().scheme()

    @cached_property
    def query(self) -> Dict[str, str]:
        return {k: v[0] for k, v in parse_qs(self._request.url().query().removeprefix("?")).items()}

    @cached_property
    def query_all(self) -> Dict[str, List[str]]:
        return parse_qs(self._request.url().query().removeprefix("?"))

    @property
    def serverInterface(self) -> QgsServerInterface:
        return self._context.serverInterface()

    def parameter(self, key: str, default: Optional[str] = "") -> str:
        return self._request.parameter(key, default)

    def finish(self, chunk: Optional[str | bytes] = None) -> None:
        if self._finished:
            logger.warning("finish() called twice")
            return

        if chunk is not None:
            self.write(chunk)

        self._finished = True

    def write_json(self, data: JsonValue | JsonModel) -> None:
        self.set_header("Content-Type", "application/json")
        if isinstance(data, JsonModel):
            self._response.write(data.model_dump_json())
        else:
            self._response.write(TypeAdapter(JsonValue).dump_json(data))  # type: ignore [arg-type]

    def write(self, chunk: str | bytes) -> None:
        """ """
        if not isinstance(chunk, (bytes, str)):
            raise TypeError("write() only accepts bytes, unicode, or dict")
        self._response.write(chunk)

    def set_status(self, status_code: int, reason: Optional[str] = None) -> None:
        """ """
        self._response.setStatusCode(status_code)
        self._reason = reason or "Unknown"

    def send_error(self, status_code: int = 500, **kwargs) -> None:
        """ """
        self._response.clear()
        reason = kwargs.get("reason")
        if "exc_info" in kwargs:
            exception = kwargs["exc_info"][1]
            if isinstance(exception, HTTPError) and exception.reason:
                reason = exception.reason
                logger.error(str(exception))
        self.set_status(status_code, reason=reason)
        self.write_json({"code": status_code, "description": self._reason})
        if not self._finished:
            self.finish()
            self._response.finish()

    def set_header(self, name: str, value: str) -> None:
        """ """
        self._response.setHeader(name, value)

    def header(self, name: str) -> Optional[str]:
        if value := self._request.header(name):
            return value

        return None

    def public_url(self, path: str) -> str:
        """Return the public base url"""
        host = self.host
        protocol = self.scheme

        rootpath = self._context.matchedPath()

        # Check for X-Forwarded-Host header
        forwarded_host = self.header("X-Forwarded-Host")
        if forwarded_host:
            host = forwarded_host
        forwarded_proto = self.header("X-Forwarded-Proto")
        if forwarded_proto:
            protocol = forwarded_proto

        # Check for 'Forwarded headers
        forwarded = self.header("Forwarded")
        if forwarded:
            parts = forwarded.split(";")
            for p in parts:
                k, v = p.split("=")
                if k == "host":
                    host = v.strip(" ")
                elif k == "proto":
                    protocol = v.strip(" ")
        if host:
            return f"{protocol}://{host}{rootpath}{path}"
        return f"{rootpath}{path}"
