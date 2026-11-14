"""Structured events: JSON lines with the base fields, redaction, and the request and tenant ids."""

import json
import logging
from typing import Any

import httpx
import pytest

from app.events import (
    REDACTED,
    clear_log_context,
    configure_logging,
    log_event,
    request_id_var,
    tenant_id_var,
)
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


@pytest.mark.parametrize("field", ["request_id", "tenant_id", "level", "message", "event", "name", "args"])
def test_a_clashing_field_is_renamed_not_raised(field: str, capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    fields: dict[str, Any] = {field: "x"}
    log_event(log, logging.INFO, "job.created", **fields)
    (line,) = lines(capsys.readouterr().out)
    assert line["event"] == "job.created"
    assert line[f"field_{field}"] == "x"


@pytest.mark.parametrize(
    "field",
    [
        "jwt",
        "session",
        "credentials",
        "auth_header",
        "bearer",
        "x-api-key",
        "X-Auth-Token",
        "private_key",
        "database_url",
        "client_secret",
        "signature",
        "pwd",
        "otp",
    ],
)
def test_more_secret_names_are_redacted(field: str, capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    fields: dict[str, Any] = {field: "v-SENTINEL"}
    log_event(log, logging.INFO, "auth.checked", **fields)
    assert "SENTINEL" not in capsys.readouterr().out


def test_lists_tuples_and_header_pairs_are_walked(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log_event(
        log,
        logging.INFO,
        "auth.checked",
        headers=[("authorization", "Bearer a-SENTINEL"), ("accept", "json")],
        items=[{"token": "b-SENTINEL"}, {"id": 7}],
        nested={"a": [{"b": ({"password": "c-SENTINEL"},)}]},
    )
    out = capsys.readouterr().out
    assert "SENTINEL" not in out
    (line,) = lines(out)
    assert line["headers"][1] == ["accept", "json"]
    assert line["items"][1] == {"id": 7}


def test_secret_shaped_text_is_scrubbed_everywhere(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    try:
        raise RuntimeError(
            "boom Authorization: Bearer e-SENTINEL [parameters: ('f-SENTINEL@example.com', 3)] done"
        )
    except RuntimeError as exc:
        log_event(
            log,
            logging.ERROR,
            "job.failed",
            "call to https://user:g-SENTINEL@host/x?token=h-SENTINEL&page=2 failed",
            exc_info=exc,
            detail="input_value='i-SENTINEL', input_type=str",
            link="https://app/login?code=j-SENTINEL",
        )
    out = capsys.readouterr().out
    assert "SENTINEL" not in out
    (line,) = lines(out)
    assert "page=2" in line["message"]
    assert "[parameters: [redacted]]" in line["exc"]


def test_harmless_words_are_left_alone(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log_event(log, logging.INFO, "job.created", "status_code=500 footprint", footprint=3, error_code="E1")
    (line,) = lines(capsys.readouterr().out)
    assert line["message"] == "status_code=500 footprint"
    assert line["footprint"] == 3
    assert line["error_code"] == "E1"


def test_cycles_depth_and_size_never_drop_the_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    loop: dict[str, Any] = {}
    loop["self"] = loop
    ring: list[Any] = []
    ring.append(ring)
    log_event(log, logging.INFO, "job.created", loop=loop, ring=ring, big="x" * 100_000, odd={(1, 2): "t"})
    (line,) = lines(capsys.readouterr().out)
    assert line["event"] == "job.created"
    assert len(line["big"]) < 3000
    assert "[too deep]" in json.dumps(line["loop"])


def test_a_value_that_cannot_be_written_gives_a_fallback_line(capsys: pytest.CaptureFixture[str]) -> None:
    class Bad:
        def __str__(self) -> str:
            raise RuntimeError("no")

    configure_logging("INFO")
    log_event(log, logging.INFO, "job.created", bad=Bad())
    (line,) = lines(capsys.readouterr().out)
    assert line["event"] == "log.format_failed"
    assert line["original_event"] == "job.created"


def test_clear_log_context_forgets_the_ids(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    request_id_var.set("req-old")
    tenant_id_var.set("t-old")
    clear_log_context()
    log_event(log, logging.INFO, "job.started")
    (line,) = lines(capsys.readouterr().out)
    assert "request_id" not in line
    assert "tenant_id" not in line


def test_the_access_log_drops_the_query_string(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "1.2.3.4", "GET", "/v1/login?magic=k-SENTINEL", "1.1", 200
    )
    out = capsys.readouterr().out
    assert "SENTINEL" not in out
    assert "/v1/login" in out


def test_caplog_still_sees_lines_after_configure(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("INFO")
    with caplog.at_level(logging.INFO):
        log_event(log, logging.INFO, "job.created")
    assert any(getattr(r, "event", None) == "job.created" for r in caplog.records)


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


async def test_the_tenant_of_one_request_never_reaches_the_next(
    app_factory: Any, world: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    app = app_factory(extra_v1_routers=[probes.router])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/v1/_dataerror", headers=world.headers())
        await c.get("/v1/_boom", headers={"X-Request-ID": "req-anon"})
    (line,) = events(capsys.readouterr().out, "request.unhandled_error")
    assert line["request_id"] == "req-anon"
    assert "tenant_id" not in line
