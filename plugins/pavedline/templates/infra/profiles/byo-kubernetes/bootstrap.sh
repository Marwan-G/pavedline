#!/usr/bin/env bash
# Bring-your-own-Kubernetes bootstrap: install onto the cluster named by --context the Gateway API CRDs, Envoy Gateway,
# cert-manager, the CloudNativePG operator, the Barman Cloud plugin and Argo CD, then the product's two ApplicationSets
# (infra/k8s/applicationsets/) rendered for one repository, revision and environment.
#
#   bootstrap.sh --context <ctx> --repo-url <url> [--revision <ref>] [--environment staging|production]
#                [--tunnel] [--allow-kind] [--print | --yes]
#
# It PRINTS every command first. Without --yes (the default, --print) it runs nothing at all. With --yes it runs them,
# every kubectl call with --context <ctx> and every helm call with --kube-context <ctx>: it never uses the current
# context and never a --kubeconfig. Every version and digest comes from the plugin's pins file (versions.env), which
# is the single place a pin lives (the file in use is printed; PAVEDLINE_PINS, with PAVEDLINE_TEST=1, swaps it, for the tests only).
#
# Against a real cloud cluster the FOUNDER runs it with --yes in their own terminal; the cluster guard hook blocks the
# agent from running it with --yes unless --context starts with kind-pavedline-, so the agent only ever runs the
# printing form.
# --allow-kind exists for the CI proof on a throwaway kind cluster; it is the only way to bootstrap production onto a
# context named kind-*.
set -euo pipefail

usage() {
  echo "usage: bootstrap.sh --context <ctx> --repo-url <url> [--revision <ref>] [--environment staging|production] [--tunnel] [--allow-kind] [--print | --yes]" >&2
  exit 2
}
die() { echo "error: $*" >&2; exit 2; }

CTX=""
REPO_URL=""
REVISION="main"
ENVIRONMENT="staging"
YES=0
PRINT=0
ALLOW_KIND=0
TUNNEL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --context) [ $# -ge 2 ] || usage; CTX="$2"; shift 2 ;;
    --repo-url) [ $# -ge 2 ] || usage; REPO_URL="$2"; shift 2 ;;
    --revision) [ $# -ge 2 ] || usage; REVISION="$2"; shift 2 ;;
    --environment) [ $# -ge 2 ] || usage; ENVIRONMENT="$2"; shift 2 ;;
    --yes) YES=1; shift ;;
    --print) PRINT=1; shift ;;
    --allow-kind) ALLOW_KIND=1; shift ;;
    --tunnel) TUNNEL=1; shift ;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) usage ;;
  esac
done

[ -n "$CTX" ] || die "--context is required: name the cluster explicitly, the current context is never used"
[[ "$CTX" =~ ^[A-Za-z0-9._:@/-]+$ ]] || die "--context has characters a context name does not use: $CTX"
[ -n "$REPO_URL" ] || die "--repo-url is required and must not be empty"
[[ "$REPO_URL" =~ ^[A-Za-z0-9._:/@~+-]+$ ]] || die "--repo-url has characters a repository URL does not use (no spaces, quotes or shell characters)"
[[ "$REPO_URL" =~ ://[^/]*@ || "$REPO_URL" =~ ^[^/:]+@ ]] && die "--repo-url carries credentials (user@ or user:password@): the URL is printed and written into the ApplicationSets. Give a plain HTTPS URL and register the credential in Argo CD instead"
[[ "$REVISION" =~ ^[A-Za-z0-9._/-]+$ ]] || die "--revision must be a branch, tag or commit name without spaces or shell characters"
case "$ENVIRONMENT" in staging|production) ;; *) die "--environment must be staging or production, got: $ENVIRONMENT" ;; esac
[ "$YES" = 0 ] || [ "$PRINT" = 0 ] || die "--print and --yes exclude each other"
if [ "$ENVIRONMENT" = production ] && [ "$ALLOW_KIND" = 0 ]; then
  case "$CTX" in kind-*) die "refusing: a production bootstrap onto the kind context $CTX is a mistake (--allow-kind is for the CI proof only)" ;; esac
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LC=""
# In the plugin the pins sit at scripts/local-cluster/ above templates/infra; in a product, above infra/.
for cand in "$HERE/../../../../scripts/local-cluster" "$HERE/../../../scripts/local-cluster"; do
  if [ -f "$cand/versions.env" ]; then LC="$cand"; break; fi
