#!/usr/bin/env bash
# The restore drill: prove a backup of the product's database can be restored into a NEW cluster and holds the data.
#
#   scripts/restore_drill.sh <project> [--namespace postgres] [--source db] [--target db-restore] [--timeout 900]
#   scripts/restore_drill.sh --cloud-context <context> --yes-i-am-the-founder [same options]
#
# Local (kind-pavedline-<project>) it runs the whole drill: it writes a marker row with a random value into the source
# database (through the direct read-write service, as the owner role), takes an on-demand Backup (method: plugin) and
# waits for `completed`, creates a NEW Cluster (default db-restore) bootstrapped from the same ObjectStore, waits until
# it is ready, reads the marker back from the restored cluster and compares it, then deletes the restore cluster and the
# marker table. PASS only if the value read back equals the value written; exit 0 on PASS, 1 on FAIL, 2 on bad usage.
#
# It refuses every context that is not kind-pavedline-*. For a cloud cluster it only PRINTS the commands (the founder
# runs them); nothing here ever runs against a cloud. It refuses a target cluster name equal to the source: the restore
# must never touch the live database.
set -euo pipefail

usage() {
  echo "usage: scripts/restore_drill.sh <project> [--namespace NS] [--source NAME] [--target NAME] [--timeout SECONDS]" >&2
  echo "       scripts/restore_drill.sh --cloud-context <context> --yes-i-am-the-founder [options]   (prints the commands, runs nothing)" >&2
  exit 2
}

PROJECT=""
NS=postgres
SOURCE=db
TARGET=db-restore
STORE=db-backups
TIMEOUT=900
CONTEXT=""
CLOUD_CONTEXT=""
FOUNDER=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --namespace) [ "$#" -ge 2 ] || usage; NS="$2"; shift 2 ;;
    --source) [ "$#" -ge 2 ] || usage; SOURCE="$2"; shift 2 ;;
    --target) [ "$#" -ge 2 ] || usage; TARGET="$2"; shift 2 ;;
    --object-store) [ "$#" -ge 2 ] || usage; STORE="$2"; shift 2 ;;
    --timeout) [ "$#" -ge 2 ] || usage; TIMEOUT="$2"; shift 2 ;;
    --context) [ "$#" -ge 2 ] || usage; CONTEXT="$2"; shift 2 ;;
    --cloud-context) [ "$#" -ge 2 ] || usage; CLOUD_CONTEXT="$2"; shift 2 ;;
    --yes-i-am-the-founder) FOUNDER=1; shift ;;
    -*) usage ;;
    *) [ -z "$PROJECT" ] || usage; PROJECT="$1"; shift ;;
  esac
done

DNS_LABEL='^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$'
for v in "$NS" "$SOURCE" "$TARGET" "$STORE"; do
  [[ "$v" =~ $DNS_LABEL ]] || { echo "error: '$v' is not a lowercase DNS label" >&2; exit 2; }
done
[[ "$TIMEOUT" =~ ^[1-9][0-9]{0,4}$ ]] || { echo "error: --timeout must be a number of seconds (1-99999)" >&2; exit 2; }
if [ "$TARGET" = "$SOURCE" ]; then
  echo "error: the restore target '$TARGET' is the source cluster; the drill restores into a NEW cluster and never touches the live one" >&2
  exit 2
fi

# Cloud: print, never run. Needs both flags, and no kubectl call is made.
if [ -n "$CLOUD_CONTEXT" ]; then
  [ "$FOUNDER" = 1 ] || { echo "error: a cloud context needs --yes-i-am-the-founder; the drill never runs against a cloud, it prints the commands for the founder" >&2; exit 2; }
  CTXQ="$(printf '%q' "$CLOUD_CONTEXT")"   # shell-quoted: the printed commands are pasted into a shell
  cat <<PLAN
