"""Signed webhook receivers: POST /webhooks/clerk (Svix) and POST /webhooks/stripe.
Outside /v1 and not in the contract.

A route exists only when its secret is configured. Order: raw body -> verify the signature and timestamp ->
claim the event id (replay protection) -> do the work or enqueue it -> 2xx fast. Real work belongs in a job.
Unauthenticated by design (the signature is the authentication), so nothing is stored before it verifies.

Status codes: 400 a required header is missing or unreadable; 401 signature wrong, body changed, timestamp
stale or too far in the future; 200 `{"data":{"status":"accepted"}}` the first time, 200
`{"data":{"status":"duplicate"}}` for an event id already accepted (nothing is done twice; a provider's
retry after a lost 2xx is acknowledged, so it does not keep retrying or disable the endpoint).
"""

import json
import logging
from typing import Annotated, Any, cast

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.errors import ApiError
from app.routes.deps import DbEngine
from app.services.webhook_events import MAX_EVENT_ID_LENGTH, claim_event
from app.services.webhook_signatures import (
    VerifiedEvent,
    WebhookError,
    verify_stripe,
    verify_svix,
)
from app.settings import Settings

log = logging.getLogger("app.webhooks")


def _refuse(exc: WebhookError) -> ApiError:
    if exc.kind == "missing":
        return ApiError(400, "webhook_headers_missing", str(exc))
    return ApiError(401, "webhook_signature_invalid", "The webhook signature could not be verified")


def _stripe_event_id(body: bytes) -> str:
    """The id of a VERIFIED Stripe event, read from the body (never before the signature is checked)."""
    try:
        event: Any = json.loads(body)
    except ValueError:
        event = None
    event_id: object = cast(dict[str, object], event).get("id") if isinstance(event, dict) else None
    if not isinstance(event_id, str) or not 0 < len(event_id) <= MAX_EVENT_ID_LENGTH:
        raise ApiError(400, "webhook_event_invalid", "The event has no usable id")
    return event_id


async def _accept(engine: DbEngine, verified: VerifiedEvent, event_id: str) -> JSONResponse:
    async with engine.connect() as conn, conn.begin():
        if not await claim_event(conn, verified.provider, event_id):
            # Already accepted: acknowledge (a provider retries non-2xx) and do nothing.
            return JSONResponse({"data": {"status": "duplicate"}})
        # Skeleton: handle or enqueue the event here, in this transaction, then return fast.
    log.info("webhook accepted", extra={"provider": verified.provider})
    return JSONResponse({"data": {"status": "accepted"}})


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/webhooks", include_in_schema=False)
    tolerance = settings.webhook_tolerance_seconds

    if settings.webhook_clerk_secret is not None:
        clerk_secret = settings.webhook_clerk_secret.get_secret_value()

        @router.post("/clerk")
        async def clerk(  # pyright: ignore[reportUnusedFunction]
            request: Request,
            engine: DbEngine,
            svix_id: Annotated[str | None, Header(alias="svix-id")] = None,
            svix_timestamp: Annotated[str | None, Header(alias="svix-timestamp")] = None,
            svix_signature: Annotated[str | None, Header(alias="svix-signature")] = None,
        ) -> JSONResponse:
            body = await request.body()  # the raw bytes the provider signed
            try:
                verified = verify_svix(
                    clerk_secret,
                    body=body,
                    svix_id=svix_id,
                    svix_timestamp=svix_timestamp,
                    svix_signature=svix_signature,
                    tolerance=tolerance,
                )
            except WebhookError as exc:
                raise _refuse(exc) from exc
            assert verified.event_id is not None  # noqa: S101  (verify_svix always sets it)
            return await _accept(engine, verified, verified.event_id)

    if settings.webhook_stripe_secret is not None:
        stripe_secret = settings.webhook_stripe_secret.get_secret_value()

        @router.post("/stripe")
        async def stripe(  # pyright: ignore[reportUnusedFunction]
            request: Request,
            engine: DbEngine,
            stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
        ) -> JSONResponse:
            body = await request.body()
            try:
                verified = verify_stripe(
                    stripe_secret, body=body, signature_header=stripe_signature, tolerance=tolerance
                )
            except WebhookError as exc:
                raise _refuse(exc) from exc
            return await _accept(engine, verified, _stripe_event_id(body))

    return router
