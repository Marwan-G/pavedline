"""/v1/items: the example slice (contract: docs/api/openapi.yaml)."""

import base64
import binascii
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import AfterValidator, BaseModel, Field

from app.db.tenant import tenant_transaction
from app.errors import ApiError
from app.routes.deps import CurrentPrincipal, DbEngine, IdempotencyKey
from app.services import items as items_service
from app.services.idempotency import StoredResponse, fingerprint, run_idempotent

router = APIRouter()


MAX_BIGINT = 2**63 - 1  # the column is bigint: a larger value is a 422, never a database error


def reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("NUL characters are not allowed")
    return value


class ItemCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200), AfterValidator(reject_nul)]
    price_minor: Annotated[int, Field(ge=0, le=MAX_BIGINT)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class Item(BaseModel):
    id: UUID
    name: str
    price_minor: int
    currency: str
    created_at: datetime


class ItemEnvelope(BaseModel):
    data: Item


class ItemList(BaseModel):
    data: list[Item]
    next_cursor: str | None


def to_item(row: items_service.ItemRow) -> Item:
    return Item(
        id=row.id,
        name=row.name,
        price_minor=row.price_minor,
        currency=row.currency,
        created_at=row.created_at,
    )


def encode_cursor(item_id: UUID) -> str:
    return base64.urlsafe_b64encode(str(item_id).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> UUID:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        return UUID(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, binascii.Error) as exc:
        raise ApiError(422, "invalid_cursor", "The cursor is not valid") from exc


@router.get("/items", operation_id="listItems", response_model=ItemList)
async def list_items(
    principal: CurrentPrincipal,
    engine: DbEngine,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> ItemList:
    after = decode_cursor(cursor) if cursor else None
    async with tenant_transaction(engine, principal.tenant_id) as conn:
        rows, next_after = await items_service.list_items(conn, principal.tenant_id, limit, after)
    return ItemList(
        data=[to_item(r) for r in rows],
        next_cursor=encode_cursor(next_after) if next_after else None,
    )


@router.get("/items/{item_id}", operation_id="getItem", response_model=ItemEnvelope)
async def get_item(item_id: UUID, principal: CurrentPrincipal, engine: DbEngine) -> ItemEnvelope:
    async with tenant_transaction(engine, principal.tenant_id) as conn:
        row = await items_service.get_item(conn, principal.tenant_id, item_id)
    if row is None:  # another tenant's item looks exactly like a missing one
        raise ApiError(404, "not_found", "Item not found")
    return ItemEnvelope(data=to_item(row))


@router.post("/items", operation_id="createItem", status_code=201, response_model=ItemEnvelope)
async def create_item(
    request: Request,
    payload: ItemCreate,
    principal: CurrentPrincipal,
    engine: DbEngine,
    key: IdempotencyKey,
) -> ItemEnvelope:
    request_fingerprint = fingerprint("POST", request.url.path, await request.body())

    async def handler() -> StoredResponse:
        row = await items_service.create_item(
            conn, principal.tenant_id, payload.name, payload.price_minor, payload.currency
        )
        return StoredResponse(201, jsonable_encoder(ItemEnvelope(data=to_item(row))))

    async with tenant_transaction(engine, principal.tenant_id) as conn:
        stored = await run_idempotent(
            conn,
            tenant_id=principal.tenant_id,
            principal=principal.subject,
            key=key,
            fingerprint=request_fingerprint,
            handler=handler,
        )
    # Always through the response model: a stored or fresh body that does not fit the contract fails here
    # instead of being passed to the client unchecked.
    return ItemEnvelope.model_validate(stored.body)
