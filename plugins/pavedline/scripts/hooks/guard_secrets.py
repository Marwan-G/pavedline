#!/usr/bin/env python3
"""PreToolUse guard: block .env access and secret material in written content."""
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

READERS = {"cat", "less", "more", "head", "tail", "source", ".", "grep", "awk",
           "sed", "cp", "base64"}
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n"}


def _tokens(command):
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return re.split(r"\s+", command.replace(";", " ; ").replace("|", " | "))


def bash_reads_env(command):
    toks = [t for t in _tokens(command) if t]
    reading = False
    for i, t in enumerate(toks):
        if t in SEPARATORS or set(t) <= set(";&|"):
            reading = False
            continue
        if t == "<" and i + 1 < len(toks) and _common.is_env_file(toks[i + 1]):
            return toks[i + 1]
        if t.startswith("<") and len(t) > 1 and _common.is_env_file(t.lstrip("<")):
            return t.lstrip("<")
        if not reading:
            if os.path.basename(t) in READERS:
                reading = True
            continue
        if _common.is_env_file(t):
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

    if tool in ("Read", "Write", "Edit"):
        fp = ti.get("file_path")
        if isinstance(fp, str) and fp:
            resolved = fp if os.path.isabs(fp) else os.path.join(cwd, fp)
            if _common.is_env_file(resolved):
                _common.block(
                    f"Blocked: {fp} is an environment file that may hold secrets. "
                    "Use .env.example for variable names, and ask the user to edit .env themselves."
                )
        text = None
        if tool == "Write":
            text = ti.get("content")
        elif tool == "Edit":
            text = ti.get("new_string")
        if isinstance(text, str) and secret_in(text):
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
