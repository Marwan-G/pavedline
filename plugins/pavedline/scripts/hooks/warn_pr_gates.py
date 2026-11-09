#!/usr/bin/env python3
"""PreToolUse hook (Bash): warn when `gh pr create` or `gh pr edit --body` carries no valid gates line.

Never blocks; fails open on input it cannot read.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BODY_LIMIT = 1 << 20  # a PR body never needs more; a huge file must not stall the hook

MESSAGE = ("The pull request body has no valid gates line. Add exactly one line: "
           "`Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓` "
           "(pick one of ✓ or n/a for adversarial; a ✗ is not valid, so a slice with a failing gate is not done), "
           "and list every unfixed finding as `accepted — <reason>`.")


def has_gates(text):
    return _common.GATES_LINE.search(text.replace("\r\n", "\n")) is not None


# In the raw command text the line sits inside quotes or a heredoc, so its anchors are the line break or a quote.
_CORE = _common.GATES_LINE.pattern[1:-1]
RAW_GATES = re.compile(r"(?:^|[\n\"'])" + _CORE + r"(?:$|[\n\"'])")


def body_args(args):
    """(bodies, files, seen) from the options of one gh pr command."""
    bodies, files, seen = [], [], False
    i = 0
    while i < len(args):
        a = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None
        if a in ("--body", "-b") and nxt is not None:
            bodies.append(nxt)
            seen = True
            i += 1
        elif a in ("--body-file", "-F") and nxt is not None:
            files.append(nxt)
            seen = True
            i += 1
        elif a.startswith("--body="):
            bodies.append(a[7:])
            seen = True
        elif a.startswith("--body-file="):
            files.append(a[12:])
            seen = True
        elif re.match(r"^-b.", a):
            bodies.append(a[2:])
            seen = True
        elif re.match(r"^-F.", a):
            files.append(a[2:])
            seen = True
        i += 1
    return bodies, files, seen


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("warn_pr_gates: no usable hook input; skipping.\n")
        sys.exit(0)
    ti = event.get("tool_input")
    command = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(command, str):
        sys.exit(0)
    try:
        for cmd in _common.shell_commands(command):
            _, verb, args = _common.unwrap(cmd)
            if verb != "gh" or len(args) < 2 or args[0] != "pr" or args[1] not in ("create", "edit"):
                continue
            bodies, files, seen = body_args(args[2:])
            if not seen and args[1] == "edit":
                continue  # an edit that leaves the body alone says nothing about it
            if "--web" in args or "-w" in args:
                continue  # the body is written in the browser
            texts = list(bodies)
            unreadable = False
            for f in files:
                if f == "-":
                    unreadable = True
                    continue
                path = _common.resolve_path(event, f)
                if os.path.isfile(path):
                    texts.append(_common.read_text(path, limit=BODY_LIMIT))
                else:
                    unreadable = True
            if unreadable:
                continue  # cannot judge a body that cannot be read
            # The raw command also counts: a heredoc body is not split into one token.
            if any(has_gates(t) for t in texts) or RAW_GATES.search(command.replace("\r\n", "\n")):
                continue
            _common.warn("PreToolUse", MESSAGE)
    except Exception as exc:  # a warn hook never blocks
        sys.stderr.write("warn_pr_gates: skipped (%s).\n" % exc)
    sys.exit(0)


if __name__ == "__main__":
    main()
