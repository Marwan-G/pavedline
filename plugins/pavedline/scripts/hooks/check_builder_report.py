#!/usr/bin/env python3
"""SubagentStop hook (matcher pavedline:builder): warn when a builder's last message lacks the report shape (a
`Status: DONE|BLOCKED` line, and for DONE the `Gates:` line). It never blocks: a builder may deliver its report
through a hand-back this hook cannot see, so blocking could stop a correct builder. An empty or missing message
(nothing to judge) and malformed input are silent (fail open)."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

AGENTS = {"pavedline:builder"}
STATUS = re.compile(r"^\s*Status:\s*(DONE|BLOCKED)\b", re.MULTILINE)
GATES = re.compile(r"^\s*Gates:\s*TDD\b", re.MULTILINE)


def missing(message):
    m = STATUS.search(message or "")
    if not m:
        return "a `Status: DONE` or `Status: BLOCKED — <what is left>` line"
    if m.group(1) == "DONE" and not GATES.search(message):
        return "the `Gates: TDD ✓ · review pending · ...` line that a DONE report carries"
    return None


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("check_builder_report: no usable hook input; skipping.\n")
        sys.exit(0)
    if event.get("stop_hook_active") is True or event.get("agent_type") not in AGENTS:
        sys.exit(0)
    msg = event.get("last_assistant_message")
    if not isinstance(msg, str) or not msg.strip():
        sys.exit(0)
    try:
        gap = missing(msg)
    except Exception as exc:  # fail open
        sys.stderr.write("check_builder_report: skipped (%s).\n" % exc)
        sys.exit(0)
    if gap:
        print(json.dumps({"systemMessage": "Pavedline: the builder's last message is missing %s "
                                           "(agents/builder.md rules 1, 10 and 11). Check its report before "
                                           "trusting it." % gap}))
    sys.exit(0)


if __name__ == "__main__":
    main()
