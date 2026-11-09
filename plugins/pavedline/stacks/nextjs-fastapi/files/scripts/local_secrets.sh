#!/usr/bin/env bash
# Create the Secrets the API and its database need on the LOCAL kind cluster kind-pavedline-<project>. Idempotent: an
# existing password is kept; nothing is ever printed that holds a value. Kind only: it refuses any other context
# before it changes anything. Secrets never go in git (the cloud ones come from the vault, a later step).
#
#   namespace postgres: db-owner, db-runtime, db-admin  (kubernetes.io/basic-auth, random passwords)
#                       db-backup-s3  (keys access-key-id, secret-access-key) ONLY when the cluster was made with
#                       `up.sh <project> --full`: copied from the local S3 store's own Secret; absent otherwise
#   namespace api:      api-db   DATABASE_URL (runtime role, through the pooler), DATABASE_OWNER_URL (owner, direct)
#                       api-webhooks WEBHOOK_CLERK_SECRET, WEBHOOK_STRIPE_SECRET from .env.local (only keys with a value;
#                       may be empty; mounted by the local API values, optional)
#                       api-provider-keys CLERK_SECRET_KEY, STRIPE_SECRET_KEY (provider TEST keys, only when set;
#                       created only when at least one is set; not mounted by any chart: the product's own slices do)
#                       api-auth AUTH_ISSUER, AUTH_AUDIENCE, AUTH_JWKS_URL, AUTH_TENANT_CLAIM from .env.local (may be empty)
set -euo pipefail

[ "$#" -eq 1 ] || { echo "usage: scripts/local_secrets.sh <project>" >&2; exit 2; }
PROJECT="$1"
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi
CTX="kind-pavedline-${PROJECT}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.local}"
DB_NAME=app
POOLER_HOST="db-pooler-rw.postgres.svc.cluster.local"
RW_HOST="db-rw.postgres.svc.cluster.local"

# Kind only, checked before anything is created: the context must exist, and its node must be the kind control plane.
if ! kubectl config get-contexts -o name 2>/dev/null | grep -qx "$CTX"; then
  echo "error: refusing to run: there is no kubeconfig context ${CTX}. This script only talks to a local kind cluster made by local-cluster/up.sh ${PROJECT}." >&2
  exit 1
fi
if ! kubectl --context "$CTX" get nodes -o name 2>/dev/null | grep -Eq "(^|/)pavedline-${PROJECT}-control-plane$"; then
  echo "error: refusing to run: context ${CTX} does not point at the kind node pavedline-${PROJECT}-control-plane." >&2
  exit 1
fi

k() { kubectl --context "$CTX" "$@"; }

ensure_namespace() { # <name> [label=value]
  k create namespace "$1" --dry-run=client -o yaml | k apply -f - >/dev/null
  if [ "$#" -gt 1 ]; then k label namespace "$1" "$2" --overwrite >/dev/null; fi
}

existing_password() { # <namespace> <secret>: prints the stored password, or nothing when the Secret does not exist
  local out err rc=0
  err="$(mktemp)"
  out="$(k -n "$1" get secret "$2" -o jsonpath='{.data.password}' 2>"$err")" || rc=$?
  if [ "$rc" -ne 0 ]; then
    if grep -q 'NotFound' "$err"; then rm -f "$err"; return 0; fi
    echo "error: could not read Secret $1/$2 (not a NotFound error), stopping so no password is replaced:" >&2
    cat "$err" >&2
    rm -f "$err"
    return 1
  fi
  rm -f "$err"
  printf '%s' "$out" | base64 -d
}

# Values travel on stdin (never in a command line, never in the output).
apply_secret() { # <namespace> <name> <type>; env-file lines on stdin
  k -n "$1" create secret generic "$2" --type="$3" --from-env-file=/dev/stdin --dry-run=client -o yaml \
    | k apply --server-side --force-conflicts -f - >/dev/null
}

