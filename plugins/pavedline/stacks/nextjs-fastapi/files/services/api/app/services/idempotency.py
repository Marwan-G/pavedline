"""Idempotency-Key handling, stored under (tenant_id, principal, key).

Same key and same fingerprint (method, path, sha256 of the body): the original response again.
Same key, different fingerprint: 422, never the cached body. Keys live for 24 hours.
The key is claimed first (INSERT ... ON CONFLICT DO NOTHING) inside the request's transaction, so a
concurrent request with the same key waits for the first to commit and then reads its result, and a
handler that fails rolls the claim back so the client may retry.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.db.tenant import list_tenant_ids, tenant_transaction
from app.errors import ApiError

TTL_HOURS = 24
MAX_KEY_LENGTH = 255


@dataclass(frozen=True)
class StoredResponse:
    status: int
    body: dict[str, Any]


def fingerprint(method: str, path: str, body: bytes) -> str:
    # The query string is left out on purpose: a state-changing operation takes its input from the
    # body; a client that varies the query between retries of one logical request still gets the
    # original result. An operation whose behaviour depends on query parameters must add them here.
    body_hash = hashlib.sha256(body).hexdigest()
    return hashlib.sha256(f"{method.upper()}\n{path}\n{body_hash}".encode()).hexdigest()


async def run_idempotent(
    conn: AsyncConnection,
    *,
    tenant_id: UUID,
    principal: str,
    key: str,
    fingerprint: str,
    handler: Callable[[], Awaitable[StoredResponse]],
) -> StoredResponse:
    """Run `handler` once per key. `conn` must be inside `tenant_transaction` for `tenant_id`."""
    params: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "principal": principal,
        "key": key,
        "fingerprint": fingerprint,
        "ttl": f"{TTL_HOURS} hours",
    }
    await conn.execute(
        text(
            "DELETE FROM idempotency_keys WHERE tenant_id = :tenant_id AND principal = :principal "
            "AND key = :key AND created_at < now() - CAST(:ttl AS interval)"
        ),
        params,
    )
    claimed = (
        await conn.execute(
            text(
                "INSERT INTO idempotency_keys (tenant_id, principal, key, request_fingerprint, "
                "response_status, response_body) "
                "VALUES (:tenant_id, :principal, :key, :fingerprint, 0, '{}'::jsonb) "
                "ON CONFLICT (tenant_id, principal, key) DO NOTHING RETURNING key"
            ),
            params,
        )
    ).first()
    if claimed is None:
        stored = (
            await conn.execute(
                text(
                    "SELECT request_fingerprint, response_status, response_body FROM idempotency_keys "
                    "WHERE tenant_id = :tenant_id AND principal = :principal AND key = :key"
                ),
                params,
            )
        ).one()
        if stored[0] != fingerprint:
            raise ApiError(
                422,
                "idempotency_key_reuse",
                "This Idempotency-Key was already used with a different request",
            )
        return StoredResponse(int(stored[1]), dict(stored[2]))
    response = await handler()
    await conn.execute(
        text(
            "UPDATE idempotency_keys SET response_status = :status, "
            "response_body = CAST(:body AS jsonb) "
            "WHERE tenant_id = :tenant_id AND principal = :principal AND key = :key"
        ),
        {**params, "status": response.status, "body": json.dumps(response.body)},
    )
    return response


async def purge_expired_idempotency_keys(engine: AsyncEngine) -> int:
    """Delete keys older than the 24 hour lifetime, for every tenant; returns how many went.

    A cross-tenant job: it lists tenants from the global table, then runs ONE tenant_transaction per
    tenant (SET LOCAL), so row-level security stays on. A scheduled job MUST call this (the table
    would otherwise grow without bound); register it in `tests/leak_registry.py` JOBS.
    """
    removed = 0
    for tenant_id in await list_tenant_ids(engine):
        async with tenant_transaction(engine, tenant_id) as conn:
            result = await conn.execute(
                text(
                    "DELETE FROM idempotency_keys WHERE tenant_id = :tenant_id "
                    "AND created_at < now() - CAST(:ttl AS interval)"
                ),
                {"tenant_id": str(tenant_id), "ttl": f"{TTL_HOURS} hours"},
            )
            removed += result.rowcount
    return removed
