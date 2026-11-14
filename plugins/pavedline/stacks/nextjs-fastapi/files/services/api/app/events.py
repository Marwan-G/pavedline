"""Structured events: one JSON object per log line on stdout, with the base fields of EVENTS.md.

Emit an event with `log_event(logger, level, "area.what_happened", **fields)`. Every name the code
emits has a row in `docs/observability/EVENTS.md`; `scripts/events_check.py` fails CI otherwise.
Fields carry ids, codes and counts, never secrets or personal data. As a safety net the formatter
also redacts fields whose names look secret, scrubs secret-shaped text (bearer tokens, passwords in
URLs, secret query values, SQL parameters, raw validation input) from every string, the message and
the traceback included, and cuts long values. A line is never dropped: if formatting fails, a
minimal line with the base fields says so. Standard library only.
"""

import json
import logging
import math
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, cast

EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
REDACTED = "[redacted]"
MAX_VALUE = 2048  # characters per string field and per message
MAX_EXC = 8192  # characters of traceback
MAX_DEPTH = 5  # nested dicts and lists
BASE_FIELDS = frozenset({"ts", "level", "event", "message", "logger", "request_id", "tenant_id", "exc"})

# Matched against the field name with `-` read as `_` (so `x-api-key` is `x_api_key`).
_SECRET_NAME = re.compile(
    r"token|passw|pwd|secret|authoriz|auth_header|bearer|cookie|session|jwt|credential|private"
    r"|signature|api_?key|(^|_)key$|(^|_)keys$|(^|_)otp($|_)|dsn|database_url|connection_string",
    re.IGNORECASE,
)
# Each pattern scans forward through one negated class or always matches, so it runs in linear
# time; `scrub` also cuts its input first. No upper bounds on values: a long token is redacted whole.
_SENSITIVE_WORD = r"[a-z_]{0,40}(?:token|key|secret|password|passwd|signature|sig|credential)s?"
_SCRUBS = (
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+"), r"\1 " + REDACTED),
    (re.compile(r"(?i)(://)[^/\s:@]{1,200}:[^/\s]{1,200}@"), r"\1" + REDACTED + "@"),
    # password='x', "token": "x", 'api_key': 'x' (reprs, dicts, JSON); an unclosed quote runs to the line end
    (
        re.compile(r"(?i)(\b" + _SENSITIVE_WORD + r"['\"]?\s*[:=]\s*)('[^'\n]*'?|\"[^\"\n]*\"?)"),
        r"\1'" + REDACTED + "'",
    ),
    # token=x, ?api_key=x
    (re.compile(r"(?i)(\b" + _SENSITIVE_WORD + r"\s*=\s*)(?!['\"])[^&\s,;)'\"]+"), r"\1" + REDACTED),
    (re.compile(r"(?i)(?<![a-z0-9_])(code=)[^&\s'\"]+"), r"\1" + REDACTED),  # an OAuth or magic-link code
    # SQLAlchemy's bound values, pydantic's raw input and Postgres's DETAIL line (it carries the row's
    # values, e.g. `Key (email)=(a@b.c) already exists`): redact to the end of the line.
    (re.compile(r"\[parameters: [^\n]*"), "[parameters: " + REDACTED + "]"),
    (re.compile(r"(input_value=)[^\n]*"), r"\1" + REDACTED),
    (re.compile(r"(?m)^([ \t]*DETAIL:)[^\n]*"), r"\1 " + REDACTED),
    (re.compile(r"(\bKey \([^)\n]{0,200}\)=)\([^\n]*"), r"\1(" + REDACTED + ")"),
)
# Attributes every LogRecord has; anything else on a record came from `extra=` and becomes a field.
_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # uvicorn's copy of the message with terminal colours
}

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def clear_log_context() -> None:
    """Forget the request and tenant ids: call it first in a background task or job loop started
    from a request, which otherwise inherits that request's ids on every line it logs."""
    request_id_var.set(None)
    tenant_id_var.set(None)


def scrub(text: str, limit: int = MAX_VALUE) -> str:
    """Remove secret-shaped text and cut the result to `limit` characters."""
    text = text[: limit * 4]  # bound the work of the patterns below on a huge string
    for pattern, repl in _SCRUBS:
        text = pattern.sub(repl, text)
    if len(text) > limit:
        text = text[:limit] + "...[truncated]"
    return text


