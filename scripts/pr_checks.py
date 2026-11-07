#!/usr/bin/env python3
"""Fail unless a PR body carries the gates line (design section 9.1)."""
import argparse
import re
import sys

GATES = re.compile(
    r"^Gates: TDD ✓ · review ✓ \(\d+ found, \d+ fixed\) · security ✓ · "
    r"adversarial (✓|n/a) · verification ✓$",
    re.MULTILINE,
)


def has_gates_line(body: str) -> bool:
    return GATES.search(body.replace("\r\n", "\n")) is not None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--body-file", required=True)
    args = ap.parse_args(argv)
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
