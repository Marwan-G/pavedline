"""One error envelope for every failure: {"error": {"code", "message", "request_id", "details"?}}."""

import logging
import re
import uuid
from typing import Any

import psycopg
import sqlalchemy.exc
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.events import log_event

log = logging.getLogger("app.errors")

REQUEST_ID_HEADER = "X-Request-ID"
MIN_APP_VERSION_HEADER = "X-Min-App-Version"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")

_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


class ApiError(Exception):
    """Raise anywhere below a route; the handler turns it into the envelope."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}


def new_request_id() -> str:
    return uuid.uuid4().hex


def clean_request_id(value: str | None) -> str:
    """A caller-supplied id is kept only when it is short and plain; anything else is replaced."""
    if value and _SAFE_REQUEST_ID.match(value):
        return value
    return new_request_id()


def request_id_of(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) else new_request_id()


def envelope_body(request_id: str, code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def envelope(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "request_id": request_id_of(request)}
    if details is not None:
        error["details"] = details
    return {"error": error}


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    *,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(envelope(request, code, message, details), status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return error_response(
            request, exc.status, exc.code, exc.message, details=exc.details, headers=exc.headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        code = _CODES.get(exc.status_code, "error")
        message = exc.detail or code.replace("_", " ")
        return error_response(request, exc.status_code, code, message, headers=dict(exc.headers or {}))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        details = [
            {"loc": [str(part) for part in e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return error_response(request, 422, "validation_error", "Request validation failed", details=details)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        log_event(log, logging.ERROR, "request.unhandled_error", "unhandled error", exc_info=exc)
        # This response is built by the server-error layer, outside the user middleware, so it sets the
        # request id and the minimum app version headers itself.
        return error_response(
            request,
            500,
            "internal_error",
            "Internal server error",
            headers={
                REQUEST_ID_HEADER: request_id_of(request),
                MIN_APP_VERSION_HEADER: request.app.state.settings.min_app_version,
            },
        )

    async def data_error(request: Request, exc: Exception) -> JSONResponse:
        # The database refused a value (bad cast, out of range, NUL byte): the client's input, not our bug.
        log_event(log, logging.WARNING, "db.data_error", "database data error", error_type=type(exc).__name__)
        return error_response(request, 422, "invalid_value", "A value in the request is not acceptable")

    app.add_exception_handler(sqlalchemy.exc.DataError, data_error)
    app.add_exception_handler(psycopg.errors.DataError, data_error)
