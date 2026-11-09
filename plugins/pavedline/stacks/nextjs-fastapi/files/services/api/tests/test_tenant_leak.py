"""The cross-tenant leak fixture.

Every route under /v1 and every job type is exercised as tenant A with tenant B's ids and must fail
or leak nothing; a route missing from `leak_registry.py` fails here.
"""

import contextlib
from typing import Any

import httpx
import psycopg
import pytest
from fastapi import APIRouter
from psycopg import sql

from tests import leak_registry
from tests.conftest import World, client_for
from tests.leak_support import Exempt, Request, RouteCase, coverage_problems, served_routes


def tenant_tables(conn: psycopg.Connection[Any]) -> list[str]:
    rows = conn.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows]


def snapshot_of_b(world: World) -> dict[str, int]:
    out: dict[str, int] = {}
    with psycopg.connect(world.db.owner_url) as conn:
        for table in tenant_tables(conn):
            row = conn.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s").format(sql.Identifier(table)),
                (world.tenant_b,),
            ).fetchone()
            assert row is not None
            out[table] = row[0]
    return out


def test_every_served_route_is_in_the_registry(app: Any) -> None:
    problems = coverage_problems(served_routes(app), leak_registry.ROUTES, leak_registry.EXEMPT)
    assert problems == []


async def test_a_route_missing_from_the_registry_fails_the_fixture(app_factory: Any) -> None:
    router = APIRouter()

    @router.get("/orphans/{orphan_id}")
    async def get_orphan(orphan_id: str) -> dict[str, str]:
        return {"id": orphan_id}

    app = app_factory(extra_v1_routers=[router])
    problems = coverage_problems(served_routes(app), leak_registry.ROUTES, leak_registry.EXEMPT)
    assert problems == ["route not in the leak registry: GET /v1/orphans/{orphan_id}"]


def test_an_exemption_needs_its_own_reason_and_a_real_route() -> None:
    served = {("GET", "/v1/public")}
    assert coverage_problems(served, [], [Exempt("GET", "/v1/public", "  ")]) == [
        "exemption without a reason: GET /v1/public"
    ]
    assert coverage_problems(served, [], [Exempt("GET", "/v1/public", "public by design")]) == []
    stale = coverage_problems(set(), [], [Exempt("GET", "/v1/gone", "x")])
    assert stale == ["leak registry entry for a route that does not exist: GET /v1/gone"]


@pytest.mark.parametrize("case", leak_registry.ROUTES, ids=lambda c: f"{c.method} {c.path}")
async def test_route_as_tenant_a_with_tenant_b_ids(case: RouteCase, app: Any, world: World) -> None:
    before = snapshot_of_b(world)
    req: Request = case.build(world)
    async with client_for(app) as c:
        r: httpx.Response = await c.request(
            req.method, req.path, json=req.json, headers={**world.headers("a"), **req.headers}
        )
    if case.expect == "denied":
        assert r.status_code in (403, 404), f"{case.method} {case.path} answered {r.status_code}: {r.text}"
    else:
        for value in world.ids_b.values():
            assert str(value) not in r.text, f"{case.method} {case.path} leaked tenant B's {value}"
    assert snapshot_of_b(world) == before, "tenant B's rows changed"


@pytest.mark.parametrize("job", leak_registry.JOBS, ids=lambda j: j.name)
async def test_job_as_tenant_a_with_tenant_b_ids(job: Any, world: World) -> None:
    before = snapshot_of_b(world)
    with contextlib.suppress(Exception):  # failing is the passing outcome
        await job.run(world)
    assert snapshot_of_b(world) == before


async def test_without_a_token_every_route_is_401(app: Any) -> None:
    async with client_for(app) as c:
        for method, path in sorted(served_routes(app)):
            r = await c.request(method, path.replace("{", "").replace("}", ""))
            assert r.status_code == 401, f"{method} {path} answered {r.status_code}"
