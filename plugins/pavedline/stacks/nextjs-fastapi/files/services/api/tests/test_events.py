"""Structured events: JSON lines with the base fields, redaction, and the request and tenant ids."""

import json
import logging
from typing import Any

import httpx
import pytest

from app.events import REDACTED, configure_logging, log_event, request_id_var, tenant_id_var
from tests import probes

log = logging.getLogger("tests.events")


def lines(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def events(out: str, name: str) -> list[dict[str, Any]]:
    return [line for line in lines(out) if line["event"] == name]


def test_a_line_is_json_with_the_base_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    rid, tid = request_id_var.set("req-1"), tenant_id_var.set("t-1")
    try:
        log_event(log, logging.INFO, "job.created", "a job was created", job_id="j-1", count=2)
    finally:
        request_id_var.reset(rid)
        tenant_id_var.reset(tid)
    (line,) = lines(capsys.readouterr().out)
    assert {"ts", "level", "event", "message", "logger", "request_id", "tenant_id"} <= set(line)
    assert line["event"] == "job.created"
    assert line["level"] == "info"
    assert line["request_id"] == "req-1"
    assert line["tenant_id"] == "t-1"
    assert line["job_id"] == "j-1"
    assert line["count"] == 2


def test_without_a_request_there_is_no_request_or_tenant_id(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log_event(log, logging.WARNING, "job.retried")
    (line,) = lines(capsys.readouterr().out)
    assert "request_id" not in line
    assert "tenant_id" not in line


def test_a_plain_log_call_is_still_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log.info("from a library")
    (line,) = lines(capsys.readouterr().out)
    assert line["event"] == "log.message"
    assert line["message"] == "from a library"


def test_secret_named_fields_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log_event(
        log,
        logging.INFO,
        "auth.checked",
        access_token="tok-SENTINEL",
        password="pw-SENTINEL",
        api_key="key-SENTINEL",
        headers={"Authorization": "Bearer SENTINEL", "accept": "json"},
    )
    out = capsys.readouterr().out
    assert "SENTINEL" not in out
    (line,) = lines(out)
    assert line["access_token"] == REDACTED
    assert line["password"] == REDACTED
    assert line["api_key"] == REDACTED
    assert line["headers"] == {"Authorization": REDACTED, "accept": "json"}


@pytest.mark.parametrize("name", ["Job.created", "job", "job.", "job created", "job.created!", ""])
def test_a_bad_event_name_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="bad event name"):
        log_event(log, logging.INFO, name)


@pytest.mark.parametrize("field", ["request_id", "tenant_id", "level", "message", "event", "msg", "args"])
def test_a_field_cannot_overwrite_a_base_field(field: str) -> None:
    fields: dict[str, Any] = {field: "x"}
    with pytest.raises(ValueError, match="reserved"):
        log_event(log, logging.INFO, "job.created", **fields)


async def test_an_unhandled_error_logs_its_event_with_the_request_id(
    app_factory: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            "/v1/_boom", headers={"X-Request-ID": "req-log", "Authorization": "Bearer tok-SENTINEL"}
        )
    assert r.status_code == 500
    out = capsys.readouterr().out
    (line,) = events(out, "request.unhandled_error")
    assert line["level"] == "error"
    assert line["request_id"] == "req-log"
    assert "exc" in line
    assert "tok-SENTINEL" not in out


async def test_a_tenant_request_logs_the_tenant_id(
    app_factory: Any, world: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/v1/_dataerror", headers={**world.headers(), "X-Request-ID": "req-t"})
    assert r.status_code == 422
    (line,) = events(capsys.readouterr().out, "db.data_error")
    assert line["tenant_id"] == str(world.tenant_a)
    assert line["request_id"] == "req-t"


async def test_a_request_body_is_never_logged(app_factory: Any, capsys: pytest.CaptureFixture[str]) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/v1/_echo", content=b'{"note": "body-SENTINEL"}')
        await c.get("/v1/_boom")
    assert "body-SENTINEL" not in capsys.readouterr().out
