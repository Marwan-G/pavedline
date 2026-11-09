#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit|MultiEdit): warn once per folder per session when a file is edited under
a folder that has an ARCHITECTURE.dot and that diagram is unchanged in `git status`. Never blocks."""
import hashlib
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

DOT = "ARCHITECTURE.dot"
DIAGRAM_FILES = {DOT, "ARCHITECTURE.svg"}


def find_dot_folder(file_path):
    """(folder, repo_root): the nearest folder holding ARCHITECTURE.dot, walking up to the repo root."""
    d = os.path.dirname(os.path.abspath(file_path))
    folder = None
    while True:
        if folder is None and os.path.isfile(os.path.join(d, DOT)):
            folder = d
        if os.path.exists(os.path.join(d, ".git")):
            return folder, d
        parent = os.path.dirname(d)
        if parent == d:
            return None, None
        d = parent


def dot_changed(root, dot):
    out = subprocess.run(["git", "status", "--porcelain", "--", dot], cwd=root, capture_output=True,
                         text=True, timeout=10)
    if out.returncode != 0:
        return None
    return bool(out.stdout.strip())


def already_warned(session, folder):
    base = os.path.join(tempfile.gettempdir(), "pavedline-dot-drift")
    os.makedirs(base, exist_ok=True)
    key = hashlib.sha256(("%s\0%s" % (session, folder)).encode()).hexdigest()[:24]
    marker = os.path.join(base, key)
    if os.path.exists(marker):
        return True
    open(marker, "w").close()
    return False


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("warn_dot_drift: no usable hook input; skipping.\n")
        sys.exit(0)
    ti = event.get("tool_input")
    fp = ti.get("file_path") if isinstance(ti, dict) else None
    if not isinstance(fp, str) or not fp:
        sys.exit(0)
    try:
        path = _common.resolve_path(event, fp)
        if os.path.basename(path) in DIAGRAM_FILES:
            sys.exit(0)
        folder, root = find_dot_folder(path)
        if folder is None:
            sys.exit(0)
        if dot_changed(root, os.path.join(folder, DOT)) is not False:
            sys.exit(0)  # changed already, or git cannot say
        session = event.get("session_id") if isinstance(event.get("session_id"), str) else "nosession"
        if already_warned(session, folder):
            sys.exit(0)
        rel = os.path.relpath(os.path.join(folder, DOT), root)
        _common.warn("PostToolUse",
                     "%s was edited, and %s is unchanged. If the change moves a boundary, a service or a "
                     "data flow, update the diagram; otherwise say `diagram unchanged: <reason>` in the "
                     "pull request." % (os.path.relpath(path, root), rel))
    except Exception as exc:  # a warn hook never blocks
        sys.stderr.write("warn_dot_drift: skipped (%s).\n" % exc)
    sys.exit(0)


if __name__ == "__main__":
    main()
