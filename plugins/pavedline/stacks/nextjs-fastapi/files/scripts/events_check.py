#!/usr/bin/env python3
"""Keep docs/observability/EVENTS.md true: every event the API emits has a row there.

    uv run --project services/api python scripts/events_check.py [--root DIR]

Run it with the API's Python: it parses the API code, which may use syntax an older system python3 rejects.

Finds every `log_event(<logger>, <level>, "<name>"` in services/api/app (also under an import alias, such as
`from app.events import log_event as emit`, or as `events.log_event`) and compares the names with the first
column of the Events table (rows inside a fenced code block do not count). Exit 1 on an emitted event with no
row, a duplicate row, or a name that is not `area.what_happened`; a row the code never emits is a warning only
(it may be planned for a later slice).
"""

import argparse
import ast
import pathlib
import re
import sys

NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
ROW = re.compile(r"^\|\s*`([^`]*)`\s*\|")


class CheckError(Exception):
    """A problem that stops the check (exit 1 with one clear line)."""


def emitted(app_dir: pathlib.Path) -> dict[str, list[str]]:
    """Event name -> the places that emit it. Only literal names count; a computed name is reported."""
    found: dict[str, list[str]] = {}
    definition = (app_dir / "events.py").resolve()
    for path in sorted(app_dir.rglob("*.py")):
        if path.resolve() == definition:
            continue  # the module that defines log_event
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise CheckError(
                f"cannot parse {path}:{exc.lineno} with Python {sys.version.split()[0]}; "
                "run this check with the API's Python (uv run --project services/api python ...)"
            ) from exc
        names = {"log_event"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(a.asname for a in node.names if a.name == "log_event" and a.asname)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if name not in names:
                continue
            where = f"{path}:{node.lineno}"
            arg = node.args[2] if len(node.args) >= 3 else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.setdefault(arg.value, []).append(where)
            else:
                found.setdefault("<not a literal string>", []).append(where)
    return found


def registered(events_md: pathlib.Path) -> list[str]:
    """The names in the first column of the table under `## Events`."""
    names: list[str] = []
    in_events = in_fence = False
    for line in events_md.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            in_events = line.strip() == "## Events"
            continue
        m = ROW.match(line)
        if in_events and m:
            names.append(m.group(1))
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--root", default=".", help="the product repository (default: the current directory)")
    args = ap.parse_args(argv)
    root = pathlib.Path(args.root)
    events_md = root / "docs" / "observability" / "EVENTS.md"
    app_dir = root / "services" / "api" / "app"
    if not events_md.is_file():
        print(f"error: {events_md} is missing", file=sys.stderr)
        return 1
    if not app_dir.is_dir():
        print(f"error: {app_dir} is missing", file=sys.stderr)
        return 1
    rows = registered(events_md)
    try:
        code = emitted(app_dir)
    except CheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    problems: list[str] = []
    for name in sorted({n for n in rows if rows.count(n) > 1}):
        problems.append(f"duplicate row in EVENTS.md: {name}")
    for name in rows:
        if not NAME.match(name):
            problems.append(f"bad name in EVENTS.md (use area.what_happened): {name}")
    for name, places in sorted(code.items()):
        if name == "<not a literal string>":
            problems.extend(f"event name is not a literal string: {p}" for p in places)
        elif not NAME.match(name):
            problems.extend(f"bad event name {name!r} (use area.what_happened): {p}" for p in places)
        elif name not in rows:
            problems.extend(f"event {name!r} has no row in EVENTS.md: {p}" for p in places)
    for name in sorted(set(rows) - set(code)):
        print(f"warning: EVENTS.md lists {name!r}, which the code does not emit")
    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"events check: {len(code)} emitted, {len(set(rows))} registered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
