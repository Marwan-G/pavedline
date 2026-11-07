#!/usr/bin/env bash
# Clean-profile install test: installs pavedline into a throwaway Claude Code config dir.
# Isolation: CLAUDE_CONFIG_DIR (documented: "Override the configuration directory
# (default: ~/.claude). All settings, session history, and plugins are stored under this path.")
# https://code.claude.com/docs/en/env-vars
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_BASE="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
CFG="$(mktemp -d "${TMP_BASE}/pavedline-install-test.XXXXXX")"
CFG="$(cd "$CFG" && pwd -P)"
trap 'rm -rf "$CFG"' EXIT

case "$CFG" in
  "$TMP_BASE"/*) ;;
  *) echo "refusing: config dir $CFG is not under $TMP_BASE" >&2; exit 1 ;;
esac
echo "Throwaway config dir: $CFG"
export CLAUDE_CONFIG_DIR="$CFG"

echo "== add local marketplace"
claude plugin marketplace add "$REPO_ROOT"
echo "== add claude-plugins-official marketplace"
claude plugin marketplace add anthropics/claude-plugins-official
echo "== add knowledge-work-plugins marketplace"
claude plugin marketplace add anthropics/knowledge-work-plugins
echo "== marketplaces known"
claude plugin marketplace list || true
echo "== install pavedline"
claude plugin install pavedline@pavedline --scope user

claude plugin list --json > "$CFG/list.json"
python3 - "$CFG/list.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
items = data if isinstance(data, list) else data.get("plugins", data)
found = {}
for p in items:
    pid = p.get("id") or p.get("name")
    found[pid] = p.get("enabled", True)
print("installed plugins:", json.dumps(found, sort_keys=True))
if found.get("pavedline@pavedline") is not True:
    print("FAIL: pavedline@pavedline missing or disabled"); sys.exit(1)
print("OK: pavedline@pavedline installed and enabled")
for dep in ("superpowers@claude-plugins-official",
            "mattpocock-skills@claude-plugins-official",
            "product-management@knowledge-work-plugins"):
    print(("auto-installed: " if dep in found else "NOT installed:   ") + dep)
PY