role_password() { # <namespace> <secret> <username>: creates the Secret if missing; prints the password
  local pw
  pw="$(existing_password "$1" "$2")" || exit 1  # no errexit inside $( ): stop on a real kubectl error
  if [ -z "$pw" ]; then
    pw="$(openssl rand -hex 24)"
    printf 'username=%s\npassword=%s\n' "$3" "$pw" | apply_secret "$1" "$2" kubernetes.io/basic-auth
  fi
  printf '%s' "$pw"
}

ensure_namespace postgres
ensure_namespace api gateway-access=shared

OWNER_PW="$(role_password postgres db-owner app_owner)"
RUNTIME_PW="$(role_password postgres db-runtime app_runtime)"
role_password postgres db-admin app_admin >/dev/null

# The local S3 store (up.sh --full) owns its throwaway key; the database's backups read a copy in their namespace.
if k -n seaweedfs get secret seaweedfs-s3 >/dev/null 2>&1; then
  ak="$(k -n seaweedfs get secret seaweedfs-s3 -o jsonpath='{.data.access-key-id}' | base64 -d)"
  sk="$(k -n seaweedfs get secret seaweedfs-s3 -o jsonpath='{.data.secret-access-key}' | base64 -d)"
  printf 'access-key-id=%s\nsecret-access-key=%s\n' "$ak" "$sk" | apply_secret postgres db-backup-s3 Opaque
  S3_NOTE=" db-backup-s3 (postgres)"
else
  S3_NOTE=""
fi

printf 'DATABASE_URL=postgresql://app_runtime:%s@%s:5432/%s\nDATABASE_OWNER_URL=postgresql://app_owner:%s@%s:5432/%s\n' \
  "$RUNTIME_PW" "$POOLER_HOST" "$DB_NAME" "$OWNER_PW" "$RW_HOST" "$DB_NAME" | apply_secret api api-db Opaque

# api-auth: only the keys .env.local actually sets (read as text, never sourced). No keys: an empty Secret, and the API
# runs with APP_ENV=development locally, where every /v1 route answers 401.
found=()
auth_lines=""
if [ -f "$ENV_FILE" ]; then
  for key in AUTH_ISSUER AUTH_AUDIENCE AUTH_JWKS_URL AUTH_TENANT_CLAIM; do
    value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/" || true)"
    if [ -n "$value" ]; then
      auth_lines+="${key}=${value}"$'\n'
      found+=("$key")
    fi
  done
fi
printf '%s' "$auth_lines" | apply_secret api api-auth Opaque

# api-webhooks: only the signing secrets of the webhook providers (Clerk dev instance endpoint, `stripe listen`); same
# rules (empty values are skipped). api-provider-keys: the providers' TEST secret keys for the integration wave,
# created only when one is set and mounted by nothing here (the API does not use them).
hook_lines=""
provider_lines=""
if [ -f "$ENV_FILE" ]; then
  for key in WEBHOOK_CLERK_SECRET WEBHOOK_STRIPE_SECRET CLERK_SECRET_KEY STRIPE_SECRET_KEY; do
    value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/" || true)"
    if [ -n "$value" ]; then
      case "$key" in
        WEBHOOK_*) hook_lines+="${key}=${value}"$'\n' ;;
        *) provider_lines+="${key}=${value}"$'\n' ;;
      esac
    fi
  done
fi
printf '%s' "$hook_lines" | apply_secret api api-webhooks Opaque
if [ -n "$provider_lines" ]; then printf '%s' "$provider_lines" | apply_secret api api-provider-keys Opaque; fi

echo "ok: ${CTX}: Secrets db-owner, db-runtime, db-admin${S3_NOTE} (postgres) and api-db, api-auth, api-webhooks (api) are in place"
if [ "${#found[@]}" -eq 0 ]; then
  echo "note: no AUTH_* keys in ${ENV_FILE}: api-auth is empty and the API runs with APP_ENV=development (every /v1 route answers 401). Copy .env.local.example to .env.local, fill it in and run this script again to test tokens."
else
  echo "api-auth keys set: ${found[*]}"
fi
