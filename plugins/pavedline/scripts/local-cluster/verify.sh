#!/usr/bin/env bash
# Verify the local cluster: Argo CD, the CNPG operator and Envoy Gateway are Available; a 1-instance Postgres becomes
# Ready; the shared Gateway is Programmed and an HTTPRoute answers on 127.0.0.1:8080; Argo CD syncs from kind-git.
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
# shellcheck source=addons-dir.sh
. "$HERE/addons-dir.sh"
ADDONS="$(resolve_addons_dir "$HERE")" || exit 1
# shellcheck source=versions.env
. "$HERE/versions.env"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

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

# Gateway: the same addon manifests a product ships (priority classes, GatewayClass, EnvoyProxy, Gateway).
kubectl --context "$CTX" -n envoy-gateway-system wait --for=condition=Available deployment/envoy-gateway --timeout=180s \
  || fail "envoy-gateway is not Available in $CTX"
kubectl --context "$CTX" apply -f "$ADDONS/priority-classes/" || fail "could not apply the priority classes"
kubectl --context "$CTX" create namespace gateway --dry-run=client -o yaml | kubectl --context "$CTX" apply -f - \
  || fail "could not create namespace gateway"
kubectl --context "$CTX" -n gateway apply -f "$ADDONS/gateway/" || fail "could not apply the gateway addon"
kubectl --context "$CTX" -n gateway wait --for=condition=Programmed gateway/shared --timeout=180s \
  || { kubectl --context "$CTX" -n gateway describe gateway/shared >&2 || true; fail "Gateway/shared is not Programmed"; }

# HTTPRoute round trip from the host through the kind port mapping 8080 -> NodePort 30080 -> Envoy -> echo backend.
sed "s|@ECHO_IMAGE@|${ECHO_IMAGE}|g" "$HERE/manifests/gateway-smoke.yaml" > "$WORK/gateway-smoke.yaml"
kubectl --context "$CTX" apply -f "$WORK/gateway-smoke.yaml" || fail "could not apply the gateway smoke objects"
kubectl --context "$CTX" -n gateway-smoke wait --for=condition=Available deployment/echo --timeout=180s \
  || fail "the echo backend is not Available"
kubectl --context "$CTX" -n gateway-smoke wait --for=jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}'=True httproute/echo --timeout=60s \
  || fail "HTTPRoute/echo was not Accepted"
body=""
for _ in $(seq 1 30); do
  body="$(curl --silent --max-time 5 http://127.0.0.1:8080/ || true)"
  [ "$body" = "pavedline-echo-ok" ] && break
  sleep 2
done
[ "$body" = "pavedline-echo-ok" ] || fail "http://127.0.0.1:8080/ did not return the echo backend's answer (got: ${body:-nothing})"
kubectl --context "$CTX" delete -f "$WORK/gateway-smoke.yaml" --ignore-not-found --timeout=120s \
  || fail "could not delete the gateway smoke objects"

# Argo CD syncs from the local git server over git://.
docker inspect -f '{{.State.Running}}' kind-git >/dev/null 2>&1 || fail "the kind-git container is not running; run up.sh ${PROJECT}"
mkdir -p "$WORK/repo/smoke"
cat > "$WORK/repo/smoke/configmap.yaml" <<'CM'
apiVersion: v1
kind: ConfigMap
metadata:
  name: git-smoke
data:
  source: kind-git
CM
git -C "$WORK/repo" init --quiet --initial-branch=main
git -C "$WORK/repo" add smoke
git -C "$WORK/repo" -c user.name=pavedline -c user.email=pavedline@localhost commit --quiet -m "git smoke" \
  || fail "could not commit the smoke repo"
(cd "$WORK/repo" && "$HERE/push.sh" "$PROJECT" main) || fail "could not push to kind-git"
sed "s|@PROJECT@|${PROJECT}|g" "$HERE/manifests/argocd-git-smoke.yaml" > "$WORK/argocd-git-smoke.yaml"
kubectl --context "$CTX" apply -f "$WORK/argocd-git-smoke.yaml" || fail "could not apply the Argo CD smoke Application"
synced=""
for _ in $(seq 1 60); do
  synced="$(kubectl --context "$CTX" -n argocd get application git-smoke -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || true)"
  [ "$synced" = "Synced/Healthy" ] && break
  sleep 3
done
if [ "$synced" != "Synced/Healthy" ]; then
  kubectl --context "$CTX" -n argocd describe application git-smoke >&2 || true
  fail "Application/git-smoke did not become Synced/Healthy from git://kind-git:9418 (got: ${synced:-nothing})"
fi
kubectl --context "$CTX" -n git-smoke get configmap git-smoke >/dev/null || fail "the ConfigMap from the git repo is missing"
kubectl --context "$CTX" delete -f "$WORK/argocd-git-smoke.yaml" --ignore-not-found --timeout=120s \
  || fail "could not delete the Argo CD smoke Application"
kubectl --context "$CTX" delete namespace git-smoke --ignore-not-found --timeout=120s || fail "could not delete namespace git-smoke"

echo "OK: $CTX verified (Argo CD, CloudNativePG, Postgres smoke cluster, Gateway Programmed, HTTPRoute round trip, Argo CD sync from kind-git)"
