"""Liveness and readiness: unauthenticated, outside /v1, not part of the contract."""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.errors import ApiError
from app.routes.deps import DbEngine

router = APIRouter(include_in_schema=False)
log = logging.getLogger("app.health")


@router.get("/healthz")
async def healthz() -> dict[str, dict[str, str]]:
    """The process is up. Never touches the database, so a database outage does not restart pods."""
    return {"data": {"status": "ok"}}


@router.get("/readyz")
async def readyz(engine: DbEngine) -> dict[str, dict[str, str]]:
    """The database answers as the runtime role."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("readiness check failed: %s", type(exc).__name__)
        raise ApiError(503, "not_ready", "The database is not reachable") from exc
    return {"data": {"status": "ready"}}
