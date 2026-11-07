#!/usr/bin/env python3
"""Copy the Pavedline product-repo templates into a target directory.

Usage: start_project.py --target DIR --name NAME --mode solo|team [--dry-run]

Never overwrites: if any destination file already exists, nothing is written,
each clash is printed as "conflict: <path>", and the exit code is 1.
Standard library only.
"""
import argparse
import datetime
import hashlib
import re
import pathlib
import sys

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"


def substitute(data: bytes, values: dict) -> bytes:
    if b"\0" in data:
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    return text.encode("utf-8")


HASH_RE = re.compile(rb"<!-- dot-source-sha256: [0-9a-f]{64} -->")


def refresh_svg_hash(dot: pathlib.Path) -> None:
    """Point a copied X.svg's source-hash comment at the substituted X.dot."""
    svg = dot.with_suffix(".svg")
    if not svg.is_file():
        return
    marker = b"<!-- dot-source-sha256: " + hashlib.sha256(dot.read_bytes()).hexdigest().encode() + b" -->"
    svg.write_bytes(HASH_RE.sub(lambda _m: marker, svg.read_bytes()))


def is_conflict(target: pathlib.Path, rel: pathlib.Path) -> bool:
    dest = target / rel
    if dest.exists() or dest.is_symlink():
        return True
    return any((target / a).exists() and not (target / a).is_dir() for a in rel.parents if a != pathlib.Path("."))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--mode", required=True, choices=["solo", "team"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    target = pathlib.Path(args.target)
    if not target.is_dir():
        print("error: target directory does not exist: " + args.target, file=sys.stderr)
        return 1

    files = sorted(p for p in TEMPLATES.rglob("*") if p.is_file())
    rels = [p.relative_to(TEMPLATES) for p in files]
    conflicts = [r for r in rels if is_conflict(target, r)]
    if conflicts:
        for r in conflicts:
            print("conflict: " + r.as_posix())
        print("nothing written: existing files are never overwritten", file=sys.stderr)
        return 1

    values = {"PROJECT_NAME": args.name, "MODE": args.mode, "DATE": datetime.date.today().isoformat()}
    for src, rel in zip(files, rels):
        if args.dry_run:
            print("would create: " + rel.as_posix())
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(substitute(src.read_bytes(), values))
        print("created: " + rel.as_posix())
    if not args.dry_run:
        for rel in rels:
            if rel.suffix == ".dot":
                refresh_svg_hash(target / rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
