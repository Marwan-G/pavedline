#!/usr/bin/env python3
"""SessionStart hook: print the project state as plain facts."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

MAX_CHARS = 4000


def clip(text):
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS].rstrip() + "\n… (truncated)"


def first_paragraph(text):
    lines = text.replace("\r\n", "\n").split("\n")
    para, started = [], False
    for line in lines:
        if line.lstrip().startswith("#") and not started:
            continue
        if not line.strip():
            if started:
                break
            continue
        started = True
        para.append(line)
    return "\n".join(para)


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("session_start: no usable hook input; using the working directory.\n")
        event = {}
    base = _common.event_cwd(event)
    state_path = os.path.join(base, "STATE.md")
    if not os.path.isfile(state_path):
        print("No Pavedline project in this directory. /pavedline:start creates one.")
        sys.exit(0)
    product = first_paragraph(_common.read_text(os.path.join(base, "PRODUCT.md"))) or "(PRODUCT.md is empty)"
    state = _common.read_text(state_path).rstrip("\n")
    waiting = [l for l in _common.read_text(os.path.join(base, "WAITING.md")).split("\n") if l.startswith("- F")]
    out = [
        "Pavedline project state",
        "Product: " + clip(product),
        "--- STATE.md ---",
        clip(state),
        "--- WAITING.md (open items) ---",
        clip("\n".join(waiting)) if waiting else "(none)",
    ]
    print("\n".join(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
