"""The example slice: /v1/items over HTTP, as a real client would call it."""

import asyncio
from typing import Any

import httpx
import psycopg

from tests.conftest import World, client_for

BODY = {"name": "Widget", "price_minor": 1250, "currency": "EUR"}


def key(value: str) -> dict[str, str]:
    return {"Idempotency-Key": value}


def count_items(world: World, tenant: Any) -> int:
    with psycopg.connect(world.db.owner_url) as conn:
        row = conn.execute("SELECT count(*) FROM items WHERE tenant_id = %s", (tenant,)).fetchone()
    assert row is not None
    return int(row[0])


async def test_create_get_list(client: httpx.AsyncClient, world: World) -> None:
    r = await client.post("/v1/items", json=BODY, headers={**world.headers(), **key("create-1")})
    assert r.status_code == 201, r.text
    item = r.json()["data"]
    assert item["name"] == "Widget" and item["price_minor"] == 1250 and item["currency"] == "EUR"
    assert isinstance(item["price_minor"], int)

    got = await client.get(f"/v1/items/{item['id']}", headers=world.headers())
    assert got.status_code == 200 and got.json()["data"] == item

    listing = await client.get("/v1/items", headers=world.headers())
    assert listing.status_code == 200
    assert item["id"] in [i["id"] for i in listing.json()["data"]]


async def test_replay_with_the_same_key_returns_the_original(client: httpx.AsyncClient, world: World) -> None:
    before = count_items(world, world.tenant_a)
    first = await client.post("/v1/items", json=BODY, headers={**world.headers(), **key("replay-1")})
    again = await client.post("/v1/items", json=BODY, headers={**world.headers(), **key("replay-1")})
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    assert count_items(world, world.tenant_a) == before + 1


async def test_replay_with_a_different_body_is_422(client: httpx.AsyncClient, world: World) -> None:
    first = await client.post("/v1/items", json=BODY, headers={**world.headers(), **key("reuse-1")})
    assert first.status_code == 201
    other = {**BODY, "name": "Different"}
    again = await client.post("/v1/items", json=other, headers={**world.headers(), **key("reuse-1")})
    assert again.status_code == 422
    err = again.json()["error"]
    assert err["code"] == "idempotency_key_reuse" and err["request_id"]
    assert "Widget" not in again.text  # never the cached body


async def test_missing_idempotency_key_is_400(client: httpx.AsyncClient, world: World) -> None:
    r = await client.post("/v1/items", json=BODY, headers=world.headers())
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "idempotency_key_required"


async def test_no_token_is_401_before_anything_else(client: httpx.AsyncClient) -> None:
    for r in (
        await client.get("/v1/items"),
        await client.get("/v1/items/00000000-0000-0000-0000-000000000000"),
        await client.post("/v1/items", json={"bad": True}),
    ):
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


async def test_validation_errors_are_422_envelopes(client: httpx.AsyncClient, world: World) -> None:
    for bad in (
        {"name": "", "price_minor": 1, "currency": "EUR"},
        {"name": "x", "price_minor": -1, "currency": "EUR"},
        {"name": "x", "price_minor": 1.5, "currency": "EUR"},  # never float money
        {"name": "x", "price_minor": 1, "currency": "eur"},
    ):
        r = await client.post("/v1/items", json=bad, headers={**world.headers(), **key("bad")})
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "validation_error"
    r = await client.get("/v1/items/not-a-uuid", headers=world.headers())
    assert r.status_code == 422


async def test_another_tenants_item_is_404(client: httpx.AsyncClient, world: World) -> None:
    r = await client.get(f"/v1/items/{world.ids_b['item_id']}", headers=world.headers("a"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    mine = await client.get(f"/v1/items/{world.ids_a['item_id']}", headers=world.headers("a"))
    assert mine.status_code == 200


async def test_pagination_is_stable_and_complete(client: httpx.AsyncClient, world: World) -> None:
    for i in range(5):
        r = await client.post(
            "/v1/items", json={**BODY, "name": f"p{i}"}, headers={**world.headers(), **key(f"page-{i}")}
        )
        assert r.status_code == 201
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = (await client.get("/v1/items", params=params, headers=world.headers())).json()
        assert len(page["data"]) <= 2
        seen += [i["id"] for i in page["data"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == count_items(world, world.tenant_a)
    assert seen == sorted(seen)
    assert world.ids_b["item_id"] not in [str(s) for s in seen]


async def test_bad_cursor_and_limit_are_422(client: httpx.AsyncClient, world: World) -> None:
    assert (
        await client.get("/v1/items", params={"cursor": "!!"}, headers=world.headers())
    ).status_code == 422
    assert (await client.get("/v1/items", params={"limit": 0}, headers=world.headers())).status_code == 422
    assert (await client.get("/v1/items", params={"limit": 101}, headers=world.headers())).status_code == 422


async def test_concurrent_creates_with_one_key_make_one_item(app_factory: Any, world: World) -> None:
    app = app_factory()
    before = count_items(world, world.tenant_a)

    async def post() -> httpx.Response:
        async with client_for(app) as c:
            return await c.post("/v1/items", json=BODY, headers={**world.headers(), **key("race-1")})

    results = await asyncio.gather(*[post() for _ in range(4)])
    assert {r.status_code for r in results} == {201}
    assert all(r.json() == results[0].json() for r in results)
    assert count_items(world, world.tenant_a) == before + 1


async def test_out_of_range_and_nul_inputs_are_422_not_500(client: httpx.AsyncClient, world: World) -> None:
    for bad in (
        {"name": "x", "price_minor": 2**70, "currency": "EUR"},
        {"name": "x", "price_minor": 2**63, "currency": "EUR"},
        {"name": "bad\u0000name", "price_minor": 1, "currency": "EUR"},
    ):
        r = await client.post("/v1/items", json=bad, headers={**world.headers(), **key("range")})
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "validation_error"
    ok = await client.post(
        "/v1/items",
        json={"name": "max", "price_minor": 2**63 - 1, "currency": "EUR"},
        headers={**world.headers(), **key("range-ok")},
    )
    assert ok.status_code == 201
    assert ok.json()["data"]["price_minor"] == 2**63 - 1


async def test_a_stored_body_that_no_longer_fits_the_model_is_not_returned_raw(
    client: httpx.AsyncClient, world: World
) -> None:
    """The reply always passes through the response model: a corrupt stored response fails, it is
    never passed through unchecked."""
    first = await client.post("/v1/items", json=BODY, headers={**world.headers(), **key("model-1")})
    assert first.status_code == 201
    with psycopg.connect(world.db.owner_url) as conn:
        conn.execute(
            'UPDATE idempotency_keys SET response_body = \'{"data": {"extra": 1}}\'::jsonb '
            "WHERE key = 'model-1'"
        )
        conn.commit()
    transport = httpx.ASGITransport(app=client._transport.app, raise_app_exceptions=False)  # type: ignore[attr-defined]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        again = await c.post("/v1/items", json=BODY, headers={**world.headers(), **key("model-1")})
    assert again.status_code == 500
    assert "extra" not in again.text