def _secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name.replace("-", "_")))


def _clean(name: str, value: Any, depth: int = 0) -> Any:
    """Redact by name, recurse into dicts, lists, tuples and sets (to MAX_DEPTH), scrub strings."""
    result: Any
    if _secret_name(name):
        result = REDACTED
    elif depth >= MAX_DEPTH:
        result = "[too deep]"
    elif isinstance(value, dict):
        pairs = cast(dict[Any, Any], value).items()
        result = {str(k): _clean(str(k), v, depth + 1) for k, v in pairs}
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = list(cast(list[Any], value))
        # A (name, value) pair, as in a list of headers (str or bytes): redact the value by the pair's name.
        first = items[0] if items else None
        pair_name = first.decode("latin-1") if isinstance(first, bytes) else first
        if len(items) == 2 and isinstance(pair_name, str) and _secret_name(pair_name):
            result = [pair_name, REDACTED]
        else:
            result = [_clean(name, v, depth + 1) for v in items[:100]]
    elif isinstance(value, str):
        result = scrub(value)
    elif isinstance(value, float) and not math.isfinite(value):
        result = str(value)  # NaN and Infinity are not valid JSON
    elif value is None or isinstance(value, (bool, int, float)):
        result = value
    else:
        result = scrub(str(value))
    return result


class JsonFormatter(logging.Formatter):
    """One JSON object per record: the base fields, then the event's own fields. ASCII only, so a
    lone surrogate or a cut multibyte character can never break the write or a reader."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            return self._format(record)
        except Exception as exc:  # never lose the line: fall back to the base fields
            return json.dumps(
                {
                    "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
                    "level": record.levelname.lower(),
                    "event": "log.format_failed",
                    "message": f"a log line could not be formatted: {type(exc).__name__}",
                    "logger": record.name,
                    "original_event": str(getattr(record, "event", "log.message")),
                }
            )

    def _format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", None) or "log.message",
            "message": scrub(record.getMessage()),
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
            line[name] = _clean(name, value)
        if record.exc_info:
            line["exc"] = scrub(self.formatException(record.exc_info), MAX_EXC)
        return json.dumps(line, default=str, ensure_ascii=True)


class _StdoutHandler(logging.StreamHandler):  # pyright: ignore[reportMissingTypeArgument]
    """Writes to whatever `sys.stdout` is at the time of each line (test capture replaces it)."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


class _DropQueryString(logging.Filter):
    """uvicorn's access line carries the full path; a query string may hold a token or a magic link."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            # Split by hand: a URL parser raises on paths such as `//[x`, and a filter must never raise.
            path = args[2].split("?", 1)[0].split("#", 1)[0]
            record.args = (*args[:2], path, *args[3:])
        return True


def configure_logging(level: str) -> None:
    """Send every log line to stdout as JSON. Idempotent; keeps handlers others added (test capture)."""
    root = logging.getLogger()
    # Replace our own handler and plain stream handlers (`basicConfig`), keep subclasses such as pytest's.
    root.handlers[:] = [
        h for h in root.handlers if type(h) is not logging.StreamHandler and not isinstance(h, _StdoutHandler)
    ]
    handler = _StdoutHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        named = logging.getLogger(name)
        named.handlers[:] = []
        named.propagate = True
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _DropQueryString) for f in access.filters):
        access.addFilter(_DropQueryString())


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
    """Emit one registered event. `event` must be `area.what_happened` and have a row in EVENTS.md.

    A field whose name clashes with a base field or a log-record attribute (`name`, `message`,
    `module`...) is kept as `field_<name>`, so logging never fails a request.
    """
    if not EVENT_NAME.match(event):
        raise ValueError(f"bad event name {event!r}: use area.what_happened, lowercase snake case")
    extra: dict[str, Any] = {"event": event}
    for key, value in fields.items():
        extra[f"field_{key}" if key in _RECORD_ATTRS or key in BASE_FIELDS else key] = value
    logger.log(level, message or event, exc_info=exc_info, extra=extra)
