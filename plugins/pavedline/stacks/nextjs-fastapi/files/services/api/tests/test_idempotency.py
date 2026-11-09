import asyncio
import uuid
from typing import Any

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.db.tenant import tenant_transaction
from app.errors import ApiError
from app.services.idempotency import (
    StoredResponse,
    fingerprint,
    purge_expired_idempotency_keys,
    run_idempotent,
)
from app.settings import async_database_url
from tests.conftest import Database, World


@pytest.fixture
async def engine(database: Database) -> Any:
    eng: AsyncEngine = create_async_engine(
        async_database_url(database.runtime_url), connect_args={"prepare_threshold": None}
    )
    yield eng
    await eng.dispose()


def fp(body: bytes = b"{}") -> str:
    return fingerprint("POST", "/v1/things", body)


async def call(
    engine: AsyncEngine, tenant: uuid.UUID, key: str, fingerprint_: str, counter: list[int]
) -> StoredResponse:
    async def handler() -> StoredResponse:
        counter.append(1)
        await asyncio.sleep(0.05)
        return StoredResponse(201, {"data": {"n": len(counter)}})

    async with tenant_transaction(engine, tenant) as conn:
        return await run_idempotent(
            conn,
            tenant_id=tenant,
            principal="user_a",
            key=key,
            fingerprint=fingerprint_,
            handler=handler,
        )


def test_fingerprint_depends_on_method_path_and_body() -> None:
    base = fingerprint("POST", "/v1/a", b"{}")
    assert base == fingerprint("POST", "/v1/a", b"{}")
    assert base != fingerprint("PUT", "/v1/a", b"{}")
    assert base != fingerprint("POST", "/v1/b", b"{}")
    assert base != fingerprint("POST", "/v1/a", b'{"x":1}')


async def test_replay_returns_the_stored_response_and_runs_once(engine: Any, world: World) -> None:
    counter: list[int] = []
    first = await call(engine, world.tenant_a, "k1", fp(), counter)
    again = await call(engine, world.tenant_a, "k1", fp(), counter)
    assert first == again
    assert counter == [1]


async def test_same_key_other_fingerprint_is_422(engine: Any, world: World) -> None:
    counter: list[int] = []
    await call(engine, world.tenant_a, "k2", fp(b"{}"), counter)
    with pytest.raises(ApiError) as err:
        await call(engine, world.tenant_a, "k2", fp(b'{"changed":true}'), counter)
    assert err.value.status == 422
    assert err.value.code == "idempotency_key_reuse"
    assert counter == [1]  # the second handler never ran


async def test_a_failed_handler_leaves_no_key(engine: Any, world: World) -> None:
    async def boom() -> StoredResponse:
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        async with tenant_transaction(engine, world.tenant_a) as conn:
            await run_idempotent(
                conn,
                tenant_id=world.tenant_a,
                principal="user_a",
                key="k3",
                fingerprint=fp(),
                handler=boom,
            )
    counter: list[int] = []
    await call(engine, world.tenant_a, "k3", fp(), counter)
    assert counter == [1]


async def test_concurrent_requests_with_one_key_run_the_handler_once(engine: Any, world: World) -> None:
    counter: list[int] = []
    results = await asyncio.gather(*[call(engine, world.tenant_a, "k4", fp(), counter) for _ in range(4)])
    assert counter == [1]
    assert all(r == results[0] for r in results)


async def test_keys_are_scoped_to_tenant_and_principal(engine: Any, world: World) -> None:
    counter: list[int] = []
    await call(engine, world.tenant_a, "same", fp(), counter)
    await call(engine, world.tenant_b, "same", fp(), counter)  # another tenant: its own key space
    assert counter == [1, 1]

    async def handler() -> StoredResponse:
        counter.append(1)
        return StoredResponse(200, {"data": {}})

    async with tenant_transaction(engine, world.tenant_a) as conn:  # another principal
        await run_idempotent(
            conn,
            tenant_id=world.tenant_a,
            principal="user_other",
            key="same",
            fingerprint=fp(),
            handler=handler,
        )
    assert counter == [1, 1, 1]


async def test_expired_keys_are_forgotten(engine: Any, world: World) -> None:
    counter: list[int] = []
    await call(engine, world.tenant_a, "old", fp(), counter)
    with psycopg.connect(world.db.owner_url) as conn:
        conn.execute("UPDATE idempotency_keys SET created_at = now() - interval '25 hours' WHERE key = 'old'")
        conn.commit()
    await call(engine, world.tenant_a, "old", fp(), counter)
    assert counter == [1, 1]


async def test_purge_removes_only_expired_keys_of_every_tenant(engine: Any, world: World) -> None:
    with psycopg.connect(world.db.owner_url) as conn:
        for tenant in (world.tenant_a, world.tenant_b):
            for name, age in (("stale", "25 hours"), ("fresh", "1 hour")):
                conn.execute(
                    "INSERT INTO idempotency_keys (tenant_id, principal, key, request_fingerprint, "
                    "response_status, response_body, created_at) "
                    "VALUES (%s, 'p', %s, 'f', 200, '{}', now() - %s::interval)",
                    (tenant, name, age),
                )
        conn.commit()
    removed = await purge_expired_idempotency_keys(engine)
    assert removed >= 2
    with psycopg.connect(world.db.owner_url) as conn:
        keys = {
            r[0]
            for r in conn.execute(
                "SELECT key FROM idempotency_keys WHERE tenant_id IN (%s, %s) AND key IN ('stale', 'fresh')",
                (world.tenant_a, world.tenant_b),
            ).fetchall()
        }
    assert keys == {"fresh"}