# Restore drill for the cloud context ${CTXQ}. NOTHING was run. Run these yourself, in order, and stop at the
# first error.
MARKER=\$(od -An -N16 -tx1 /dev/urandom | tr -d ' \\n')
k() { kubectl --context ${CTXQ} -n ${NS} "\$@"; }
# 1. write the marker (the table is dropped again at step 7)
k exec -i -c postgres \$(k get cluster ${SOURCE} -o jsonpath='{.status.currentPrimary}') -- psql -d app -v ON_ERROR_STOP=1 \\
  -c "CREATE TABLE IF NOT EXISTS pavedline_restore_drill (id text PRIMARY KEY, written_at timestamptz DEFAULT now())" \\
  -c "INSERT INTO pavedline_restore_drill (id) VALUES ('\$MARKER')"
# 2. an on-demand backup through the plugin; wait until its phase is completed
cat <<'YAML' | k apply -f -
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata: {name: drill-1}
spec: {cluster: {name: ${SOURCE}}, method: plugin, pluginConfiguration: {name: barman-cloud.cloudnative-pg.io}}
YAML
k get backup drill-1 -w
#    then close the WAL segment so the backup's last segment is archived, and wait for it (last_archived_wal)
k exec -c postgres \$(k get cluster ${SOURCE} -o jsonpath='{.status.currentPrimary}') -- psql -d app -tAc "SELECT pg_walfile_name(pg_switch_wal())"
k exec -c postgres \$(k get cluster ${SOURCE} -o jsonpath='{.status.currentPrimary}') -- psql -d app -tAc "SELECT last_archived_wal FROM pg_stat_archiver"
# 3. a NEW cluster ${TARGET} recovered from the object store: copy imageName and storage from cluster ${SOURCE}
k get cluster ${SOURCE} -o yaml
#    bootstrap: {recovery: {source: source, database: app, owner: app_owner}}
#    externalClusters: [{name: source, plugin: {name: barman-cloud.cloudnative-pg.io, parameters: {barmanObjectName: ${STORE}, serverName: ${SOURCE}}}}]
# 4. wait until it is ready
k wait --for=condition=Ready cluster/${TARGET} --timeout=${TIMEOUT}s
# 5. read it back; it must print the same value as \$MARKER
k exec -c postgres ${TARGET}-1 -- psql -d app -tAc "SELECT id FROM pavedline_restore_drill"
# 6. delete the restore cluster
k delete cluster ${TARGET}
# 7. drop the marker table on the source
k exec -c postgres \$(k get cluster ${SOURCE} -o jsonpath='{.status.currentPrimary}') -- psql -d app -c "DROP TABLE pavedline_restore_drill"
PLAN
  exit 0
fi

[ -n "$PROJECT" ] || [ -n "$CONTEXT" ] || usage
if [ -z "$CONTEXT" ]; then
  [[ "$PROJECT" =~ $DNS_LABEL ]] || { echo "error: project must be a lowercase DNS label, got: $PROJECT" >&2; exit 2; }
  CONTEXT="kind-pavedline-${PROJECT}"
fi
case "$CONTEXT" in
  kind-pavedline-*) ;;
  *) echo "error: refusing context '$CONTEXT': the drill runs only on kind-pavedline-* contexts (for a cloud use --cloud-context ... --yes-i-am-the-founder, which only prints the commands)" >&2; exit 2 ;;
esac
CLUSTER_NAME="${CONTEXT#kind-}"
if ! kubectl --context "$CONTEXT" get nodes -o name 2>/dev/null | grep -Eq "(^|/)${CLUSTER_NAME}-control-plane$"; then
  echo "error: context ${CONTEXT} does not point at the kind node ${CLUSTER_NAME}-control-plane; refusing" >&2
  exit 2
fi

k() { kubectl --context "$CONTEXT" -n "$NS" "$@"; }
log() { echo "[drill] $*" >&2; }
RESTORE_CREATED=0
MARKER_WRITTEN=0
BACKUP_CREATED=0
PRIMARY=""
BACKUP="drill-$(date +%s)"
MARKER="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
[ "${#MARKER}" = 32 ] || { echo "error: could not make a random marker" >&2; exit 1; }

