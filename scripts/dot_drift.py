#!/usr/bin/env python3
"""Flag changed code whose owning ARCHITECTURE.dot was not updated in the same change."""
import argparse
import pathlib
import subprocess
import sys
from typing import List

OPT_OUT = "diagram unchanged:"


def _owner(path: str, dot_owners: List[str]):
    best = None
    for o in dot_owners:
        o = "" if o in (".", "") else o.rstrip("/")
        if o == "" or path == o or path.startswith(o + "/"):
            if best is None or len(o) > len(best):
                best = o
    return best


def _dot_of(owner: str) -> str:
    return "ARCHITECTURE.dot" if owner == "" else f"{owner}/ARCHITECTURE.dot"


def drift(changed: List[str], dot_owners: List[str], pr_body: str) -> List[str]:
    if OPT_OUT in pr_body:
        return []
    touched = {}
    for path in changed:
        if path.endswith("ARCHITECTURE.dot"):
            continue
        owner = _owner(path, dot_owners)
        if owner is not None:
            touched[owner] = True
    changed_set = set(changed)
    out = [o for o in touched if _dot_of(o) not in changed_set]
    return sorted("." if o == "" else o for o in out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--pr-body-file")
    a = ap.parse_args(argv)
    changed = subprocess.run(["git", "diff", "--name-only", f"{a.base}...HEAD"],
                             capture_output=True, text=True, check=True).stdout.split()
    tracked = subprocess.run(["git", "ls-files", "*ARCHITECTURE.dot"],
                             capture_output=True, text=True, check=True).stdout.split()
    owners = [str(pathlib.PurePosixPath(p).parent) for p in tracked]
    body = pathlib.Path(a.pr_body_file).read_text(encoding="utf-8") if a.pr_body_file else ""
    stale = drift(changed, owners, body)
    for o in stale:
        print(f"{o}: code changed but {_dot_of('' if o == '.' else o)} did not "
              f"(update it, or add '{OPT_OUT} <reason>' to the PR body)", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
