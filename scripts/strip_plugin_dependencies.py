#!/usr/bin/env python3
"""Remove `dependencies` from a COPY of a plugin manifest (used by run_evals.sh: an eval run loads only the plugin
under test, and Claude Code does not load a plugin whose declared dependencies are missing). Refuses the real manifest
under plugins/ so the shipped plugin.json is never changed."""
import json
import pathlib
import sys


def strip(path):
    p = pathlib.Path(path).resolve()
    repo_plugins = (pathlib.Path(__file__).resolve().parent.parent / "plugins").resolve()
    if repo_plugins in p.parents:
        raise SystemExit("refusing to edit the shipped manifest: %s" % p)
    data = json.loads(p.read_text())
    data.pop("dependencies", None)
    p.write_text(json.dumps(data, indent=2) + "\n")
    return data


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: strip_plugin_dependencies.py <copied plugin.json>")
    strip(sys.argv[1])
