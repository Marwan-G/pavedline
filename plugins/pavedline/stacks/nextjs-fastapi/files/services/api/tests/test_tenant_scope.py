"""The tenant setting must never outlive its transaction, even when one pooled connection is reused."""

from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.db.tenant import tenant_transaction
from app.settings import async_database_url
from tests.conftest import World


@pytest.fixture
async def one_connection_engine(world: World) -> AsyncIterator[AsyncEngine]:
    """A pool of exactly one connection: every use is the same session, as behind a pooler."""
    engine = create_async_engine(
        async_database_url(world.db.runtime_url),
        pool_size=1,
        max_overflow=0,
        connect_args={"prepare_threshold": None},
    )
    yield engine
    await engine.dispose()


async def pid_and_setting(engine: AsyncEngine) -> tuple[int, str | None, int]:
    async with engine.connect() as conn:
        pid = (await conn.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        setting = (await conn.execute(text("SELECT current_setting('app.tenant_id', true)"))).scalar()
        rows = (await conn.execute(text("SELECT count(*) FROM idempotency_keys"))).scalar_one()
    return int(pid), setting, int(rows)


def seed_rows(world: World) -> None:
    with psycopg.connect(world.db.owner_url) as conn:
        for tenant in (world.tenant_a, world.tenant_b):
            conn.execute(
                "INSERT INTO idempotency_keys (tenant_id, principal, key, request_fingerprint, "
                "response_status, response_body) VALUES (%s, 'p', 'k', 'f', 200, '{}')",
                (tenant,),
            )
        conn.commit()


async def test_setting_does_not_survive_a_committed_transaction(
    one_connection_engine: AsyncEngine, world: World
) -> None:
    seed_rows(world)
    async with tenant_transaction(one_connection_engine, world.tenant_a) as conn:
        assert (await conn.execute(text("SELECT count(*) FROM idempotency_keys"))).scalar_one() >= 1
    pid, setting, rows = await pid_and_setting(one_connection_engine)
    assert setting in (None, "")
    assert rows == 0  # fail closed: no tenant, no rows
    pid2, _, _ = await pid_and_setting(one_connection_engine)
    assert pid == pid2  # it really was the same connection


async def test_setting_does_not_survive_a_failed_transaction(
    one_connection_engine: AsyncEngine, world: World
) -> None:
    seed_rows(world)

    async def fail() -> Any:
        async with tenant_transaction(one_connection_engine, world.tenant_b) as conn:
            await conn.execute(text("SELECT 1"))
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await fail()
    _, setting, rows = await pid_and_setting(one_connection_engine)
    assert setting in (None, "")
    assert rows == 0
