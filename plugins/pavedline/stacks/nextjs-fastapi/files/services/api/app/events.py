"""Structured events: one JSON object per log line on stdout, with the base fields of EVENTS.md.

Emit an event with `log_event(logger, level, "area.what_happened", **fields)`. Every name the code
emits has a row in `docs/observability/EVENTS.md`; `scripts/events_check.py` fails CI otherwise.
Fields carry ids, codes and counts, never secrets or personal data; a field whose name looks secret
is redacted here anyway. Standard library only, so any log tool chosen at step 12 can read the lines
without a new dependency.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
REDACTED = "[redacted]"
_SECRET_NAME = re.compile(
    r"token|password|passwd|secret|authorization|cookie|api_?key|(^|_)key$", re.IGNORECASE
)
# Attributes every LogRecord has; anything else on a record came from `extra=` and becomes a field.
_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def _redact(name: str, value: Any) -> Any:
    if _SECRET_NAME.search(name):
        return REDACTED
    if isinstance(value, dict):
        return {str(k): _redact(str(k), v) for k, v in value.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return value


class JsonFormatter(logging.Formatter):
    """One JSON object per record: the base fields, then the event's own fields."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", None) or "log.message",
            "message": record.getMessage(),
            "logger": record.name,
        }
        request_id = request_id_var.get()
        tenant_id = tenant_id_var.get()
        if request_id is not None:
            line["request_id"] = request_id
        if tenant_id is not None:
            line["tenant_id"] = tenant_id
        for name, value in vars(record).items():
            if name in _RECORD_ATTRS or name == "event" or name in line:
                continue
            line[name] = _redact(name, value)
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Send every log line to stdout as JSON. Replaces any handler set before (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        named = logging.getLogger(name)
        named.handlers[:] = []
        named.propagate = True


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str = "",
    /,
    *,
    exc_info: BaseException | None = None,
    **fields: Any,
) -> None:
    """Emit one registered event. `event` must be `area.what_happened` and have a row in EVENTS.md."""
    if not EVENT_NAME.match(event):
        raise ValueError(f"bad event name {event!r}: use area.what_happened, lowercase snake case")
    clash = sorted(
        set(fields) & (_RECORD_ATTRS | {"event", "ts", "level", "logger", "request_id", "tenant_id"})
    )
    if clash:
        raise ValueError(f"field names reserved for the base fields or the log record: {clash}")
    logger.log(level, message or event, exc_info=exc_info, extra={"event": event, **fields})
