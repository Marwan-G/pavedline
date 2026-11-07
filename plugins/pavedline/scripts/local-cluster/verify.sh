#!/usr/bin/env bash
# Verify the local cluster: Argo CD and the CNPG operator are Available, and a 1-instance Postgres becomes Ready.
set -euo pipefail

[ "$#" -eq 1 ] || { echo "usage: verify.sh <project>" >&2; exit 2; }
PROJECT="$1"
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CTX="kind-pavedline-${PROJECT}"
SMOKE="$HERE/manifests/cnpg-smoke-cluster.yaml"

fail() { echo "FAIL: $*" >&2; exit 1; }

kubectl --context "$CTX" -n argocd wait --for=condition=Available deployment/argocd-server --timeout=180s \
  || fail "argocd-server is not Available in $CTX"
kubectl --context "$CTX" -n cnpg-system wait --for=condition=Available deployment/cnpg-cloudnative-pg --timeout=180s \
  || fail "the CloudNativePG controller is not Available in $CTX"

kubectl --context "$CTX" apply -f "$SMOKE" || fail "could not apply the smoke Cluster"
if ! kubectl --context "$CTX" wait --for=condition=Ready cluster/smoke --timeout=600s; then
  kubectl --context "$CTX" describe cluster/smoke >&2 || true
  kubectl --context "$CTX" delete -f "$SMOKE" --ignore-not-found --wait=false >&2 || true
  fail "Cluster/smoke did not become Ready within 600s"
fi
kubectl --context "$CTX" delete -f "$SMOKE" --ignore-not-found --timeout=120s \
  || fail "could not delete the smoke Cluster"

echo "OK: $CTX verified (Argo CD, CloudNativePG, Postgres smoke cluster)"
