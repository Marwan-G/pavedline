#!/usr/bin/env python3
"""PreToolUse guard: STATE.md may never grow past 60 lines."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

CAP = 60


def _apply(text, old, new, replace_all):
    if not isinstance(old, str) or not isinstance(new, str) or old == "" or old not in text:
        return text
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("guard_state_size: no usable hook input; allowing.\n")
        _common.allow()
    ti = event.get("tool_input")
    if not isinstance(ti, dict) or not isinstance(ti.get("file_path"), str):
        _common.allow()
    if os.path.basename(ti["file_path"].replace("\\", "/")) != "STATE.md":
        _common.allow()
    tool = event.get("tool_name")
    current = _common.read_text(_common.resolve_path(event, ti["file_path"]))
    if tool == "Write":
        content = ti.get("content")
        if not isinstance(content, str):
            _common.allow()
        result = content
    elif tool == "Edit":
        result = _apply(current, ti.get("old_string"), ti.get("new_string"), ti.get("replace_all") is True)
    elif tool == "MultiEdit":
        edits = ti.get("edits")
        if not isinstance(edits, list):
            _common.allow()
        result = current
        for e in edits:
            if isinstance(e, dict):
                result = _apply(result, e.get("old_string"), e.get("new_string"), e.get("replace_all") is True)
    else:
        _common.allow()
    n = _common.count_lines(result)
    if n > CAP:
        _common.block("STATE.md would be %d lines (cap %d). Move closed items to docs/archive/state-YYYY-MM.md first." % (n, CAP))
    _common.allow()


if __name__ == "__main__":
    main()
