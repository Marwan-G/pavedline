#!/usr/bin/env bash
# Create the local kind cluster pavedline-<project>, a local registry, a local git server, Argo CD, the CloudNativePG
# operator, the Gateway API CRDs and Envoy Gateway.
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
GIT_NAME="kind-git"

for tool in docker kind kubectl helm curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "error: $tool is not installed. Run /pavedline:doctor; it tells you what it will install and why, then installs it with your permission." >&2; exit 1; }
done
# helm older than HELM_MIN_VERSION has a known bug that turns the Argo CD install into ~40 minutes; stop now instead.
helm_v="$(helm version --template '{{.Version}}' 2>/dev/null || true)"
if ! [[ "$helm_v" =~ ^v([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3}) ]]; then
  echo "error: could not read the helm version (got: ${helm_v:-nothing}). Run /pavedline:doctor." >&2
  exit 1
fi
have=$(( 10#${BASH_REMATCH[1]} * 1000000 + 10#${BASH_REMATCH[2]} * 1000 + 10#${BASH_REMATCH[3]} ))
IFS=. read -r need_major need_minor need_patch <<<"$HELM_MIN_VERSION"
need=$(( 10#$need_major * 1000000 + 10#$need_minor * 1000 + 10#$need_patch ))
if [ "$have" -lt "$need" ]; then
  echo "error: helm $helm_v is too old; Pavedline needs helm ${HELM_MIN_VERSION} or newer." >&2
  echo "helm v4.2.1 waits the full timeout on every hook deletion, which makes the Argo CD install take ~40 minutes:" >&2
  echo "https://github.com/helm/helm/issues/32214. Upgrade with: brew upgrade helm (macOS), or see https://helm.sh/docs/intro/install/" >&2
  exit 1
fi
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
  if [ -z "$(docker port "${CLUSTER}-control-plane" 30080/tcp 2>/dev/null || true)" ]; then
    echo "error: this cluster was created by an older Pavedline; run down.sh <project> then up.sh <project> (host port 8080 must map to the Gateway NodePort 30080)" >&2
    exit 1
  fi
else
  CONFIG="$(mktemp)"
  trap 'rm -f "$CONFIG"' EXIT
  sed "s|@KIND_NODE_IMAGE@|${KIND_NODE_IMAGE}|g" "$HERE/kind-config.yaml.tpl" > "$CONFIG"
  # kind publishes the API server on a random free host port; another process can take it between the check and the
  # bind ("address already in use"). Remove the half-made cluster and try again, which picks a new port.
  for attempt in 1 2 3; do
    if kind create cluster --name "$CLUSTER" --config "$CONFIG"; then break; fi
    kind delete cluster --name "$CLUSTER" || true
    if [ "$attempt" = 3 ]; then echo "error: kind create cluster failed 3 times" >&2; exit 1; fi
    echo "kind create cluster failed (attempt $attempt of 3); retrying" >&2
    sleep 5
  done
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

# 7. Gateway API standard CRDs, then Envoy Gateway. The CRD file is checked against its pinned sha256.
CRD_FILE="$(mktemp)"
trap 'rm -f "${CONFIG:-}" "$CRD_FILE"' EXIT
retry curl --fail --silent --show-error --location -o "$CRD_FILE" \
  "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml"
if command -v sha256sum >/dev/null 2>&1; then
  got="$(sha256sum "$CRD_FILE" | cut -d' ' -f1)"
else
  got="$(shasum -a 256 "$CRD_FILE" | cut -d' ' -f1)"
fi
[ "$got" = "$GATEWAY_API_STANDARD_SHA256" ] || { echo "error: Gateway API ${GATEWAY_API_VERSION} CRDs have sha256 $got, expected $GATEWAY_API_STANDARD_SHA256" >&2; exit 1; }
retry kubectl --context "$CTX" apply --server-side -f "$CRD_FILE"
kubectl --context "$CTX" wait --for=condition=Established crd/gateways.gateway.networking.k8s.io crd/httproutes.gateway.networking.k8s.io --timeout=60s

# The chart's own CRDs are not used (crds.enabled=false): it bundles Gateway API v1.6.1 (experimental channel), and
# Helm 4 would fight with the pinned v1.6.3 CRDs above over field ownership. One owner for every CRD: kubectl applies the
# Envoy CRDs from the pinned chart, then the chart installs without them.
CHART_DIR="$(mktemp -d)"
trap 'rm -rf "${CONFIG:-}" "$CRD_FILE" "$CHART_DIR"' EXIT
retry helm pull "${ENVOY_GATEWAY_CHART}:${ENVOY_GATEWAY_CHART_VERSION}@${ENVOY_GATEWAY_CHART_DIGEST}" --untar --untardir "$CHART_DIR"
retry kubectl --context "$CTX" apply --server-side -f "$CHART_DIR/gateway-helm/charts/crds/crds/generated/"
retry helm upgrade --install eg "${ENVOY_GATEWAY_CHART}:${ENVOY_GATEWAY_CHART_VERSION}@${ENVOY_GATEWAY_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace envoy-gateway-system --create-namespace --set crds.enabled=false --wait --timeout 10m

# 8. The local git server: Argo CD syncs from git://kind-git:9418/<project>.git. Built from the pinned base image; the
# daemon is read-only and publishes no host port (pushes go through push.sh, `docker exec`). The container is replaced
# when it is not running or was built from a different base image than the pin.
GIT_IMAGE="kind-git:local"
have_base="$(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.base.digest"}}' "$GIT_NAME" 2>/dev/null || true)"
if [ "$(docker inspect -f '{{.State.Running}}' "$GIT_NAME" 2>/dev/null || true)" != 'true' ] || [ "$have_base" != "$GIT_SERVER_BASE_IMAGE" ]; then
  docker rm -f "$GIT_NAME" >/dev/null 2>&1 || true
  retry docker build --build-arg "BASE=${GIT_SERVER_BASE_IMAGE}" -t "$GIT_IMAGE" "$HERE/git-server"
  docker run -d --restart=always --network kind --name "$GIT_NAME" "$GIT_IMAGE"
fi
docker exec "$GIT_NAME" sh -c "[ -d /srv/git/${PROJECT}.git ] || git init --bare --initial-branch=main /srv/git/${PROJECT}.git"

echo "ready: context $CTX, registry localhost:${REGISTRY_PORT}, port 8080->Gateway :80, git git://kind-git:9418/${PROJECT}.git (in cluster; push with push.sh ${PROJECT})"
