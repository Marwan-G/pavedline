"""The leak registry: every route under /v1 and every job type, as tenant A using tenant B's ids.

Add an entry in the same change that adds a route or a job. `test_tenant_leak.py` fails when a route
is missing, when an exemption has no reason, and when an entry names a route that no longer exists.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg

from tests.leak_jobs import PLATFORM_JOBS
from tests.leak_support import Exempt, JobCase, RouteCase

ROUTES: list[RouteCase] = []

# Each exemption carries its own reason (a public route, a webhook ingress...). Never share one reason.
EXEMPT: list[Exempt] = []


# Every job type, run as tenant A with tenant B's ids. The platform job types (leak_jobs.py) come first;
# a scheduled job MUST call purge_expired_idempotency_keys and purge_expired_webhook_events. Add each new job type here.
JOBS: list[JobCase] = [*PLATFORM_JOBS]


def seed(conn: psycopg.Connection[Any], tenant_id: uuid.UUID) -> dict[str, Any]:
    """Insert one of every tenant entity for `tenant_id` (as the owner role); return the ids by name."""
    return {}
