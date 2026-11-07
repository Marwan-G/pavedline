"""Shared helpers for Pavedline hooks. Python stdlib only."""
import json
import os
import re
import shlex
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


# ---------------------------------------------------------------------------
# Bash command parsing shared by the guards (heuristic, not a full shell parser)
# ---------------------------------------------------------------------------

ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "ash"}
# Words that run another command: skip them (and their options) to reach it.
WRAPPERS = {"sudo", "doas", "env", "command", "builtin", "exec", "nohup", "nice", "time",
            "xargs", "watch", "timeout", "stdbuf", "ionice", "setsid"}
WRAPPER_VALUE_OPTS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C"},
    "nice": {"-n"},
    "xargs": {"-I", "-n", "-P", "-L", "-s", "-d", "-a", "-E"},
    "watch": {"-n", "-d"},
    "timeout": {"-s", "-k"},
    "ionice": {"-c", "-n", "-p"},
}
CONTROL_WORDS = {"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until"}
MAX_DEPTH = 6


def tokens(command):
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return re.split(r"\s+", re.sub(r"([;|&()])", r" \1 ", command))


def _is_sep(t, parens):
    if not t:
        return False
    if parens and set(t) <= set("()"):
        return True
    return t in SEPARATORS or set(t) <= set(";&|")


def split_commands(toks, parens=False):
    cmds, cur = [], []
    for t in toks:
        if not t:
            continue
        if _is_sep(t, parens):
            cmds.append(cur)
            cur = []
        else:
            cur.append(t)
    cmds.append(cur)
    return cmds


def _substitutions(text):
    """Inner text of $(...), <(...), >(...) and `...` in text."""
    out = []
    for m in re.finditer(r"[$<>]\(", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        out.append(text[m.end():i - 1 if depth == 0 else i])
    out.extend(re.findall(r"`([^`]*)`", text))
    return out


def unwrap(cmd):
    """Return (assignments, verb, args) with wrappers/prefixes stripped.

    verb is the lower-cased basename without a .exe suffix ('' if none).
    """
    assigns, i = [], 0
    while i < len(cmd):
        t = cmd[i]
        if ASSIGN.match(t):
            assigns.append(t)
            i += 1
            continue
        b = os.path.basename(t).lower()
        if t in CONTROL_WORDS:
            i += 1
            continue
        if b in WRAPPERS:
            i += 1
            while i < len(cmd):
                u = cmd[i]
                if ASSIGN.match(u):
                    assigns.append(u)
                    i += 1
                elif u.startswith("-") and u != "-":
                    i += 1 + (u in WRAPPER_VALUE_OPTS.get(b, ()))
                else:
                    break
            if b == "timeout" and i < len(cmd):
                i += 1  # the duration
            continue
        break
    if i >= len(cmd):
        return assigns, "", []
    verb = os.path.basename(cmd[i]).lower()
    if verb.endswith(".exe"):
        verb = verb[:-4]
    return assigns, verb, cmd[i + 1:]


def shell_commands(command, _depth=0):
    """All simple commands in a Bash string, including those nested in
    bash -c / eval strings, $(...) and backticks. Each is a token list."""
    if _depth > MAX_DEPTH:
        return []
    command = command.replace("\\\n", " ").replace("\n", " ; ")
    out = []
    for inner in _substitutions(command):
        out.extend(shell_commands(inner, _depth + 1))
    for cmd in split_commands(tokens(command), parens=True):
        if not cmd:
            continue
        out.append(cmd)
        _, verb, args = unwrap(cmd)
        if verb == "eval" and args:
            out.extend(shell_commands(" ".join(args), _depth + 1))
        elif verb in SHELLS:
            for j, a in enumerate(args):
                if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", a) and j + 1 < len(args):
                    out.extend(shell_commands(args[j + 1], _depth + 1))
                    break
    return out
