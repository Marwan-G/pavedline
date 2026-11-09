import time
from typing import Any

import httpx
import pytest

from app.main import create_app
from tests import probes
from tests.conftest import World, client_for, make_settings
from tests.tokens import TokenFactory


@pytest.fixture
async def probe_client(app_factory: Any) -> Any:
    from tests.conftest import client_for

    app = app_factory(extra_v1_routers=[probes.router])
    async with client_for(app) as c:
        yield c


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def assert_401(r: httpx.Response) -> None:
    assert r.status_code == 401, r.text
    body = r.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["request_id"]
    assert r.headers["www-authenticate"] == "Bearer"
    assert "Traceback" not in r.text


async def test_no_token_is_401(probe_client: httpx.AsyncClient) -> None:
    await assert_401(await probe_client.get("/v1/_probe"))


async def test_garbage_token_is_401(probe_client: httpx.AsyncClient) -> None:
    await assert_401(await probe_client.get("/v1/_probe", headers=bearer("not.a.jwt")))


async def test_wrong_scheme_is_401(probe_client: httpx.AsyncClient, world: World) -> None:
    r = await probe_client.get("/v1/_probe", headers={"Authorization": f"Basic {world.token_a}"})
    await assert_401(r)


async def test_token_signed_by_another_key_is_401(
    probe_client: httpx.AsyncClient, tokens: TokenFactory, world: World
) -> None:
    token = tokens.token(tenant=world.ext_a, key=tokens.other_key)
    await assert_401(await probe_client.get("/v1/_probe", headers=bearer(token)))


async def test_expired_token_is_401(
    probe_client: httpx.AsyncClient, tokens: TokenFactory, world: World
) -> None:
    token = tokens.token(tenant=world.ext_a, expires_in=-3600)
    await assert_401(await probe_client.get("/v1/_probe", headers=bearer(token)))


async def test_wrong_audience_and_issuer_are_401(
    probe_client: httpx.AsyncClient, tokens: TokenFactory, world: World
) -> None:
    for token in (
        tokens.token(tenant=world.ext_a, audience="someone-else"),
        tokens.token(tenant=world.ext_a, issuer="https://evil.test"),
    ):
        await assert_401(await probe_client.get("/v1/_probe", headers=bearer(token)))


async def test_none_algorithm_is_401(probe_client: httpx.AsyncClient, world: World) -> None:
    import base64
    import json

    def b64(obj: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    now = int(time.time())
    payload = {
        "iss": "https://issuer.test",
        "aud": "acme-api",
        "sub": "u",
        "exp": now + 300,
        "o": {"id": world.ext_a},
    }
    token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}."
    await assert_401(await probe_client.get("/v1/_probe", headers=bearer(token)))


async def test_hs256_token_with_the_public_key_as_secret_is_401(
    probe_client: httpx.AsyncClient, tokens: TokenFactory, world: World
) -> None:
    import jwt

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://issuer.test",
            "aud": "acme-api",
            "sub": "u",
            "exp": now + 300,
            "o": {"id": world.ext_a},
        },
        "a-shared-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
        headers={"kid": "test-key-1"},
    )
    await assert_401(await probe_client.get("/v1/_probe", headers=bearer(token)))


async def test_valid_rs256_and_es256_tokens_work(
    probe_client: httpx.AsyncClient, tokens: TokenFactory, world: World
) -> None:
    for algorithm in ("RS256", "ES256"):
        token = tokens.token(tenant=world.ext_a, subject="user_x", algorithm=algorithm)
        r = await probe_client.get("/v1/_probe", headers=bearer(token))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["subject"] == "user_x"
        assert data["tenant_id"] == str(world.tenant_a)
        assert data["db_setting"] == str(world.tenant_a)  # SET LOCAL happened in the transaction


