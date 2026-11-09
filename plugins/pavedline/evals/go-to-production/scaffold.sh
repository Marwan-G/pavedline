#!/bin/sh
# A tiny neutral product that is NOT feature-complete: one acceptance test has no merged slice.
set -eu
mkdir -p docs/spec docs/plans decisions docs/production
cat > docs/spec/SPEC.md <<'SPEC'
# Spec

## 5. Acceptance tests

- AT-001 (Web app): Given a user, when they open acme, then they see items.
- AT-002 (Web app): Given a user, when they add an item, then it is listed.
SPEC
cat > docs/plans/2026-11-09-wave-1.md <<'PLAN'
# Wave 1

### Slice 1.1: List items
Tests: AT-001
Surfaces: web, api
Branch: slice-1-1-list-items
Depends on: none

### Slice 1.2: Add item
Tests: AT-002
Surfaces: web, api
Branch: slice-1-2-add-item
Depends on: 1.1
PLAN
printf 'PRODUCT: acme items\nSTEP: 12 — Go to production\nNEXT: ask whether it is time\n' > STATE.md
git init -q . 2>/dev/null || true
# Commit the scaffold so the session starts from clean, committed records (as a real product does).
git add -A && git -c user.name=eval -c user.email=eval@example.com commit -qm "scaffold" 2>/dev/null || true
