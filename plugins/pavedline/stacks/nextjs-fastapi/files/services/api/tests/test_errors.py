from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from tests import probes
from tests.conftest import client_for


def assert_envelope(body: dict[str, Any], code: str) -> None:
    assert set(body) == {"error"}
    err = body["error"]
    assert err["code"] == code
    assert isinstance(err["message"], str) and err["message"]
    assert isinstance(err["request_id"], str) and err["request_id"]


async def test_unknown_route_is_a_404_envelope(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/nothing-here")
    assert r.status_code == 404
    assert_envelope(r.json(), "not_found")


async def test_wrong_method_is_a_405_envelope(client: httpx.AsyncClient) -> None:
    r = await client.post("/healthz")
    assert r.status_code == 405
    assert_envelope(r.json(), "method_not_allowed")


async def test_request_id_is_echoed_or_generated(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/nothing-here", headers={"X-Request-ID": "req-123"})
    assert r.json()["error"]["request_id"] == "req-123"
    assert r.headers["x-request-id"] == "req-123"
    r2 = await client.get("/v1/nothing-here")
    assert r2.headers["x-request-id"] == r2.json()["error"]["request_id"]


@pytest.mark.parametrize("bad", ["x" * 200, "has space", "bad\x00id"])
async def test_a_hostile_request_id_is_replaced(client: httpx.AsyncClient, bad: str) -> None:
    try:
        r = await client.get("/v1/nothing-here", headers={"X-Request-ID": bad})
    except httpx.InvalidURL:
        return
    assert r.json()["error"]["request_id"] != bad


async def test_unhandled_error_is_a_500_envelope_without_details(app_factory: Any) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/v1/_boom")
    assert r.status_code == 500
    assert_envelope(r.json(), "internal_error")
    assert "secret internal detail" not in r.text


async def test_client_for_helper_is_usable(app_factory: Any) -> None:
    async with client_for(app_factory()) as c:
        assert (await c.get("/healthz")).status_code == 200


async def test_500_carries_the_request_id_header(app_factory: Any) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/v1/_boom", headers={"X-Request-ID": "req-500"})
    assert r.status_code == 500
    assert r.headers["x-request-id"] == "req-500"
    assert r.json()["error"]["request_id"] == "req-500"


async def test_database_data_errors_are_422_not_500(app_factory: Any, world: Any) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/v1/_dataerror", headers=world.headers())
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_value"
    assert "not a number" not in r.text


async def test_oversized_body_is_413_before_auth(app_factory: Any) -> None:
    app = app_factory(extra_v1_routers=[probes.router], max_body_bytes=100)
    async with client_for(app) as c:
        r = await c.post("/v1/_echo", content=b"x" * 101)  # no token: 413 comes first
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"
    assert r.json()["error"]["request_id"]


async def test_streamed_body_over_the_limit_is_413(app_factory: Any) -> None:
    app = app_factory(extra_v1_routers=[probes.router], max_body_bytes=100)

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(10):
            yield b"x" * 30  # no Content-Length header: counted while streaming

    async with client_for(app) as c:
        r = await c.post("/v1/_echo", content=chunks())
    assert r.status_code == 413


async def test_body_at_the_limit_is_accepted(app_factory: Any) -> None:
    app = app_factory(extra_v1_routers=[probes.router], max_body_bytes=100)
    async with client_for(app) as c:
        r = await c.post("/v1/_echo", content=b"x" * 100)
    assert r.status_code == 200
    assert r.json() == {"bytes": 100}
