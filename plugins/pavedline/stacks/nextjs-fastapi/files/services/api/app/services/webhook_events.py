"""Replay protection: each verified (provider, event id) is accepted once.

`webhook_events` is a global table (no tenant is known before the payload is read and trusted); it holds only
the provider name and the event id. The claim is an INSERT ... ON CONFLICT DO NOTHING in the caller's
transaction: a handler that fails rolls the claim back, so the provider's retry is processed. Rows older
than the retention are purged by `purge_expired_webhook_events`, a scheduled job (see tests/leak_jobs.py).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.settings import Settings

DEFAULT_RETENTION_DAYS = 30
MAX_EVENT_ID_LENGTH = 255


async def claim_event(conn: AsyncConnection, provider: str, event_id: str) -> bool:
    """True when this event id is new (now claimed); False when it was already accepted."""
    row = (
        await conn.execute(
            text(
                "INSERT INTO webhook_events (provider, event_id) VALUES (:provider, :event_id) "
                "ON CONFLICT (provider, event_id) DO NOTHING RETURNING event_id"
            ),
            {"provider": provider, "event_id": event_id},
        )
    ).first()
    return row is not None


async def purge_expired_webhook_events(
    engine: AsyncEngine, settings: Settings | None = None, retention_days: int | None = None
) -> int:
    """Delete event ids older than the retention. The scheduled job passes its `settings`, so the retention is
    `settings.webhook_event_retention_days` (WEBHOOK_EVENT_RETENTION_DAYS, default 30); `retention_days`
    overrides it (tests) and with neither the default is 30. Keep it well above the timestamp tolerance, or an
    old signed request could be replayed once its id is forgotten. The product MUST schedule this job, or the
    table grows without bound."""
    if retention_days is None:
        retention_days = settings.webhook_event_retention_days if settings else DEFAULT_RETENTION_DAYS
    async with engine.connect() as conn, conn.begin():
        result = await conn.execute(
            text("DELETE FROM webhook_events WHERE received_at < now() - CAST(:ttl AS interval)"),
            {"ttl": f"{retention_days} days"},
        )
    return result.rowcount
