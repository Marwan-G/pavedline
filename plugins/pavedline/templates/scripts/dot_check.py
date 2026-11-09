#!/usr/bin/env python3
"""Validate and render every tracked Graphviz .dot; --check verifies committed SVGs are current.

Each rendered SVG records the sha256 of its .dot source in a comment, so staleness is
detected without comparing SVG bytes (which differ between Graphviz versions).
"""
import hashlib
import pathlib
import re
import subprocess
import sys
from typing import List, Tuple

HASH_RE = re.compile(r"<!-- dot-source-sha256: ([0-9a-f]{64}) -->")


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def validate(dot_file) -> Tuple[bool, str]:
    try:
        r = subprocess.run(["dot", "-Tcanon", "-o", "/dev/null", str(dot_file)],
                           capture_output=True, text=True)
    except FileNotFoundError:
        return False, "graphviz 'dot' not found"
    return r.returncode == 0, r.stderr.strip()


def render(dot_file) -> pathlib.Path:
    dot_file = pathlib.Path(dot_file)
    svg = dot_file.with_suffix(".svg")
    r = subprocess.run(["dot", "-Tsvg", str(dot_file)], capture_output=True, text=True, check=True)
    lines = r.stdout.splitlines()
    marker = f"<!-- dot-source-sha256: {sha256_of(dot_file)} -->"
    lines.insert(1 if lines and lines[0].startswith("<?xml") else 0, marker)
    svg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return svg


def tracked_dots(root=".") -> List[pathlib.Path]:
    out = subprocess.run(["git", "ls-files", "*.dot"], cwd=root, capture_output=True,
                         text=True, check=True).stdout.split()
    return [pathlib.Path(root) / p for p in out]


def check(dots) -> List[str]:
    problems = []
    for dot in map(pathlib.Path, dots):
        ok, err = validate(dot)
        if not ok:
            problems.append(f"{dot}: invalid: {err}")
            continue
        svg = dot.with_suffix(".svg")
        if not svg.is_file():
            problems.append(f"{dot}: missing {svg.name}")
            continue
        m = HASH_RE.search(svg.read_text(encoding="utf-8", errors="replace"))
        if not m or m.group(1) != sha256_of(dot):
            problems.append(f"{dot}: {svg.name} is stale (re-run scripts/dot_check.py)")
    return problems


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dots = tracked_dots()
    if "--check" in argv:
        problems = check(dots)
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    rc = 0
    for dot in dots:
        ok, err = validate(dot)
        if not ok:
            print(f"{dot}: invalid: {err}", file=sys.stderr)
            rc = 1
            continue
        print(f"rendered {render(dot)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
