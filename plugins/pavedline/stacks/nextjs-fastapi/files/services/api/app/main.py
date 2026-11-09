"""The application factory. `app.main:app` is created lazily so importing this module has no side effects."""

import json
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth import JwksClient, TokenVerifier
from app.db.engine import make_engine
from app.errors import (
    MIN_APP_VERSION_HEADER,
    REQUEST_ID_HEADER,
    clean_request_id,
    envelope_body,
    install_error_handlers,
)
from app.routes import health
from app.routes.v1 import build_router
from app.settings import Settings

API_TITLE = "API"
API_VERSION = "0.0.0"


class RequestIdMiddleware:
    """Gives every request an id (the caller's X-Request-ID when plain, else a new one)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        wanted = next(
            (v.decode("latin-1") for k, v in scope["headers"] if k.lower() == b"x-request-id"), None
        )
        request_id = clean_request_id(wanted)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_id)


class MinAppVersionMiddleware:
    """Adds `X-Min-App-Version` to every HTTP response, errors and refusals included."""

    def __init__(self, app: ASGIApp, version: str) -> None:
        self.app = app
        self.header = (MIN_APP_VERSION_HEADER.lower().encode(), version.encode())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_version(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), self.header]
            await send(message)

        await self.app(scope, receive, send_with_version)


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Refuses a request body over `limit` bytes with 413, before parsing and before authentication.

    A Content-Length over the limit is refused at once; a body without one (chunked) is counted as it
    streams, so the limit holds either way.
    """

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = next((v for k, v in scope["headers"] if k.lower() == b"content-length"), None)
        if declared is not None and declared.isdigit() and int(declared) > self.limit:
            await self.refuse(scope, send)
            return
        seen = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    raise BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except BodyTooLarge:
            if started:
                raise
            await self.refuse(scope, send)

    async def refuse(self, scope: Scope, send: Send) -> None:
        request_id = scope.get("state", {}).get("request_id") or clean_request_id(None)
        body = json.dumps(
            envelope_body(request_id, "payload_too_large", "The request body is too large")
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"connection", b"close"),
        ]
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def create_app(
    settings: Settings | None = None,
    *,
    jwks_client: JwksClient | None = None,
    extra_v1_routers: Sequence[APIRouter] = (),
) -> FastAPI:
    """Build the app. `jwks_client` and `extra_v1_routers` are seams for tests."""
    settings = settings or Settings()  # pyright: ignore[reportCallIssue]
    logging.basicConfig(level=settings.log_level.upper())
    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await engine.dispose()

    production = settings.app_env == "production"
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.verifier = TokenVerifier(settings, jwks_client)
    app.add_middleware(BodyLimitMiddleware, limit=settings.max_body_bytes)
    app.add_middleware(MinAppVersionMiddleware, version=settings.min_app_version)
    app.add_middleware(RequestIdMiddleware)  # added last = outermost: the id exists before anything else
    install_error_handlers(app)
    app.include_router(health.router)
    v1_router = build_router()
    for extra in extra_v1_routers:
        v1_router.include_router(extra)
    app.include_router(v1_router)
    return app


def __getattr__(name: str) -> Any:
    if name == "app":
        return create_app()
    raise AttributeError(name)
