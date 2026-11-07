#!/usr/bin/env python3
"""PostToolUse hook: tell Claude when CLAUDE.md grows past 150 lines (never blocks)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

LIMIT = 150


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("warn_claude_md: no usable hook input; skipping.\n")
        sys.exit(0)
    ti = event.get("tool_input")
    if not isinstance(ti, dict) or not isinstance(ti.get("file_path"), str):
        sys.exit(0)
    if os.path.basename(ti["file_path"].replace("\\", "/")) != "CLAUDE.md":
        sys.exit(0)
    n = _common.count_lines(_common.read_text(_common.resolve_path(event, ti["file_path"])))
    if n > LIMIT:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "CLAUDE.md is %d lines (target ≤ %d). Move detail into skills or docs "
                                 "and keep CLAUDE.md to the essentials." % (n, LIMIT)}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
