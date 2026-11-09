"""Webhook signature verification for the two default schemes: Svix (Clerk) and Stripe.

Pure functions over the RAW request body bytes (never re-serialised JSON). Constant-time comparison, a
timestamp window in both directions, several signatures accepted (secret rotation). No HTTP, no database.

Svix:   headers svix-id, svix-timestamp, svix-signature (space-separated `v1,<base64>` entries); secret
        `whsec_<base64>`; HMAC-SHA256 over `{id}.{timestamp}.{body}`; the digest is base64.
Stripe: header `Stripe-Signature: t=<unix>,v1=<hex>[,v1=<hex>][,v0=...]`; HMAC-SHA256 over `{t}.{body}`
        with the endpoint secret (`whsec_...` used as is); hex digest; only `v1` counts.
Sources and dates: skills/fastapi-service/references/sources.md.
"""

import base64
import binascii
import hashlib
import hmac
import time
from dataclasses import dataclass

DEFAULT_TOLERANCE_SECONDS = 300
# Defence in depth: an empty or tiny key never verifies (Settings enforces the real minimum).
MIN_KEY_BYTES = 8
MAX_SIGNATURES = 16  # a header with more entries than any rotation needs is hostile


class WebhookError(Exception):
    """`missing` (headers absent or unreadable: HTTP 400) or `invalid` (signature or timestamp: HTTP 401)."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class VerifiedEvent:
    provider: str
    event_id: str | None  # Svix: svix-id; Stripe: the id is inside the body, read it after verification
    timestamp: int


def _check_timestamp(raw: str, now: float, tolerance: int) -> int:
    if not raw.isascii() or not raw.isdigit() or len(raw) > 12:
        raise WebhookError("missing", "The timestamp header is missing or not a number")
    ts = int(raw)
    if abs(now - ts) > tolerance:  # stale AND future beyond the window
        raise WebhookError("invalid", "The timestamp is outside the allowed window")
    return ts


def _any_equal(expected: str, candidates: list[str]) -> bool:
    ok = False
    for cand in candidates[:MAX_SIGNATURES]:
        ok |= hmac.compare_digest(expected.encode(), cand.encode())  # no early exit: constant work
    return ok


def verify_svix(
    secret: str,
    *,
    body: bytes,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> VerifiedEvent:
    if not svix_id or not svix_timestamp or not svix_signature:
        raise WebhookError("missing", "svix-id, svix-timestamp and svix-signature are required")
    if len(svix_id) > 255 or not svix_id.isprintable():
        raise WebhookError("invalid", "The svix-id is not acceptable")
    ts = _check_timestamp(svix_timestamp, time.time() if now is None else now, tolerance)
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The webhook secret is not valid base64") from exc
    if len(key) < MIN_KEY_BYTES:
        raise ValueError("The webhook secret is empty or too short")
    signed = f"{svix_id}.{svix_timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    candidates = [part.split(",", 1)[1] for part in svix_signature.split() if part.startswith("v1,")]
    if not _any_equal(expected, candidates):
        raise WebhookError("invalid", "The signature does not match")
    return VerifiedEvent("svix", svix_id, ts)


def verify_stripe(
    secret: str,
    *,
    body: bytes,
    signature_header: str | None,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> VerifiedEvent:
    if len(secret.encode()) < MIN_KEY_BYTES:
        raise ValueError("The webhook secret is empty or too short")
    if not signature_header:
        raise WebhookError("missing", "The Stripe-Signature header is required")
    timestamp = ""
    candidates: list[str] = []
    for item in signature_header.split(","):
        name, _, value = item.strip().partition("=")
        if name == "t":
            timestamp = value
        elif name == "v1":  # every other scheme (v0 ...) is ignored: no downgrade
            candidates.append(value)
    if not timestamp or not candidates:
        raise WebhookError("missing", "The Stripe-Signature header has no timestamp or v1 signature")
    ts = _check_timestamp(timestamp, time.time() if now is None else now, tolerance)
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    if not _any_equal(expected, candidates):
        raise WebhookError("invalid", "The signature does not match")
    return VerifiedEvent("stripe", None, ts)
