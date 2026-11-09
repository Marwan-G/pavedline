import base64
import hashlib
import hmac
import time

import pytest

from app.services.webhook_signatures import WebhookError, verify_stripe, verify_svix

NOW = 1_800_000_000
KEY = b"throwaway-key-bytes-0123456789ab"
SVIX_SECRET = "whsec_" + base64.b64encode(KEY).decode()
OTHER_SECRET = "whsec_" + base64.b64encode(b"another-throwaway-key-0123456789").decode()
STRIPE_SECRET = "whsec_stripe_throwaway_secret"
BODY = b'{"type":"user.created",  "data":{"id":"user_1"}}'  # odd spacing: raw bytes


def svix_sig(secret: str, msg_id: str, ts: int, body: bytes) -> str:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    mac = hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode()


def stripe_header(secret: str, ts: int, body: bytes, *extra: str) -> str:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return ",".join([f"t={ts}", f"v1={mac}", *extra])


def svix(**over: object) -> dict[str, object]:
    args: dict[str, object] = {
        "body": BODY,
        "svix_id": "msg_1",
        "svix_timestamp": str(NOW),
        "svix_signature": svix_sig(SVIX_SECRET, "msg_1", NOW, BODY),
        "now": NOW,
    }
    args.update(over)
    return args


def test_svix_valid() -> None:
    ev = verify_svix(SVIX_SECRET, **svix())  # type: ignore[arg-type]
    assert ev.event_id == "msg_1"
    assert ev.provider == "svix"


def test_svix_rotation_accepts_the_second_signature() -> None:
    old = svix_sig(OTHER_SECRET, "msg_1", NOW, BODY)
    new = svix_sig(SVIX_SECRET, "msg_1", NOW, BODY)
    verify_svix(SVIX_SECRET, **svix(svix_signature=f"{old} {new}"))  # type: ignore[arg-type]


def test_svix_bad_signature() -> None:
    bad = svix_sig(OTHER_SECRET, "msg_1", NOW, BODY)
    with pytest.raises(WebhookError) as e:
        verify_svix(SVIX_SECRET, **svix(svix_signature=bad))  # type: ignore[arg-type]
    assert e.value.kind == "invalid"


def test_svix_tampered_body() -> None:
    with pytest.raises(WebhookError) as e:
        verify_svix(SVIX_SECRET, **svix(body=BODY + b" "))  # type: ignore[arg-type]
    assert e.value.kind == "invalid"


@pytest.mark.parametrize("delta", [-301, 301])
def test_svix_stale_and_future_timestamps(delta: int) -> None:
    ts = NOW + delta
    with pytest.raises(WebhookError) as e:
        verify_svix(
            SVIX_SECRET,
            **svix(svix_timestamp=str(ts), svix_signature=svix_sig(SVIX_SECRET, "msg_1", ts, BODY)),  # type: ignore[arg-type]
        )
    assert e.value.kind == "invalid"


def test_svix_edge_of_the_window_is_accepted() -> None:
    ts = NOW - 300
    verify_svix(
        SVIX_SECRET,
        **svix(svix_timestamp=str(ts), svix_signature=svix_sig(SVIX_SECRET, "msg_1", ts, BODY)),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("missing", ["svix_id", "svix_timestamp", "svix_signature"])
def test_svix_missing_headers(missing: str) -> None:
    with pytest.raises(WebhookError) as e:
        verify_svix(SVIX_SECRET, **svix(**{missing: None}))  # type: ignore[arg-type]
    assert e.value.kind == "missing"


def test_svix_non_numeric_timestamp() -> None:
    with pytest.raises(WebhookError) as e:
        verify_svix(SVIX_SECRET, **svix(svix_timestamp="12.5"))  # type: ignore[arg-type]
    assert e.value.kind == "missing"


def test_svix_garbage_signature_entries_are_ignored() -> None:
    good = svix_sig(SVIX_SECRET, "msg_1", NOW, BODY)
    verify_svix(SVIX_SECRET, **svix(svix_signature=f"v2,xx junk {good}"))  # type: ignore[arg-type]


def test_stripe_valid_and_default_clock() -> None:
    ts = int(time.time())
    verify_stripe(STRIPE_SECRET, body=BODY, signature_header=stripe_header(STRIPE_SECRET, ts, BODY))


def test_stripe_rotation_and_v0_is_ignored() -> None:
    old = stripe_header(OTHER_SECRET, NOW, BODY).split(",")[1]
    new = stripe_header(STRIPE_SECRET, NOW, BODY).split(",")[1]
    verify_stripe(STRIPE_SECRET, body=BODY, signature_header=f"t={NOW},{old},{new}", now=NOW)
    # a valid-looking v0 alone is not enough
    v0 = "v0=" + new.removeprefix("v1=")
    with pytest.raises(WebhookError):
        verify_stripe(STRIPE_SECRET, body=BODY, signature_header=f"t={NOW},{v0}", now=NOW)


def test_stripe_bad_tampered_stale_future_missing() -> None:
    good = stripe_header(STRIPE_SECRET, NOW, BODY)
    with pytest.raises(WebhookError) as e:
        verify_stripe(OTHER_SECRET, body=BODY, signature_header=good, now=NOW)
    assert e.value.kind == "invalid"
    with pytest.raises(WebhookError) as e:
        verify_stripe(STRIPE_SECRET, body=BODY + b"x", signature_header=good, now=NOW)
    assert e.value.kind == "invalid"
    for delta in (-301, 301):
        with pytest.raises(WebhookError) as e:
            verify_stripe(STRIPE_SECRET, body=BODY, signature_header=good, now=NOW + delta)
        assert e.value.kind == "invalid"
    for header in (None, "", "v1=abc", f"t={NOW}"):
        with pytest.raises(WebhookError) as e:
            verify_stripe(STRIPE_SECRET, body=BODY, signature_header=header, now=NOW)
        assert e.value.kind == "missing"


@pytest.mark.parametrize("secret", ["", "whsec_", "whsec_AAAA"])
def test_an_empty_or_tiny_svix_key_never_verifies_even_with_a_forged_signature(secret: str) -> None:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    mac = hmac.new(key, f"msg_1.{NOW}.".encode() + BODY, hashlib.sha256).digest()
    forged = "v1," + base64.b64encode(mac).decode()
    with pytest.raises(ValueError, match="empty or too short"):
        verify_svix(secret, **svix(svix_signature=forged))  # type: ignore[arg-type]


@pytest.mark.parametrize("secret", ["", "short"])
def test_an_empty_or_tiny_stripe_key_never_verifies_even_with_a_forged_signature(secret: str) -> None:
    forged = stripe_header(secret, NOW, BODY)
    with pytest.raises(ValueError, match="empty or too short"):
        verify_stripe(secret, body=BODY, signature_header=forged, now=NOW)
