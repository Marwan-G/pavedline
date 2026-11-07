"""Shared helpers for Pavedline hooks. Python stdlib only."""
import json
import os
import sys
from typing import NoReturn, Optional

# Own copy of the key/token lines of the repo-root .sanitize-denylist (kept in
# sync by tests/hooks/test_guard_secrets.py). Cloud-ID and private-IP lines are
# not secrets and are deliberately excluded.
SECRET_PATTERNS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bghp_[A-Za-z0-9]{36}\b",
    r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",
]

ENV_ALLOWED_SUFFIXES = (".example", ".sample", ".template")


def read_event() -> Optional[dict]:
    """Parse the hook JSON from stdin; None on empty or invalid input."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return None
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def block(reason: str) -> NoReturn:
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)


def allow() -> NoReturn:
    sys.exit(0)


def is_env_file(path: str) -> bool:
    # Case-insensitive: macOS file systems are, so ".ENV" reads the real file.
    name = os.path.basename(str(path).replace("\\", "/").rstrip("/")).lower()
    if name != ".env" and not name.startswith(".env."):
        return False
    return not name.endswith(ENV_ALLOWED_SUFFIXES)
