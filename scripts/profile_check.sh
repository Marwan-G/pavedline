#!/usr/bin/env bash
# Prove the bring-your-own-Kubernetes profile on a throwaway second kind cluster, kind-pavedline-byo: create the
# cluster, serve a tiny product repo from the local git server, run the profile's bootstrap.sh against the cluster
# (--allow-kind, --yes), wait until Argo CD reports every add-on Synced and Healthy and the apps ApplicationSet has
# generated its Application, then tear everything down. Never touches a context that is not kind-pavedline-byo.
# usage: scripts/profile_check.sh [--keep]
# Needs: git, kind, kubectl, helm (4.2.2 or newer), docker, curl.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN="$ROOT/plugins/pavedline"
LC="$PLUGIN/scripts/local-cluster"
PROFILE="$PLUGIN/templates/infra/profiles/byo-kubernetes"
# shellcheck source=/dev/null
. "$LC/versions.env"
# shellcheck source=/dev/null
. "$LC/retry.sh"

CLUSTER="pavedline-byo"
CTX="kind-pavedline-byo"
GIT_NAME="kind-git"
REPO_URL="git://${GIT_NAME}:9418/byo.git"
WAIT_OTHERS_MINUTES="${PROFILE_CHECK_WAIT_MINUTES:-45}"
KEEP=0
case "${1:-}" in
  "") ;;
  --keep) KEEP=1 ;;
  *) echo "usage: scripts/profile_check.sh [--keep]" >&2; exit 2 ;;
esac

say() { echo "== $*" >&2; }
for t in git kind kubectl helm docker curl; do command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t" >&2; exit 2; }; done
case "$CTX" in kind-pavedline-*) ;; *) echo "refusing: $CTX" >&2; exit 2 ;; esac

# One Pavedline kind cluster at a time on a machine: wait for any other pavedline-* cluster to go away.
waited=0
while others="$(kind get clusters 2>/dev/null | grep '^pavedline-' | grep -vx "$CLUSTER" || true)"; [ -n "$others" ]; do
  if [ "$waited" -ge "$WAIT_OTHERS_MINUTES" ]; then echo "error: another cluster is still there after ${WAIT_OTHERS_MINUTES} minutes: $others" >&2; exit 1; fi
  say "another cluster exists ($(echo "$others" | tr '\n' ' ')); waiting 2 minutes"
  sleep 120; waited=$((waited + 2))
done

WORK="$(mktemp -d)"
STARTED_GIT=0
cleanup() {
  rc=$?
  if [ "$KEEP" = 0 ]; then
    say "tearing down"
    kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true
    if [ "$STARTED_GIT" = 1 ]; then docker rm -f "$GIT_NAME" >/dev/null 2>&1 || true; fi
  fi
  rm -rf "$WORK"
  exit "$rc"
}
trap cleanup EXIT

start=$(date +%s)
kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true

say "kind cluster $CLUSTER"
printf 'kind: Cluster\napiVersion: kind.x-k8s.io/v1alpha4\nnodes:\n  - role: control-plane\n    image: %s\n' "$KIND_NODE_IMAGE" > "$WORK/kind.yaml"
for attempt in 1 2 3; do
  if kind create cluster --name "$CLUSTER" --config "$WORK/kind.yaml"; then break; fi
  kind delete cluster --name "$CLUSTER" || true
  [ "$attempt" = 3 ] && { echo "error: kind create cluster failed 3 times" >&2; exit 1; }
  sleep 5
done

say "local git server $GIT_NAME"
have_base="$(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.base.digest"}}' "$GIT_NAME" 2>/dev/null || true)"
if [ "$(docker inspect -f '{{.State.Running}}' "$GIT_NAME" 2>/dev/null || true)" != 'true' ] || [ "$have_base" != "$GIT_SERVER_BASE_IMAGE" ]; then
  docker rm -f "$GIT_NAME" >/dev/null 2>&1 || true
  retry docker build --build-arg "BASE=${GIT_SERVER_BASE_IMAGE}" -t kind-git:local "$LC/git-server"
  docker run -d --restart=always --network kind --name "$GIT_NAME" kind-git:local >/dev/null
  STARTED_GIT=1
fi
docker exec "$GIT_NAME" sh -c "rm -rf /srv/git/byo.git && git init --bare --initial-branch=main /srv/git/byo.git" >/dev/null

say "a tiny product repo: the add-ons and one app chart"
REPO="$WORK/repo"
mkdir -p "$REPO/infra/k8s/apps/demo/templates"
cp -R "$PLUGIN/templates/infra/k8s/addons" "$REPO/infra/k8s/addons"
cat > "$REPO/infra/k8s/apps/demo/Chart.yaml" <<'CHART'
apiVersion: v2
name: demo
version: 0.1.0
CHART
cat > "$REPO/infra/k8s/apps/demo/templates/config.yaml" <<'CM'
apiVersion: v1
kind: ConfigMap
metadata:
  name: demo
data:
  proof: byo
CM
git -C "$REPO" init -q --initial-branch=main
git -C "$REPO" add -A
git -C "$REPO" -c user.name=pavedline -c user.email=pavedline@example.invalid commit -q -m "byo profile proof"
SHA="$(git -C "$REPO" rev-parse HEAD)"
git -C "$REPO" -c protocol.ext.allow=always push --force -q "ext::docker exec -i $GIT_NAME %S /srv/git/byo.git" HEAD:refs/heads/main

say "bootstrap.sh --context $CTX --revision $SHA --environment staging --yes --allow-kind"
"$PROFILE/bootstrap.sh" --context "$CTX" --repo-url "$REPO_URL" --revision "$SHA" --environment staging --yes --allow-kind

say "waiting for Argo CD: the add-ons Synced and Healthy, the apps Application generated"
want_addons="$(find "$PLUGIN/templates/infra/k8s/addons" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | sed 's/^/addon-/')"
deadline=$(( $(date +%s) + 900 ))
while :; do
  rows="$(kubectl --context "$CTX" -n argocd get applications.argoproj.io -o jsonpath='{range .items[*]}{.metadata.name} {.status.sync.status} {.status.health.status}{"\n"}{end}' 2>/dev/null || true)"
  ok=1
  for a in $want_addons; do
    grep -qx "$a Synced Healthy" <<<"$rows" || ok=0
  done
  grep -q '^app-demo ' <<<"$rows" || ok=0
  if [ "$ok" = 1 ]; then break; fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "error: Argo CD did not reach the expected state in 15 minutes; applications:" >&2
    echo "$rows" >&2
    kubectl --context "$CTX" -n argocd get applications.argoproj.io -o yaml 2>/dev/null | grep -E "message:|conditions" | head -20 >&2 || true
    exit 1
  fi
  sleep 10
done
echo "$rows"
elapsed=$(( $(date +%s) - start ))
say "profile_check PASS in ${elapsed}s: add-ons $(echo "$want_addons" | tr '\n' ' ')Synced+Healthy, app-demo generated (revision $SHA)"
