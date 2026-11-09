#!/usr/bin/env bash
# Start (or stop) a Cloudflare quick tunnel from the internet to the local cluster's Gateway, for the integration wave:
# real provider webhooks need a public URL. Testing only: no account, the URL changes at every start, 200 requests in
# flight at most, no server-sent events. Stripe webhooks do not need it (`stripe listen --forward-to`).
#
#   tunnel.sh <project> [--host <hostname>]   start; prints the public URL and the provider-dashboard step
#   tunnel.sh stop [<project>]                remove the tunnel container (and, with the project, its route)
#
# Refuses unless SERVICES.md (the current directory's, or $SERVICES_FILE) has a row whose service column is
# `Cloudflare quick tunnel` (case-insensitive; rows inside an HTML comment do not count): the founder approves a new
# service before it is used. The pinned cloudflared image runs on
# the `kind` docker network and talks to the cluster node's Gateway NodePort (30080) directly: kind publishes host port
# 8080 on 127.0.0.1 only, which a container cannot reach through host.docker.internal on every host (Colima, Linux CI).
# Only /webhooks/* and /healthz of the API are exposed: the tunnel sends Host: tunnel.localtest.me and this script applies
# manifests/tunnel-route.yaml, an HTTPRoute for exactly that host and those paths. --host overrides the hostname (the route
# is then written for it too).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=versions.env
. "$HERE/versions.env"
NAME="pavedline-tunnel"

usage() { echo "usage: tunnel.sh <project> [--host <hostname>] | tunnel.sh stop" >&2; exit 2; }

if [ "${1:-}" = "stop" ]; then
  [ "$#" -le 2 ] || usage
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  if [ -n "${2:-}" ] && [[ "$2" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --context "kind-pavedline-$2" -n api delete httproute pavedline-tunnel --ignore-not-found >/dev/null 2>&1 || true
  fi
  echo "tunnel stopped ($NAME removed); its public URL no longer works"
  exit 0
fi

PROJECT=""
HOST_HEADER="tunnel.localtest.me"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) [ "$#" -ge 2 ] || usage; HOST_HEADER="$2"; shift 2 ;;
    -*) usage ;;
    *) [ -z "$PROJECT" ] || usage; PROJECT="$1"; shift ;;
  esac
done
[ -n "$PROJECT" ] || usage
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi
if ! [[ "$HOST_HEADER" =~ ^[A-Za-z0-9]([-A-Za-z0-9.]{0,251}[A-Za-z0-9])?$ ]]; then
  echo "error: --host must be a hostname, got: $HOST_HEADER" >&2
  exit 2
fi

# The founder's approval, checked before anything else runs.
SERVICES_FILE="${SERVICES_FILE:-$PWD/SERVICES.md}"
# (text inside an HTML comment, such as the template's example row, is not approval)
approved() { [ -f "$SERVICES_FILE" ] && awk '/<!--/{c=1} !c{print} /-->/{c=0}' "$SERVICES_FILE" \
  | grep -Eiq '^\|[[:space:]]*Cloudflare quick tunnel[[:space:]]*\|'; }
if ! approved; then
  echo "refusing: ${SERVICES_FILE} has no row for 'Cloudflare quick tunnel'." >&2
  echo "A tunnel exposes the local cluster to the internet; it is a service the founder approves first (testing only, no account, URL changes each start)." >&2
  echo "After the founder says yes, add the row (see templates/SERVICES.md) and run this again." >&2
  exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "error: docker is not installed. Run /pavedline:doctor." >&2; exit 1; }
NODE="pavedline-${PROJECT}-control-plane"
if [ "$(docker inspect -f '{{.State.Running}}' "$NODE" 2>/dev/null || true)" != 'true' ]; then
  echo "error: the kind node ${NODE} is not running; run up.sh ${PROJECT} first." >&2
  exit 1
fi

command -v kubectl >/dev/null 2>&1 || { echo "error: kubectl is not installed. Run /pavedline:doctor." >&2; exit 1; }
CTX="kind-pavedline-${PROJECT}"
BACKEND="$(kubectl --context "$CTX" -n api get svc -l app.kubernetes.io/name=api -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
[ -n "$BACKEND" ] || { echo "error: no API Service in namespace api of ${CTX}; deploy the API first (scripts/deploy_local.sh ${PROJECT})." >&2; exit 1; }
sed -e "s|@BACKEND@|${BACKEND}|g" -e "s|tunnel.localtest.me|${HOST_HEADER}|g" "$HERE/manifests/tunnel-route.yaml" \
  | kubectl --context "$CTX" apply -f - >/dev/null

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --network kind --restart=no "$CLOUDFLARED_IMAGE" \
  tunnel --no-autoupdate --url "http://${NODE}:30080" --http-host-header "$HOST_HEADER" >/dev/null

URL=""
for _ in $(seq 1 45); do
  URL="$(docker logs "$NAME" 2>&1 | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | head -n 1 || true)"
  [ -n "$URL" ] && break
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || true)" != 'true' ]; then break; fi
  sleep 2
done
if [ -z "$URL" ]; then
  echo "error: no public URL after 90 seconds. Last log lines:" >&2
  docker logs --tail 20 "$NAME" >&2 || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  exit 1
fi

echo "tunnel up: ${URL}  ->  ${NODE}:30080 (Host: ${HOST_HEADER}); testing only, the URL changes at every start"
echo "Founder step: in the provider dashboard, set the webhook endpoint to ${URL}/webhooks/<provider> (Clerk: Configure > Webhooks > Add endpoint,"
echo "  development instance; copy its Signing Secret into .env.local as WEBHOOK_CLERK_SECRET, never into chat), then run scripts/local_secrets.sh ${PROJECT}."
echo "Stripe needs no tunnel: stripe listen --forward-to http://api.localtest.me:8080/webhooks/stripe"
echo "Only /webhooks/* and /healthz are reachable through it. Stop it with: tunnel.sh stop ${PROJECT}"
