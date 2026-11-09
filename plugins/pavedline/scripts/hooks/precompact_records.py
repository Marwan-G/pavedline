#!/usr/bin/env python3
"""PreCompact hook: tell the compaction summary which record facts to keep. Never blocks; fails open."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

MAX_CHARS = 9000
KEEP = ("STEP", "WAVE", "NEXT", "LEFT BEHIND", "STALE")
LINE_CAP = 600


def build(base):
    state = os.path.join(base, "STATE.md")
    if not os.path.isfile(state):
        return ""
    found = {}
    for line in _common.read_text(state, 200000).splitlines():
        for key in KEEP:
            if line.startswith(key + ":") and key not in found:
                found[key] = line[:LINE_CAP]
    waiting = [l.split(" ")[1] if len(l.split(" ")) > 1 else l
               for l in _common.read_text(os.path.join(base, "WAITING.md"), 200000).splitlines()
               if l.startswith("- F")]
    dirty = _common.uncommitted_records(base)
    out = ["Keep these Pavedline record facts verbatim in the compaction summary:"]
    out.extend(found[k] for k in KEEP if k in found)
    out.append("WAITING.md: %d open%s" % (len(waiting), (" (" + ", ".join(waiting[:50]) + ")") if waiting else ""))
    out.append("Uncommitted record files: " + (", ".join(dirty[:50]) if dirty else "none"))
    out.append("After compaction, re-read STATE.md before acting.")
    text = "\n".join(out)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS].rstrip() + "\n… (truncated)"


def main():
    try:
        event = _common.read_event()
        if event is None:
            sys.exit(0)
        text = build(_common.project_dir(event))
        if text:
            print(text)
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
