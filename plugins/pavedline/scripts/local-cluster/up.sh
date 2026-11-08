#!/usr/bin/env bash
# Create the local kind cluster pavedline-<project>, a local registry, Argo CD and the CloudNativePG operator.
set -euo pipefail

usage() { echo "usage: up.sh <project>" >&2; exit 2; }
[ "$#" -eq 1 ] || usage
PROJECT="$1"
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=versions.env
. "$HERE/versions.env"
# shellcheck source=retry.sh
. "$HERE/retry.sh"

CLUSTER="pavedline-${PROJECT}"
CTX="kind-pavedline-${PROJECT}"
REG_NAME="kind-registry"

for tool in docker kind kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || { echo "error: $tool is not installed. Run /pavedline:doctor; it tells you what it will install and why, then installs it with your permission." >&2; exit 1; }
done
if ! docker info >/dev/null 2>&1; then
  echo "error: no container runtime answers. Start Docker or Colima (colima start --cpu 4 --memory 10)." >&2
  exit 1
fi

# 1. Local registry container, bound to loopback only (kind local-registry recipe).
if [ "$(docker inspect -f '{{.State.Running}}' "$REG_NAME" 2>/dev/null || true)" != 'true' ]; then
  docker rm -f "$REG_NAME" >/dev/null 2>&1 || true
  docker run -d --restart=always -p "127.0.0.1:${REGISTRY_PORT}:5000" --network bridge --name "$REG_NAME" registry:3
fi

# 2. The cluster, from the rendered config.
clusters="$(kind get clusters 2>/dev/null || true)"
if grep -qx "$CLUSTER" <<<"$clusters"; then
  echo "cluster $CLUSTER already exists; reusing it"
else
  CONFIG="$(mktemp)"
  trap 'rm -f "$CONFIG"' EXIT
  sed "s|@KIND_NODE_IMAGE@|${KIND_NODE_IMAGE}|g" "$HERE/kind-config.yaml.tpl" > "$CONFIG"
  kind create cluster --name "$CLUSTER" --config "$CONFIG"
fi

# 3. Tell containerd on each node that localhost:PORT is the registry container.
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REGISTRY_PORT}"
for node in $(kind get nodes --name "$CLUSTER"); do
  docker exec "$node" mkdir -p "$REGISTRY_DIR"
  printf '[host."http://%s:5000"]\n' "$REG_NAME" | docker exec -i "$node" cp /dev/stdin "$REGISTRY_DIR/hosts.toml"
done

# 4. Connect the registry to the cluster network.
if [ "$(docker inspect -f '{{json .NetworkSettings.Networks.kind}}' "$REG_NAME")" = 'null' ]; then
  docker network connect "kind" "$REG_NAME"
fi

# 5. Document the registry for tooling (KEP-1755).
kubectl --context "$CTX" apply -f - <<MANIFEST
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
MANIFEST

# 6. Argo CD and the CloudNativePG operator, at the pinned chart versions.
# Charts are pulled as OCI artifacts by version and digest (helm refuses a digest mismatch); retry rides out a
# brief registry or network failure.
retry helm upgrade --install argocd "${ARGOCD_CHART}:${ARGOCD_CHART_VERSION}@${ARGOCD_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace argocd --create-namespace --wait --timeout 10m

retry helm upgrade --install cnpg "${CNPG_CHART}:${CNPG_CHART_VERSION}@${CNPG_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace cnpg-system --create-namespace --wait --timeout 10m

echo "ready: context $CTX, registry localhost:${REGISTRY_PORT}, ports 8080->80 and 8443->443"
