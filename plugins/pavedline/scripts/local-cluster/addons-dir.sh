#!/usr/bin/env bash
# Sourced by verify.sh. resolve_addons_dir <local-cluster dir>: print the add-on manifests directory for the layout
# this copy runs in: the plugin (scripts/local-cluster next to templates/infra/k8s/addons) or a product
# (scripts/local-cluster next to infra/k8s/addons).
resolve_addons_dir() {
  local here="$1" cand
  for cand in "$here/../../templates/infra/k8s/addons" "$here/../../infra/k8s/addons"; do
    if [ -d "$cand" ]; then (cd "$cand" && pwd); return 0; fi
  done
  echo "error: cannot find the add-ons directory (looked for templates/infra/k8s/addons and infra/k8s/addons above $here)" >&2
  return 1
}