done
[ -n "$LC" ] || die "cannot find scripts/local-cluster/versions.env"
# PAVEDLINE_PINS replaces the pins file, checksums included, so it is for the tests only and needs PAVEDLINE_TEST=1.
if [ -n "${PAVEDLINE_PINS:-}" ] && [ "${PAVEDLINE_TEST:-}" != 1 ]; then die "PAVEDLINE_PINS is test-only: it also replaces the checksums; set PAVEDLINE_TEST=1 to use it"; fi
PINS="${PAVEDLINE_PINS:-$LC/versions.env}"
echo "pins file: $PINS"
[ -f "$PINS" ] || die "cannot find the pins file $PINS"
# shellcheck source=/dev/null
. "$PINS"
# shellcheck source=/dev/null
. "$LC/retry.sh"
SETS_DIR="$HERE/../../k8s/applicationsets"
[ -d "$SETS_DIR" ] || die "cannot find the ApplicationSets at $SETS_DIR"

WORK=""
cleanup() { if [ -n "$WORK" ]; then rm -rf "$WORK"; fi; }
trap cleanup EXIT
# Same scheme in the printed plan and the run; the directory is created only with --yes.
TMP_BASE="${TMPDIR:-/tmp}"
WORK_TEMPLATE="${TMP_BASE%/}/pavedline-bootstrap.XXXXXX"
if [ "$YES" = 1 ]; then WORK="$(mktemp -d "$WORK_TEMPLATE")"; else WORK="$WORK_TEMPLATE"; fi
export RETRY_SCRIPT=bootstrap.sh

if [ "$YES" = 1 ]; then echo "== running against context $CTX (environment $ENVIRONMENT)"; else echo "== PRINT ONLY: nothing is run; add --yes to run these against context $CTX (environment $ENVIRONMENT)"; fi

# step <command...>: print it, run it only with --yes (network steps ride out a brief failure).
step() {
  printf '+'; printf ' %q' "$@"; printf '\n'
  if [ "$YES" = 1 ]; then retry "$@"; fi
}
# check_sha <file> <expected>: the pinned checksum is the check.
check_sha() {
  printf '+ sha256 of %s must be %s\n' "$1" "$2"
  if [ "$YES" = 1 ]; then
    local got
    if command -v sha256sum >/dev/null 2>&1; then got="$(sha256sum "$1" | cut -d' ' -f1)"; else got="$(shasum -a 256 "$1" | cut -d' ' -f1)"; fi
    [ "$got" = "$2" ] || { echo "error: $1 has sha256 $got, expected $2" >&2; exit 1; }
  fi
}
kc() { step kubectl --context "$CTX" "$@"; }
# render_apply <file> <sed args>: fill the placeholders into a file in $WORK, then apply that file. A retry applies the
# whole file again (a pipe would be empty on every attempt after the first).
render_apply() {
  local file="$1" out; shift
  out="$WORK/$(basename "$file")"
  printf '+ sed'; printf ' %q' "$@"; printf ' %q > %q\n' "$file" "$out"
  if [ "$YES" = 1 ]; then sed "$@" "$file" > "$out"; fi
  kc apply -f "$out"
}

echo '-- 1. Gateway API CRDs and Envoy Gateway'
# 1. Gateway API standard CRDs (checked), then Envoy Gateway. kubectl owns every CRD: the chart installs without its own.
step curl --fail --silent --show-error --location -o "$WORK/gateway-crds.yaml" \
  "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml"
check_sha "$WORK/gateway-crds.yaml" "$GATEWAY_CRDS_SHA256"
kc apply --server-side -f "$WORK/gateway-crds.yaml"
kc wait --for=condition=Established crd/gateways.gateway.networking.k8s.io crd/httproutes.gateway.networking.k8s.io --timeout=60s
step helm pull "${ENVOY_GATEWAY_CHART}:${ENVOY_GATEWAY_CHART_VERSION}@${ENVOY_GATEWAY_CHART_DIGEST}" --untar --untardir "$WORK/envoy"
kc apply --server-side -f "$WORK/envoy/gateway-helm/charts/crds/crds/generated/"
step helm upgrade --install eg "${ENVOY_GATEWAY_CHART}:${ENVOY_GATEWAY_CHART_VERSION}@${ENVOY_GATEWAY_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace envoy-gateway-system --create-namespace --set crds.enabled=false --wait --timeout 10m

