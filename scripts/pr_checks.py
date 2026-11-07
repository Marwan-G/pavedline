#!/usr/bin/env python3
"""Fail unless a PR body carries the gates line (design section 9.1)."""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dot_drift  # noqa: E402  (shared glob matcher)

GATES = re.compile(
    r"^Gates: TDD ✓ · review ✓ \(\d+ found, \d+ fixed\) · security ✓ · "
    r"adversarial (✓|n/a) · verification ✓$",
    re.MULTILINE,
)


def has_gates_line(body: str) -> bool:
    return GATES.search(body.replace("\r\n", "\n")) is not None


DEPENDENCY_FILES = pathlib.Path(__file__).resolve().parent / "dependency-files.txt"


def is_dependency_update(head_ref: str, changed: list, globs: list) -> bool:
    """Renovate branch AND every changed file is a dependency file (a branch name alone proves nothing)."""
    if not head_ref.startswith("renovate/") or not changed:
        return False
    return all(dot_drift.matches_any(c, globs) for c in changed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--head-ref", default="")
    ap.add_argument("--changed-files-file")
    ap.add_argument("--dependency-globs-file", default=str(DEPENDENCY_FILES))
    args = ap.parse_args(argv)
    if args.head_ref and args.changed_files_file:
        try:
            changed = pathlib.Path(args.changed_files_file).read_text(encoding="utf-8").split()
            globs = dot_drift.parse_globs(pathlib.Path(args.dependency_globs_file).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"pr_checks: cannot read input: {exc}", file=sys.stderr)
            return 1
        if is_dependency_update(args.head_ref, changed, globs):
            return 0
    try:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read()
    except OSError as exc:
        print(f"pr_checks: cannot read body file: {exc}", file=sys.stderr)
        return 1
    if has_gates_line(body):
        return 0
    print("pr_checks: the PR body needs a line exactly like:\n"
          "Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