# Run SQL as app_owner through the direct read-write service. The password travels on stdin, never on a command line.
sql_owner() {
  local pw
  pw="$(k get secret db-owner -o jsonpath='{.data.password}' | base64 -d)"
  printf '%s\n' "$pw" | k exec -i -c postgres "$PRIMARY" -- sh -c \
    'read -r PGPASSWORD; export PGPASSWORD; host="$1"; shift; exec psql -h "$host" -U app_owner -d app -v ON_ERROR_STOP=1 -tA "$@"' _ "${SOURCE}-rw" "$@"
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [ "$RESTORE_CREATED" = 1 ]; then
    log "deleting the restore cluster $TARGET"
    k delete cluster "$TARGET" --ignore-not-found --wait=true --timeout=300s >&2 || echo "warning: could not delete cluster $TARGET; delete it by hand" >&2
  fi
  if [ "$MARKER_WRITTEN" = 1 ]; then
    sql_owner -c "DROP TABLE IF EXISTS pavedline_restore_drill" >/dev/null 2>&1 || echo "warning: could not drop pavedline_restore_drill on $SOURCE; drop it by hand" >&2
  fi
  if [ "$BACKUP_CREATED" = 1 ]; then k delete backup "$BACKUP" --ignore-not-found --wait=false >/dev/null 2>&1 || true; fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fail() { echo "FAIL: $*" >&2; echo "RESTORE DRILL FAIL"; exit 1; }

# 0. The source must exist and be healthy; the target must not exist.
k get cluster "$SOURCE" >/dev/null 2>&1 || fail "cluster $SOURCE not found in namespace $NS"
# --ignore-not-found: absent is an empty answer with exit 0; any other error (API timeout, auth) is not "absent".
EXISTING="$(k get cluster "$TARGET" --ignore-not-found -o name 2>&1)" || fail "could not tell whether cluster $TARGET exists: ${EXISTING}"
[ -z "$EXISTING" ] || fail "cluster $TARGET already exists; the drill creates it and will not reuse or delete a cluster it did not make"
k get objectstore "$STORE" >/dev/null 2>&1 || fail "ObjectStore $STORE not found: backups are not enabled on this database (backup.enabled)"
PRIMARY="$(k get cluster "$SOURCE" -o jsonpath='{.status.currentPrimary}')"
[ -n "$PRIMARY" ] || fail "cluster $SOURCE has no primary yet"
IMAGE="$(k get cluster "$SOURCE" -o jsonpath='{.spec.imageName}')"
STORAGE="$(k get cluster "$SOURCE" -o jsonpath='{.spec.storage.size}')"
DB="$(k get cluster "$SOURCE" -o jsonpath='{.spec.bootstrap.initdb.database}')"
OWNER="$(k get cluster "$SOURCE" -o jsonpath='{.spec.bootstrap.initdb.owner}')"
[ -n "$IMAGE" ] && [ -n "$STORAGE" ] && [ -n "$DB" ] && [ -n "$OWNER" ] || fail "could not read imageName, storage, database and owner from cluster $SOURCE"
[ "$DB" = app ] && [ "$OWNER" = app_owner ] || fail "this drill expects database app owned by app_owner (found $DB / $OWNER)"

# 1. The marker.
log "writing the marker into $SOURCE (through ${SOURCE}-rw as app_owner)"
MARKER_WRITTEN=1
sql_owner -c "CREATE TABLE IF NOT EXISTS pavedline_restore_drill (id text PRIMARY KEY, written_at timestamptz DEFAULT now())" \
  -c "INSERT INTO pavedline_restore_drill (id) VALUES ('${MARKER}')" >/dev/null || fail "could not write the marker row"
WRITTEN="$(sql_owner -c "SELECT id FROM pavedline_restore_drill WHERE id = '${MARKER}'")"
[ "$WRITTEN" = "$MARKER" ] || fail "the marker was not readable from the source after writing it"

# 2. An on-demand backup through the plugin, until completed (or failed, or the time limit).
log "taking backup $BACKUP (method: plugin)"
BACKUP_CREATED=1
k apply -f - >/dev/null <<YAML || fail "could not create the Backup"
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: ${BACKUP}
spec:
  cluster:
    name: ${SOURCE}
  method: plugin
  pluginConfiguration:
    name: barman-cloud.cloudnative-pg.io
YAML
deadline=$(( $(date +%s) + TIMEOUT ))
phase=""
while :; do
  phase="$(k get backup "$BACKUP" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  [ "$phase" = completed ] && break
  if [ "$phase" = failed ]; then
    k get backup "$BACKUP" -o jsonpath='{.status.error}' >&2 || true; echo >&2
    fail "backup $BACKUP failed"
  fi
  [ "$(date +%s)" -lt "$deadline" ] || fail "backup $BACKUP did not complete within ${TIMEOUT}s (phase: ${phase:-none})"
  sleep 5
done
log "backup $BACKUP completed"

# A backup is usually taken on a standby and ends in a WAL segment the primary has not archived yet; a restore needs that
# segment ("WAL ends before consistent recovery point" otherwise). Close the segment and wait until it is archived.
SWITCHED="$(k exec -c postgres "$PRIMARY" -- psql -d "$DB" -tA -c "SELECT pg_walfile_name(pg_switch_wal())")" \
  || fail "could not switch the WAL segment on $PRIMARY"
[[ "$SWITCHED" =~ ^[0-9A-F]{24}$ ]] || fail "unexpected WAL segment name '${SWITCHED}'"
log "waiting until WAL segment $SWITCHED is archived"
deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  archived="$(k exec -c postgres "$PRIMARY" -- psql -d "$DB" -tA -c "SELECT coalesce(last_archived_wal, '') >= '${SWITCHED}' FROM pg_stat_archiver" 2>/dev/null || true)"
  [ "$archived" = t ] && break
  [ "$(date +%s)" -lt "$deadline" ] || fail "WAL segment $SWITCHED was not archived within ${TIMEOUT}s"
  sleep 3
done

# 3. A NEW cluster recovered from the object store. It does not archive WAL (no plugins section), so it cannot write
# into the live backups.
log "creating the restore cluster $TARGET from ObjectStore $STORE (server $SOURCE)"
RESTORE_CREATED=1
k apply -f - >/dev/null <<YAML || fail "could not create the restore cluster"
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ${TARGET}
  labels:
    pavedline.dev/restore-drill: "true"
spec:
  instances: 1
  imageName: ${IMAGE}
  storage:
    size: ${STORAGE}
  bootstrap:
    recovery:
      source: source
      database: ${DB}
      owner: ${OWNER}
  externalClusters:
    - name: source
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: ${STORE}
          serverName: ${SOURCE}
YAML
k wait --for=condition=Ready "cluster/${TARGET}" --timeout="${TIMEOUT}s" >&2 \
  || { k get cluster "$TARGET" -o jsonpath='{.status.phase}: {.status.phaseReason}' >&2 || true; echo >&2; fail "cluster $TARGET was not ready within ${TIMEOUT}s"; }

# 4. Read the marker back from the restored cluster and compare.
log "reading the marker back from $TARGET"
GOT="$(k exec -c postgres "${TARGET}-1" -- psql -d "$DB" -tA -c "SELECT id FROM pavedline_restore_drill WHERE id = '${MARKER}'" 2>/dev/null || true)"
if [ "$GOT" != "$MARKER" ]; then
  fail "the restored cluster does not hold the marker (wrote ${MARKER}, read '${GOT:-nothing}')"
fi
echo "RESTORE DRILL PASS: backup ${BACKUP} restored into ${TARGET} and returned the marker ${MARKER}"
