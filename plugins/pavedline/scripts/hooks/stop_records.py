#!/usr/bin/env python3
"""Stop hook: remind Claude to commit uncommitted record files. Never blocks; fails open."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402


def main():
    try:
        event = _common.read_event()
        if event is None or event.get("stop_hook_active"):
            sys.exit(0)
        base = _common.project_dir(event)
        if not os.path.isfile(os.path.join(base, "STATE.md")):
            sys.exit(0)
        files = _common.uncommitted_records(base)
        if not files:
            sys.exit(0)
        msg = ("Records not committed: %s. Commit them (the state skill: after every state change) "
               "or say why not." % ", ".join(files[:20]))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
