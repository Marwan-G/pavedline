#!/usr/bin/env python3
"""PreToolUse guard: block .env access and secret material in written content."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n"}
# Verbs that only name or move an env file without reading its contents.
SAFE_VERBS = {"ls", "stat", "test", "[", "rm", "mv", "touch"}
SAFE_GIT = {"add", "rm", "mv", "check-ignore"}
PIECE_SPLIT = re.compile(r"[`$(){}<>\"';:=,\s]+")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


_tokens = _common.tokens


def _names_env(token):
    """True if the token, or any word/path embedded in it, is an env file.

    Splitting on quotes, parens, backticks, whitespace, '=' and ':' also covers
    nested code strings (bash -c "cat .env", python -c "open('.env')") and
    git refs (HEAD:.env) without a recursive shell parser.
    """
    if _common.is_env_file(token):
        return True
    return any(_common.is_env_file(p) for p in PIECE_SPLIT.split(token) if p)


def _is_safe(cmd):
    i = 0
    while i < len(cmd) and ASSIGN.match(cmd[i]):
        i += 1
    if i >= len(cmd):
        return True
    verb = os.path.basename(cmd[i])
    if verb == "git":
        rest = [t for t in cmd[i + 1:] if not t.startswith("-")]
        return bool(rest) and rest[0] in SAFE_GIT
    return verb in SAFE_VERBS


def bash_reads_env(command):
    toks = [t for t in _tokens(command) if t]
    cmds, cur = [], []
    for t in toks:
        if t in SEPARATORS or set(t) <= set(";&|"):
            cmds.append(cur)
            cur = []
        else:
            cur.append(t)
    cmds.append(cur)
    nested = "`" in command or "$(" in command
    for cmd in cmds:
        safe = _is_safe(cmd) and not nested
        skip_next = False
        for t in cmd:
            if skip_next:  # target of a write redirect (deferred, allowed)
                skip_next = False
                continue
            if t in (">", ">>", ">|", "&>"):
                skip_next = True
                continue
            if safe:
                continue
            if _names_env(t):
                return t
    return None


def secret_in(text):
    for pat in _common.SECRET_PATTERNS:
        if re.search(pat, text):
            return True
    return False


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("pavedline guard_secrets: empty or invalid hook input; allowing.\n")
        _common.allow()
    tool = event.get("tool_name")
    ti = event.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else os.getcwd()

    if tool == "Grep":
        path = ti.get("path")
        glob = ti.get("glob")
        gbase = os.path.basename(glob.lower()) if isinstance(glob, str) else ""
        env_glob = gbase.endswith(".env") or (
            gbase.startswith(".env") and not gbase.endswith(_common.ENV_ALLOWED_SUFFIXES)
        )
        if (isinstance(path, str) and _common.is_env_file(path)) or env_glob:
            _common.block(
                "Blocked: this search targets environment files that may hold secrets. "
                "Search .env.example instead."
            )
    elif tool in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        fp = ti.get("file_path") or ti.get("notebook_path")
        if isinstance(fp, str) and fp:
            resolved = fp if os.path.isabs(fp) else os.path.join(cwd, fp)
            if _common.is_env_file(resolved):
                _common.block(
                    f"Blocked: {fp} is an environment file that may hold secrets. "
                    "Use .env.example for variable names, and ask the user to edit .env themselves."
                )
        texts = []
        if tool == "Write":
            texts = [ti.get("content")]
        elif tool == "Edit":
            texts = [ti.get("new_string")]
        elif tool == "NotebookEdit":
            texts = [ti.get("new_source")]
        elif tool == "MultiEdit" and isinstance(ti.get("edits"), list):
            texts = [e.get("new_string") for e in ti["edits"] if isinstance(e, dict)]
        if any(isinstance(t, str) and secret_in(t) for t in texts):
            _common.block(
                "Blocked: the content looks like a secret (private key or API token). "
                "Reference it through an environment variable or secret manager instead."
            )
    elif tool == "Bash":
        cmd = ti.get("command")
        if isinstance(cmd, str):
            hit = bash_reads_env(cmd)
            if hit:
                _common.block(
                    f"Blocked: this command reads {hit}, an environment file that may hold secrets. "
                    "Use .env.example, or ask the user to run it themselves."
                )
    _common.allow()


if __name__ == "__main__":
    main()