async def test_tenant_comes_from_the_token_never_from_the_request(
    probe_client: httpx.AsyncClient, world: World
) -> None:
    r = await probe_client.get(
        "/v1/_probe",
        headers={**world.headers("a"), "X-Tenant-Id": str(world.tenant_b)},
        params={"tenant_id": str(world.tenant_b)},
    )
    assert r.json()["data"]["tenant_id"] == str(world.tenant_a)


async def test_token_without_a_tenant_is_403(probe_client: httpx.AsyncClient, tokens: TokenFactory) -> None:
    r = await probe_client.get("/v1/_probe", headers=bearer(tokens.token(tenant=None)))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_unknown_tenant_is_403(probe_client: httpx.AsyncClient, tokens: TokenFactory) -> None:
    r = await probe_client.get("/v1/_probe", headers=bearer(tokens.token(tenant="org_nobody")))
    assert r.status_code == 403


async def test_default_claim_is_the_clerk_v2_nested_organisation(tokens: TokenFactory, world: World) -> None:
    settings = make_settings(world.db)
    assert settings.auth_tenant_claim == "o.id"
    app = create_app(settings, jwks_client=tokens.jwks_client(), extra_v1_routers=[probes.router])
    try:
        async with client_for(app) as c:
            r = await c.get("/v1/_probe", headers=bearer(tokens.token(tenant=world.ext_a)))
            assert r.status_code == 200, r.text
            assert r.json()["data"]["tenant_id"] == str(world.tenant_a)
            # a v1 style flat claim is not read unless configured
            flat = tokens.token(tenant=None, extra={"org_id": world.ext_a})
            assert (await c.get("/v1/_probe", headers=bearer(flat))).status_code == 403
    finally:
        await app.state.engine.dispose()


async def test_flat_claim_is_supported_by_configuration(tokens: TokenFactory, world: World) -> None:
    app = create_app(
        make_settings(world.db, auth_tenant_claim="org_id"),
        jwks_client=tokens.jwks_client(),
        extra_v1_routers=[probes.router],
    )
    try:
        async with client_for(app) as c:
            token = tokens.token(tenant=world.ext_a, claim="org_id")
            r = await c.get("/v1/_probe", headers=bearer(token))
            assert r.status_code == 200, r.text
    finally:
        await app.state.engine.dispose()


async def test_unknown_key_ids_do_not_hammer_the_jwks_endpoint(tokens: TokenFactory, world: World) -> None:
    jwks = tokens.counting_client()
    app = create_app(make_settings(world.db), jwks_client=jwks, extra_v1_routers=[probes.router])
    try:
        async with client_for(app) as c:
            for i in range(20):
                token = tokens.token(tenant=world.ext_a, kid=f"unknown-{i}")
                await assert_401(await c.get("/v1/_probe", headers=bearer(token)))
        assert jwks.fetches <= 2, jwks.fetches
    finally:
        await app.state.engine.dispose()


async def test_jwks_fetch_failure_is_503_not_401(tokens: TokenFactory, world: World) -> None:
    app = create_app(
        make_settings(world.db),
        jwks_client=tokens.counting_client(fail=True),
        extra_v1_routers=[probes.router],
    )
    try:
        async with client_for(app) as c:
            r = await c.get("/v1/_probe", headers=bearer(tokens.token(tenant=world.ext_a)))
            assert r.status_code == 503
            assert r.json()["error"]["code"] == "auth_unavailable"
    finally:
        await app.state.engine.dispose()


async def test_unconfigured_auth_rejects_everything(world: World, tokens: TokenFactory) -> None:
    from app.main import create_app
    from tests.conftest import client_for, make_settings

    app = create_app(
        make_settings(world.db, auth_issuer=None, auth_audience=None, auth_jwks_url=None),
        extra_v1_routers=[probes.router],
    )
    try:
        async with client_for(app) as c:
            await assert_401(await c.get("/v1/_probe", headers=bearer(world.token_a)))
    finally:
        await app.state.engine.dispose()
