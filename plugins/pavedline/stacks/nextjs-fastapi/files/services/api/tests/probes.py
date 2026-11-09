"""Test-only routes, mounted with `create_app(extra_v1_routers=[...])`. They never ship in the app."""

from fastapi import APIRouter, Request

from app.db.tenant import tenant_transaction
from app.routes.deps import CurrentPrincipal, DbEngine

router = APIRouter()


@router.get("/_probe")
async def probe(principal: CurrentPrincipal, engine: DbEngine) -> dict[str, dict[str, str]]:
    async with tenant_transaction(engine, principal.tenant_id) as conn:
        from sqlalchemy import text

        setting = (await conn.execute(text("SELECT current_setting('app.tenant_id', true)"))).scalar()
    return {
        "data": {
            "subject": principal.subject,
            "tenant_id": str(principal.tenant_id),
            "db_setting": str(setting),
        }
    }


@router.get("/_boom")
async def boom() -> None:
    raise RuntimeError("secret internal detail")


@router.get("/_dataerror")
async def dataerror(principal: CurrentPrincipal, engine: DbEngine) -> None:
    """A database data error (bad cast): a client problem, never a 500."""
    from sqlalchemy import text

    async with tenant_transaction(engine, principal.tenant_id) as conn:
        await conn.execute(text("SELECT CAST('not a number' AS integer)"))


@router.post("/_echo")
async def echo(request: Request) -> dict[str, int]:
    return {"bytes": len(await request.body())}
