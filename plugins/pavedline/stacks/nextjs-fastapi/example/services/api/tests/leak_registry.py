"""The leak registry for the example slice (replaces the empty starter registry)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg

from app.services.idempotency import fingerprint
from tests.leak_jobs import PLATFORM_JOBS
from tests.leak_support import Exempt, JobCase, Request, RouteCase


def seed_key(tenant_id: uuid.UUID) -> str:
    return f"seed-{tenant_id}"


SEED_BODY: dict[str, Any] = {"name": "Seeded", "price_minor": 100, "currency": "EUR"}
# the exact bytes httpx sends for json=SEED_BODY, so the fingerprints match
SEED_BYTES = json.dumps(SEED_BODY, separators=(",", ":"), ensure_ascii=False).encode()

ROUTES: list[RouteCase] = [
    RouteCase("GET", "/v1/items", lambda w: Request("GET", "/v1/items?limit=100"), expect="no_leak"),
    RouteCase(
        "GET",
        "/v1/items/{item_id}",
        lambda w: Request("GET", f"/v1/items/{w.ids_b['item_id']}"),
        expect="denied",
    ),
    # Tenant A replays tenant B's Idempotency-Key with B's exact request: it must get its own result.
    RouteCase(
        "POST",
        "/v1/items",
        lambda w: Request(
            "POST", "/v1/items", json=SEED_BODY, headers={"Idempotency-Key": seed_key(w.tenant_b)}
        ),
        expect="no_leak",
    ),
]

EXEMPT: list[Exempt] = []
JOBS: list[JobCase] = [*PLATFORM_JOBS]


def seed(conn: psycopg.Connection[Any], tenant_id: uuid.UUID) -> dict[str, Any]:
    """One item, and one stored idempotency key (principal user_a, the caller's own subject) whose
    response names that item."""
    item_id = uuid.uuid7()
    conn.execute(
        "INSERT INTO items (id, tenant_id, name, price_minor, currency) "
        "VALUES (%s, %s, 'Seeded', 100, 'EUR')",
        (item_id, tenant_id),
    )
    body = {"data": {"id": str(item_id), "name": "Seeded", "price_minor": 100, "currency": "EUR"}}
    conn.execute(
        "INSERT INTO idempotency_keys (tenant_id, principal, key, request_fingerprint, response_status, "
        "response_body) VALUES (%s, 'user_a', %s, %s, 201, %s::jsonb)",
        (tenant_id, seed_key(tenant_id), fingerprint("POST", "/v1/items", SEED_BYTES), json.dumps(body)),
    )
    return {"item_id": item_id}
