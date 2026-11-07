#!/usr/bin/env python3
"""Lint skills: usage lint_skills.py <skills_dir>. Prints `path: problem` lines, exits 1 on any."""
import pathlib
import re
import sys
from typing import Dict, List, Optional

MAX_LINES = 500
MAX_DESC = 1024
LINK_RE = re.compile(r"\]\((references/[^)#\s]+)")


def parse_frontmatter(text: str) -> Optional[Dict[str, str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm: Dict[str, str] = {}
    key = None
    block: Optional[str] = None
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key, val = m.group(1), m.group(2).strip()
            if val in (">", "|", ">-", "|-"):
                block, fm[key] = val[0], ""
            else:
                block, fm[key] = None, val.strip("\"'")
        elif key and block is not None and line.strip():
            sep = " " if block == ">" else "\n"
            fm[key] = (fm[key] + sep + line.strip()).strip()
    return None


def check_skills(skills_dir) -> List[str]:
    problems: List[str] = []
    root = pathlib.Path(skills_dir)
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if not md.is_file():
            problems.append(f"{d}: missing SKILL.md")
            continue
        text = md.read_text()
        fm = parse_frontmatter(text)
        if fm is None:
            problems.append(f"{md}: missing or unterminated frontmatter")
            continue
        if fm.get("name") != d.name:
            problems.append(f"{md}: name {fm.get('name')!r} does not equal directory {d.name!r}")
        desc = fm.get("description", "")
        if not desc:
            problems.append(f"{md}: description is empty")
        elif len(desc) > MAX_DESC:
            problems.append(f"{md}: description is {len(desc)} characters (max {MAX_DESC})")
        n = len(text.splitlines())
        if n > MAX_LINES:
            problems.append(f"{md}: {n} lines (max {MAX_LINES})")
        for link in sorted(set(LINK_RE.findall(text))):
            if not (d / link).exists():
                problems.append(f"{md}: broken link {link}")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: lint_skills.py <skills_dir>", file=sys.stderr)
        return 2
    if not pathlib.Path(argv[0]).is_dir():
        print(f"{argv[0]}: skills directory not found")
        return 1
    problems = check_skills(argv[0])
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
