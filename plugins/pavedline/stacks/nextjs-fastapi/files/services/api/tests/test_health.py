import httpx

from app.main import create_app
from app.settings import Settings
from tests.conftest import Database, client_for


async def test_healthz_is_unauthenticated(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"data": {"status": "ok"}}


async def test_readyz_checks_the_database(client: httpx.AsyncClient) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"data": {"status": "ready"}}


async def test_readyz_is_503_when_the_database_is_down(database: Database) -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql://app_runtime:x@127.0.0.1:1/none?connect_timeout=1",
    )
    app = create_app(settings)
    try:
        async with client_for(app) as c:
            r = await c.get("/readyz")
            assert r.status_code == 503
            body = r.json()
            assert body["error"]["code"] == "not_ready"
            assert "127.0.0.1" not in r.text  # no connection details leak
            assert (await c.get("/healthz")).status_code == 200  # liveness does not touch the database
    finally:
        await app.state.engine.dispose()


async def test_docs_are_off_in_production() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql://app_runtime:x@127.0.0.1:1/none",
        auth_issuer="https://issuer.test",
        auth_audience="acme-api",
        auth_jwks_url="https://issuer.test/jwks.json",
    )
    app = create_app(settings)
    try:
        async with client_for(app) as c:
            assert (await c.get("/openapi.json")).status_code == 404
    finally:
        await app.state.engine.dispose()
