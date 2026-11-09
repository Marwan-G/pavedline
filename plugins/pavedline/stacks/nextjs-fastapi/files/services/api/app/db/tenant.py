"""Tenant scoping. Every request and every job runs in ONE transaction that starts with SET LOCAL.

`set_config('app.tenant_id', <id>, true)` is SET LOCAL: it lasts to the end of the transaction, so a
pooled connection never carries a tenant to the next client. Never use a session-level SET and never a
session advisory lock: the pooler runs in transaction mode.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@asynccontextmanager
async def tenant_transaction(engine: AsyncEngine, tenant_id: UUID) -> AsyncGenerator[AsyncConnection]:
    """One transaction scoped to `tenant_id`; commits on success, rolls back on any exception."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        yield conn


async def resolve_tenant(engine: AsyncEngine, external_id: str) -> UUID | None:
    """Map the identity provider's organisation id (from the verified token) to our tenant id.

    `tenants` is a global table the runtime role may read; this is the only query that runs before
    the tenant is set.
    """
    async with engine.connect() as conn, conn.begin():
        row = (
            await conn.execute(
                text("SELECT id FROM tenants WHERE external_id = :external_id"),
                {"external_id": external_id},
            )
        ).first()
    return None if row is None else UUID(str(row[0]))


async def list_tenant_ids(engine: AsyncEngine) -> list[UUID]:
    """For a cross-tenant job: enumerate tenants from the global table, then run ONE
    `tenant_transaction` per tenant. Never give the runtime role BYPASSRLS to avoid this."""
    async with engine.connect() as conn, conn.begin():
        rows = (await conn.execute(text("SELECT id FROM tenants ORDER BY created_at, id"))).all()
    return [UUID(str(r[0])) for r in rows]
