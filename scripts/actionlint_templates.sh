#!/usr/bin/env bash
# Run actionlint over both CI template trees. actionlint resolves a local reusable workflow (./.github/workflows/x.yml)
# from the git repository root, so each tree is copied into a throwaway git repository first, as a product has it.
# usage: scripts/actionlint_templates.sh [path-to-actionlint]   (default: actionlint on PATH)
set -euo pipefail
LINT="${1:-actionlint}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
rc=0
for tree in plugins/pavedline/templates plugins/pavedline/stacks/nextjs-fastapi/files; do
  dest="$TMP/$(basename "$(dirname "$tree")")-$(basename "$tree")"
  mkdir -p "$dest"
  cp -R "$ROOT/$tree/.github" "$dest/.github"
  git -C "$dest" init -q
  echo "== actionlint $tree"
  (cd "$dest" && "$LINT" -no-color .github/workflows/*.yml) || rc=1
done
exit "$rc"
