#!/usr/bin/env bash
# Run Pavedline's plugin eval suites (plugins/pavedline/evals) with `claude plugin eval`.
#
#   scripts/run_evals.sh [--max-cost-usd N] [extra claude plugin eval flags...]
#
# Each eval run loads ONLY the plugin under test (https://code.claude.com/docs/en/plugin-evals.md, "Nothing personal or
# project-level loads", read 2026-11-09). Claude Code does not load a plugin whose declared dependencies are missing, so
# the eval runs against a temporary copy of plugins/pavedline whose plugin.json has no `dependencies`. The cases test
# Pavedline's own skills, which need none of them. Every run is a real model call on your account: the default cost cap
# is $5 and one run per case, with no no-plugin baseline arm (--ablation none).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAX_COST=5
EXTRA=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --max-cost-usd) [ "$#" -ge 2 ] || { echo "usage: run_evals.sh [--max-cost-usd N] [flags...]" >&2; exit 2; }; MAX_COST="$2"; shift 2 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

COPY_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/pavedline-evals.XXXXXX")"
trap 'rm -rf "$COPY_PARENT"' EXIT
COPY="$COPY_PARENT/pavedline"
cp -R "$ROOT/plugins/pavedline" "$COPY"
rm -rf "$COPY/evals/results"
python3 "$ROOT/scripts/strip_plugin_dependencies.py" "$COPY/.claude-plugin/plugin.json"

OUT="$ROOT/plugins/pavedline/evals/results"
mkdir -p "$OUT"
claude plugin eval "$COPY" --trust-plugin --scaffold --allow-tools Bash Write Edit \
  --runs 1 --ablation none --max-cost-usd "$MAX_COST" --no-publish \
  --output-dir "$OUT" ${EXTRA[@]+"${EXTRA[@]}"}
