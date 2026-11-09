import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from tests.conftest import client_for
from tests.test_webhook_signatures import STRIPE_SECRET, SVIX_SECRET, stripe_header, svix_sig


def stripe_body(event_id: str) -> bytes:
    return json.dumps({"id": event_id, "object": "event", "type": "ping"}).encode()


async def post(client: httpx.AsyncClient, path: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    return await client.post(path, content=body, headers={"content-type": "application/json", **headers})


def svix_headers(msg_id: str, body: bytes, ts: int | None = None) -> dict[str, str]:
    ts = int(time.time()) if ts is None else ts
    return {
        "svix-id": msg_id,
        "svix-timestamp": str(ts),
        "svix-signature": svix_sig(SVIX_SECRET, msg_id, ts, body),
    }


async def test_routes_do_not_exist_without_a_secret(client: httpx.AsyncClient) -> None:
    assert (await post(client, "/webhooks/clerk", b"{}", {})).status_code == 404
    assert (await post(client, "/webhooks/stripe", b"{}", {})).status_code == 404


async def test_clerk_accepts_then_rejects_a_replay(app_factory: Callable[..., Any]) -> None:
    app = app_factory(webhook_clerk_secret=SVIX_SECRET)
    body = b'{"type":"user.created","data":{"id":"user_1"}}'
    async with client_for(app) as c:
        h = svix_headers("msg_replay_1", body)
        ok = await post(c, "/webhooks/clerk", body, h)
        assert ok.status_code == 200
        assert ok.json() == {"data": {"status": "accepted"}}
        replay = await post(c, "/webhooks/clerk", body, h)
        assert replay.status_code == 200  # acknowledged, not processed again
        assert replay.json() == {"data": {"status": "duplicate"}}


async def test_clerk_refusals(app_factory: Callable[..., Any]) -> None:
    app = app_factory(webhook_clerk_secret=SVIX_SECRET)
    body = b'{"type":"user.created"}'
    async with client_for(app) as c:
        assert (await post(c, "/webhooks/clerk", body, {})).status_code == 400
        h = svix_headers("msg_refuse_1", body)
        assert (await post(c, "/webhooks/clerk", body + b" ", h)).status_code == 401  # tampered
        stale = svix_headers("msg_refuse_2", body, int(time.time()) - 1000)
        assert (await post(c, "/webhooks/clerk", body, stale)).status_code == 401
        future = svix_headers("msg_refuse_3", body, int(time.time()) + 1000)
        assert (await post(c, "/webhooks/clerk", body, future)).status_code == 401
        # a refused request claimed nothing: the same id still works once it is signed correctly
        assert (await post(c, "/webhooks/clerk", body, h)).status_code == 200


async def test_stripe_accepts_then_rejects_a_replay(app_factory: Callable[..., Any]) -> None:
    app = app_factory(webhook_stripe_secret=STRIPE_SECRET)
    body = stripe_body("evt_replay_1")
    async with client_for(app) as c:
        h = {"Stripe-Signature": stripe_header(STRIPE_SECRET, int(time.time()), body)}
        assert (await post(c, "/webhooks/stripe", body, h)).status_code == 200
        dup = await post(c, "/webhooks/stripe", body, h)
        assert (dup.status_code, dup.json()["data"]["status"]) == (200, "duplicate")
        assert (await post(c, "/webhooks/stripe", body, {})).status_code == 400
        bad = {"Stripe-Signature": stripe_header("whsec_wrong", int(time.time()), body)}
        assert (await post(c, "/webhooks/stripe", body, bad)).status_code == 401


async def test_stripe_event_without_an_id_is_400_after_verification(app_factory: Callable[..., Any]) -> None:
    app = app_factory(webhook_stripe_secret=STRIPE_SECRET)
    body = b'{"object":"event"}'
    async with client_for(app) as c:
        h = {"Stripe-Signature": stripe_header(STRIPE_SECRET, int(time.time()), body)}
        assert (await post(c, "/webhooks/stripe", body, h)).status_code == 400


async def test_the_same_id_from_two_providers_is_two_events(app_factory: Callable[..., Any]) -> None:
    app = app_factory(webhook_clerk_secret=SVIX_SECRET, webhook_stripe_secret=STRIPE_SECRET)
    body = stripe_body("shared_id_1")
    async with client_for(app) as c:
        sh = {"Stripe-Signature": stripe_header(STRIPE_SECRET, int(time.time()), body)}
        assert (await post(c, "/webhooks/stripe", body, sh)).status_code == 200
        assert (await post(c, "/webhooks/clerk", body, svix_headers("shared_id_1", body))).status_code == 200
