"""Items: tenant-scoped queries. Every statement carries tenant_id; row-level security is the backstop."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ItemRow:
    id: UUID
    name: str
    price_minor: int  # money: integer minor units plus a currency code, never float
    currency: str
    created_at: datetime


COLUMNS = "id, name, price_minor, currency, created_at"


def to_row(row: tuple[object, ...]) -> ItemRow:
    item_id, name, price_minor, currency, created_at = row
    assert isinstance(created_at, datetime)  # noqa: S101
    return ItemRow(UUID(str(item_id)), str(name), int(str(price_minor)), str(currency), created_at)


async def create_item(
    conn: AsyncConnection, tenant_id: UUID, name: str, price_minor: int, currency: str
) -> ItemRow:
    row = (
        await conn.execute(
            text(
                f"INSERT INTO items (id, tenant_id, name, price_minor, currency) "  # noqa: S608
                f"VALUES (:id, :tenant_id, :name, :price_minor, :currency) RETURNING {COLUMNS}"
            ),
            {
                "id": uuid.uuid7(),
                "tenant_id": tenant_id,
                "name": name,
                "price_minor": price_minor,
                "currency": currency,
            },
        )
    ).one()
    return to_row(tuple(row))


async def get_item(conn: AsyncConnection, tenant_id: UUID, item_id: UUID) -> ItemRow | None:
    row = (
        await conn.execute(
            text(f"SELECT {COLUMNS} FROM items WHERE tenant_id = :tenant_id AND id = :id"),  # noqa: S608
            {"tenant_id": tenant_id, "id": item_id},
        )
    ).first()
    return None if row is None else to_row(tuple(row))


async def list_items(
    conn: AsyncConnection, tenant_id: UUID, limit: int, after: UUID | None
) -> tuple[list[ItemRow], UUID | None]:
    """Keyset pagination on the time-ordered id: a stable sort. Returns the page and the next cursor."""
    rows = (
        await conn.execute(
            text(
                f"SELECT {COLUMNS} FROM items WHERE tenant_id = :tenant_id "  # noqa: S608
                "AND (CAST(:after AS uuid) IS NULL OR id > CAST(:after AS uuid)) "
                "ORDER BY id LIMIT :n"
            ),
            {"tenant_id": tenant_id, "after": after, "n": limit + 1},
        )
    ).all()
    page = [to_row(tuple(r)) for r in rows[:limit]]
    next_after = page[-1].id if len(rows) > limit else None
    return page, next_after
