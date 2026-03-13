"""HTTP errors as exception"""

from typing import Optional


class HTTPError(Exception):
    """An exception that will turn into an HTTP error response."""

    def __init__(
        self,
        status_code: int = 500,
        reason: Optional[str] = None,
        log_message: Optional[str] = None,
        *args,
    ):
        self.status_code = status_code
        self.log_message = log_message
        self.reason = reason
        self.args = args

    def __str__(self) -> str:
        message = f"HTTP {self.status_code}: {self.reason}"
        if self.log_message:
            message = f"{message} ({self.log_message})"
        return message


class HTTPMethodNotAllowed(HTTPError):
    def __init__(self):
        super().__init__(405, reason="Method not allowed")


class HTTPBadRequest(HTTPError):
    def __init__(self):
        super().__init__(400, reason="Bad request")


class HTTPNotFound(HTTPError):
    def __init__(self):
        super().__init__(404, reason="Not found")
