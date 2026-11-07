#!/usr/bin/env python3
"""Write each agent's `model:` frontmatter line from plugins/pavedline/config/models.yaml.

Usage: gen_agent_models.py [--check] [--models FILE] [--agents-dir DIR]
--check exits 1 listing drifted files and changes nothing.
"""
import argparse
import pathlib
import re
import sys
from typing import Dict, List, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "pavedline"
ALLOWED = {"opus", "sonnet"}
ROLE_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def parse_models(text: str) -> Dict[str, str]:
    models: Dict[str, str] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        role, sep, value = line.partition(":")
        role, value = role.strip(), value.split("#", 1)[0].strip()
        if not sep or not ROLE_RE.match(role):
            raise ValueError(f"line {n}: expected 'role: model'")
        if value not in ALLOWED:
            raise ValueError(f"line {n}: model {value!r} for {role} not in {sorted(ALLOWED)}")
        if role in models:
            raise ValueError(f"line {n}: duplicate role: {role}")
        models[role] = value
    return models


def set_model(text: str, model: str) -> Optional[str]:
    """Return text with the frontmatter model line set, or None if there is no frontmatter."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            end = i
            break
    else:
        return None
    nl = "\r\n" if lines[0].endswith("\r\n") else "\n"
    new = f"model: {model}{nl}"
    for i in range(1, end):
        if re.match(r"model\s*:", lines[i]):
            lines[i] = new
            break
    else:
        lines.insert(end, new)
    return "".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--models", default=str(PLUGIN / "config" / "models.yaml"))
    ap.add_argument("--agents-dir", default=str(PLUGIN / "agents"))
    args = ap.parse_args(argv)
    try:
        models = parse_models(pathlib.Path(args.models).read_text())
    except (OSError, ValueError) as e:
        print(f"{args.models}: {e}", file=sys.stderr)
        return 1
    drifted: List[str] = []
    agents_dir = pathlib.Path(args.agents_dir)
    missing = [p.stem for p in sorted(agents_dir.glob("*.md")) if p.stem not in models]
    if missing:
        for name in missing:
            print(f"no model policy for agent {name}", file=sys.stderr)
        return 1
    for role, model in sorted(models.items()):
        path = agents_dir / f"{role}.md"
        if not path.is_file():
            continue
        old = path.read_bytes().decode("utf-8")
        new = set_model(old, model)
        if new is None:
            print(f"{path}: no frontmatter", file=sys.stderr)
            return 1
        if new != old:
            drifted.append(str(path))
            if not args.check:
                path.write_bytes(new.encode("utf-8"))
    if args.check and drifted:
        for p in drifted:
            print(f"{p}: model line drifted from models.yaml", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
