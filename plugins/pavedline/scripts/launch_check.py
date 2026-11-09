#!/usr/bin/env python3
"""Launch gate (step 12): every item of docs/production/LAUNCH.md ticked or carrying a recorded exception.

    python3 launch_check.py [--repo DIR] [--file PATH]

Reads every `- [ ]` / `- [x]` line. An item passes when ticked, or when it carries `exception: decisions/NNNN` and
that ADR file exists in the repository and is not superseded. Exit 0 only when all items pass; exit 1 lists each open
item (including items a product added later); exit 2 when LAUNCH.md is missing or has no items. Standard library only.
"""
import argparse
import pathlib
import re
import sys

ITEM_RE = re.compile(r"^[-] \[([ xX])\] (\S.*?)\s*$")
LOOKS_LIKE_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s*\[.?\]")
EXC_RE = re.compile(r"\bexception: (decisions/\d{4}-[\w.\-]+?\.md)$")
STATUS_RES = (
    re.compile(r"^\s*[-*]?\s*\*{0,2}Status:?\*{0,2}:?\s*(.+?)\s*$", re.I | re.M),
    re.compile(r"^#+\s*Status\s*\n+\s*(\S.*?)\s*$", re.I | re.M),
)


def adr_problem(repo, ref):
    path = repo / ref
    if not path.is_file():
        return "exception names %s, which does not exist" % ref
    text = path.read_text(errors="replace")
    if not text.strip():
        return "exception names %s, which is empty" % ref
    values = [m.group(1).strip().strip("*_ ").lower() for r in STATUS_RES for m in r.finditer(text)]
    if not values:
        return "exception names %s, which has no Status" % ref
    if any(v.startswith("superseded") for v in values):
        return "exception names %s, which is superseded" % ref
    if values[0] != "accepted":
        return "exception names %s, whose Status is %r, not accepted" % (ref, values[0])
    return None


FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def scan(text):
    """Split the file into (visible lines by number, errors). Nothing can be hidden: an item inside a fenced block
    or an HTML comment is an error, and so is a fence or comment that never closes (CommonMark fences: opened by 3+
    backticks or tildes with at most 3 spaces of indent, closed only by the same character, at least as long)."""
    visible, errors = [], []
    fence = None  # (char, length, line)
    comment = None  # line where an unclosed <!-- started
    for n, line in enumerate(text.splitlines(), 1):
        if fence:
            c, ln, _ = fence
            if re.match(r"^ {0,3}%s{%d,}\s*$" % (re.escape(c), ln), line):
                fence = None
            elif LOOKS_LIKE_ITEM_RE.match(line):
                errors.append("line %d: checklist item inside a code block or comment: move it out: %s" % (n, line.strip()))
            continue
        if comment:
            if LOOKS_LIKE_ITEM_RE.match(line):
                errors.append("line %d: checklist item inside a code block or comment: move it out: %s" % (n, line.strip()))
            if "-->" in line:
                comment = None
            continue
        m = FENCE_OPEN_RE.match(line)
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = (m.group(1)[0], len(m.group(1)), n)
            continue
        if "<!--" in line:
            before, _, after = line.partition("<!--")
            closed = "-->" in after
            if not before.strip() and LOOKS_LIKE_ITEM_RE.match(after.lstrip()):
                errors.append("line %d: checklist item inside a code block or comment: move it out: %s" % (n, line.strip()))
                if not closed:
                    comment = n
                continue
            if not closed:
                comment = n
                if not before.strip():
                    continue
            line = before if not before.strip() or not closed else line
        visible.append((n, line))
    if fence:
        errors.append("line %d: unclosed code fence" % fence[2])
    if comment:
        errors.append("line %d: unclosed HTML comment" % comment)
    return visible, errors


def check(repo, launch):
    if not launch.is_file():
        print("error: %s not found" % launch)
        return 2
    items, open_items = [], []
    visible, malformed = scan(launch.read_text())
    for n, line in visible:
        m = ITEM_RE.match(line)
        if m:
            items.append((n, m))
        elif LOOKS_LIKE_ITEM_RE.match(line):
            malformed.append("line %d: not a checklist item (use `- [ ] text` or `- [x] text`): %s" % (n, line.strip()))
    if not items and not malformed:
        print("error: %s has no checklist items" % launch)
        return 2
    for n, m in items:
        text = m.group(2)
        if m.group(1) in "xX":
            continue
        exc = EXC_RE.search(text)
        if not exc:
            open_items.append("line %d: %s" % (n, text))
            continue
        why = adr_problem(repo, exc.group(1))
        if why:
            open_items.append("line %d: %s (%s)" % (n, text, why))
    problems = sorted(malformed, key=lambda s: int(s.split(":")[0].split()[1])) + open_items
    if problems:
        print("launch NOT ready: %d problem(s) in %d item(s)" % (len(problems), len(items)))
        for i in problems:
            print("  - " + i)
        return 1
    print("launch ready: all %d items ticked or excepted" % len(items))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--file", help="default: <repo>/docs/production/LAUNCH.md")
    a = ap.parse_args(argv)
    repo = pathlib.Path(a.repo)
    return check(repo, pathlib.Path(a.file) if a.file else repo / "docs/production/LAUNCH.md")


if __name__ == "__main__":
    sys.exit(main())
