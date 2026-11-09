#!/usr/bin/env python3
"""Deny-list scan: keeps private identifiers and secrets out of the public repo."""
import pathlib
import re
import subprocess
import sys
from typing import List, NamedTuple

DENYLISTS = (".sanitize-denylist", ".sanitize-denylist.local")


class Finding(NamedTuple):
    path: str
    line: int
    pattern: str


def load_patterns(repo_root) -> List["re.Pattern"]:
    root = pathlib.Path(repo_root)
    patterns = []
    for name in DENYLISTS:
        p = root / name
        if not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                patterns.append(re.compile(line))
    return patterns


def scan(paths, patterns) -> List[Finding]:
    findings = []
    for path in paths:
        path = pathlib.Path(path)
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    findings.append(Finding(str(path), n, pat.pattern))
    return findings


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8")
    names = sorted({n for n in out.split("\0") if n and n not in DENYLISTS and (root / n).is_file()})
    findings = scan([root / n for n in names], load_patterns(root))
    for f in findings:
        print(f"{pathlib.Path(f.path).relative_to(root)}:{f.line}: {f.pattern}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