echo '-- 2. cert-manager, CloudNativePG, the Barman Cloud plugin'
# 2. cert-manager (the Barman Cloud plugin's certificates), then the CloudNativePG operator, then the plugin in cnpg-system.
step helm upgrade --install cert-manager "${CERT_MANAGER_CHART}:${CERT_MANAGER_CHART_VERSION}@${CERT_MANAGER_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace cert-manager --create-namespace --set crds.enabled=true --wait --timeout 10m
step helm upgrade --install cnpg "${CNPG_CHART}:${CNPG_CHART_VERSION}@${CNPG_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace cnpg-system --create-namespace --wait --timeout 10m
step curl --fail --silent --show-error --location -o "$WORK/barman-plugin.yaml" \
  "https://github.com/cloudnative-pg/plugin-barman-cloud/releases/download/${BARMAN_PLUGIN_VERSION}/manifest.yaml"
check_sha "$WORK/barman-plugin.yaml" "$BARMAN_PLUGIN_SHA256"
kc apply --server-side --force-conflicts -f "$WORK/barman-plugin.yaml"
# The manifest names its images by tag; move them to the pinned digests (the sidecar image is read from a Secret).
printf '+ read the Secret name: kubectl --context %q -n cnpg-system get deployment barman-cloud -o jsonpath of the SIDECAR_IMAGE secretKeyRef name\n' "$CTX"
SIDECAR_REF=barman-cloud-sidecar-secret  # the name read from the deployment (shown in the printed plan only)
if [ "$YES" = 1 ]; then
  SIDECAR_REF="$(kubectl --context "$CTX" -n cnpg-system get deployment barman-cloud -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="SIDECAR_IMAGE")].valueFrom.secretKeyRef.name}')"
  [ -n "$SIDECAR_REF" ] || { echo "error: could not find the SIDECAR_IMAGE Secret of deployment barman-cloud" >&2; exit 1; }
fi
kc -n cnpg-system patch secret "$SIDECAR_REF" --type merge -p "{\"stringData\":{\"SIDECAR_IMAGE\":\"${BARMAN_SIDECAR_IMAGE}\"}}"
kc -n cnpg-system set image deployment/barman-cloud "barman-cloud=${BARMAN_PLUGIN_IMAGE}"
kc -n cnpg-system rollout status deployment/barman-cloud --timeout=300s

echo '-- 3. Argo CD and the ApplicationSets'
# 3. Argo CD, then the product's ApplicationSets with the placeholders filled from the flags.
step helm upgrade --install argocd "${ARGOCD_CHART}:${ARGOCD_CHART_VERSION}@${ARGOCD_CHART_DIGEST}" \
  --kube-context "$CTX" --namespace argocd --create-namespace --wait --timeout 10m
for f in addons apps; do
  render_apply "$SETS_DIR/$f.yaml" -e "s|{{REPO_URL}}|${REPO_URL}|g" -e "s|{{REVISION}}|${REVISION}|g" -e "s|{{ENVIRONMENT}}|${ENVIRONMENT}|g"
done

# 4. Optional: the Cloudflare Tunnel connector. Needs the Secret cloudflared-token in namespace cloudflared first (README).
if [ "$TUNNEL" = 1 ]; then
  kc apply -f "$HERE/cloudflared/namespace.yaml"
  render_apply "$HERE/cloudflared/deployment.yaml" -e "s|@CLOUDFLARED_IMAGE@|${CLOUDFLARED_IMAGE}|g"
else
  echo "(skipped: the tunnel connector; create the Secret cloudflared-token, then re-run with --tunnel or apply cloudflared/ by hand, see README.md)"
fi
if [ "$YES" = 1 ]; then echo "== done: Argo CD now syncs the add-ons from $REPO_URL at $REVISION"; else echo "== end of the printed plan; nothing was run"; fi
