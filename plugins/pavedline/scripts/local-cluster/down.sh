#!/usr/bin/env bash
# Delete the kind cluster pavedline-<project> only. With --all, also remove the shared kind-registry and kind-git containers.
set -euo pipefail

usage() { echo "usage: down.sh <project> [--all]" >&2; exit 2; }
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then usage; fi
PROJECT="$1"
ALL=0
if [ "$#" -eq 2 ]; then
  [ "$2" = "--all" ] || usage
  ALL=1
fi
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi

CLUSTER="pavedline-${PROJECT}"
kind delete cluster --name "$CLUSTER"

if [ "$ALL" -eq 1 ]; then
  docker rm -f kind-registry >/dev/null 2>&1 || true
  docker rm -f kind-git >/dev/null 2>&1 || true
  echo "removed the kind-registry and kind-git containers"
fi
echo "removed cluster $CLUSTER (context kind-pavedline-${PROJECT})"
