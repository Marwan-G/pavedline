"""The minimum supported app version: every response carries `X-Min-App-Version` (spec 11.4)."""

import httpx
import pytest
from pydantic import ValidationError

from app.main import create_app
from app.settings import Settings
from tests import probes
from tests.conftest import Database, client_for, make_settings

HEADER = "X-Min-App-Version"


async def test_default_is_0_0_0_on_a_success_response(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.headers[HEADER] == "0.0.0"


async def test_value_comes_from_the_setting(database: Database) -> None:
    app = create_app(make_settings(database, min_app_version="2.3.4"))
    try:
        async with client_for(app) as c:
            assert (await c.get("/healthz")).headers[HEADER] == "2.3.4"
    finally:
        await app.state.engine.dispose()


async def test_present_on_errors_too(database: Database) -> None:
    app = create_app(make_settings(database, min_app_version="1.0.0", max_body_bytes=10))
    try:
        async with client_for(app) as c:
            unauthorised = await c.get("/v1/items")
            missing = await c.get("/no-such-path")
            too_large = await c.post("/v1/items", content=b"x" * 100)
        assert unauthorised.status_code in (401, 404)
        assert missing.status_code == 404
        assert too_large.status_code == 413
        for r in (unauthorised, missing, too_large):
            assert r.headers[HEADER] == "1.0.0"
    finally:
        await app.state.engine.dispose()


async def test_present_on_an_unhandled_500(database: Database) -> None:
    app = create_app(make_settings(database, min_app_version="1.4.0"), extra_v1_routers=[probes.router])
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/_boom")
        assert r.status_code == 500
        assert r.headers[HEADER] == "1.4.0"
    finally:
        await app.state.engine.dispose()


def test_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app_runtime:pw@db:5432/app")
    monkeypatch.setenv("MIN_APP_VERSION", "3.1.4")
    assert Settings().min_app_version == "3.1.4"  # pyright: ignore[reportCallIssue]


BAD = ["", "1", "1.2", "v1.2.3", "1.2.3-beta", "1.2.x", "1.2.3\n", "1.2.3\r\nX-Evil: 1", "01.2.3"]


@pytest.mark.parametrize("bad", BAD)
def test_must_be_plain_semver(bad: str) -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", database_url="postgresql://a:b@h/d", min_app_version=bad)
