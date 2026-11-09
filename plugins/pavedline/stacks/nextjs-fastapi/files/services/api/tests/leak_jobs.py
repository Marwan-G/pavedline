"""Job types the platform ships (part of the pack; products add theirs in leak_registry.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import create_async_engine

from app.services.idempotency import purge_expired_idempotency_keys
from app.services.webhook_events import purge_expired_webhook_events
from app.settings import async_database_url
from tests.leak_support import JobCase

if TYPE_CHECKING:
    from tests.conftest import World


async def purge_job(world: World) -> None:
    """Cross-tenant job: it enumerates tenants and runs one SET LOCAL transaction per tenant. It takes no
    ids, so the leak case is that running it changes none of tenant B's live (unexpired) rows."""
    engine = create_async_engine(
        async_database_url(world.db.runtime_url), connect_args={"prepare_threshold": None}
    )
    try:
        await purge_expired_idempotency_keys(engine)
    finally:
        await engine.dispose()


async def purge_webhook_events_job(world: World) -> None:
    """Global-table job (webhook_events holds ids only, no tenant data): it is not tenant-scoped, so the leak
    case is only that it runs as the runtime role and touches no tenant table."""
    from tests.conftest import make_settings  # conftest imports this module

    engine = create_async_engine(
        async_database_url(world.db.runtime_url), connect_args={"prepare_threshold": None}
    )
    try:
        await purge_expired_webhook_events(engine, settings=make_settings(world.db))
    finally:
        await engine.dispose()


# Every job type, run as tenant A with tenant B's ids. A scheduled job MUST call
# purge_expired_idempotency_keys (the table grows otherwise); add each new job type here.
JOBS: list[JobCase] = [
    JobCase("purge_expired_idempotency_keys", purge_job),
    JobCase("purge_expired_webhook_events", purge_webhook_events_job),
]


PLATFORM_JOBS: list[JobCase] = [*JOBS]
