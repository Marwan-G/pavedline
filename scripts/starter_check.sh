#!/usr/bin/env bash
# Prove the whole stack pack works on a generated neutral product: render it, then build, test, boot and deploy it.
# usage: scripts/starter_check.sh [--stage generate|static|unit|cluster|full|all] [--keep]
#   generate  only build the tree and print its path (last stdout line); the tree is kept
#   static    web boundary, deploy manifest vs charts, helm + Checkov, actionlint, the records scripts, gitleaks
#             (the pin in scripts/gitleaks.env, over a git archive export under $HOME)
#   unit      pnpm install, lint/typecheck/test, both next builds, Playwright + axe, generated-file checks,
#             mobile lint/types/jest + expo prebuild, api uv sync, ruff, pyright, lint-imports, pytest on a
#             throwaway Postgres, rls_check and contract_check against the migrated database
#   cluster   kind cluster, deploy through Argo CD, curl every hostname, tear down
#   full      the cluster stage with the production shape of the database: three Postgres instances, backups to the
#             local S3 store (SeaweedFS, up.sh --full: cert-manager + the Barman Cloud plugin), a completed backup and
#             the restore drill (scripts/restore_drill.sh: restore into db-restore, read a marker row back)
#             then the three alerts (full-alerts): the checker chart is deployed against a local sink and each alert is
#             driven red (endpoint down, backup too old, scheduled job late); exactly one message each, heartbeat only
#             when all green
#   all       static + unit + cluster (default; full is separate, CI runs it in its own job)
# Needs: python3, git, node + npx (or pnpm), uv, docker, helm, actionlint, dot (graphviz); kind + kubectl + curl for
# the cluster stage. Native mobile builds (Gradle, Xcode) run only in CI. Never touches a context that is not
# kind-pavedline-*. Exit 0 only if every step passed.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN="$ROOT/plugins/pavedline"
PACK="$PLUGIN/stacks/nextjs-fastapi"
FIXTURE="$ROOT/tests/fixtures/starter-answers.json"
PROJECT=ci
CTX="kind-pavedline-$PROJECT"
GATEWAY_PORT=8080

STAGE=all
KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --stage) STAGE="${2:-}"; shift 2 ;;
    --stage=*) STAGE="${1#--stage=}"; shift ;;
    --keep) KEEP=1; shift ;;
    -h|--help) awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
case "$STAGE" in generate|static|unit|cluster|full|all|selftest) ;; *) echo "unknown stage: $STAGE (generate|static|unit|cluster|full|all)" >&2; exit 2 ;; esac
[ "$STAGE" = generate ] && KEEP=1

# Refuse any Kubernetes context that is not a Pavedline kind cluster, before anything is created.
require_kind_context() {
  case "$1" in
    kind-pavedline-*) ;;
    *) echo "refusing: context '$1' is not a kind-pavedline-* context" >&2; exit 2 ;;
  esac
}
require_kind_context "$CTX"

say() { echo "$@" >&2; }
need() { command -v "$1" >/dev/null 2>&1 || { say "missing tool: $1"; exit 2; }; }
for t in python3 git; do need "$t"; done
case "$STAGE" in
  static) for t in helm docker actionlint dot; do need "$t"; done ;;
  unit) for t in uv docker node; do need "$t"; done ;;
  cluster|full) for t in kind kubectl helm docker curl; do need "$t"; done ;;
  all) for t in uv docker node helm actionlint dot kind kubectl curl; do need "$t"; done ;;
esac

WORK="$(mktemp -d "${TMPDIR:-/tmp}/pavedline-starter.XXXXXX")" || { say "cannot create a temp directory under ${TMPDIR:-/tmp}"; exit 2; }
T="$WORK/example"
LOGS="$WORK/logs"
mkdir -p "$T" "$LOGS"
PG_NAME="pl-starter-pg-$$"
CLUSTER_UP=0          # 1 once this run is about to create the cluster, so teardown must delete it
SHARED_PRE_EXISTING=0 # 1 when kind-registry or kind-git already existed before this run (they are not ours to remove)
RESULTS=()
FAILED=0
START_ALL=$(date +%s)

# Delete our cluster. The shared kind-registry and kind-git containers go only when this run created them and no
# other pavedline-* cluster still uses them.
note_shared_containers() {
  local c
  for c in kind-registry kind-git; do
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$c"; then SHARED_PRE_EXISTING=1; fi
  done
}
teardown_cluster() {
  say "== tearing down $CTX"
  "$T/scripts/local-cluster/down.sh" "$PROJECT" >&2 2>&1 || say "cluster teardown reported an error"
  if [ "$SHARED_PRE_EXISTING" = 1 ]; then
    say "keeping kind-registry and kind-git: they existed before this run"
  elif kind get clusters 2>/dev/null | grep -q '^pavedline-'; then
    say "keeping kind-registry and kind-git: another pavedline-* cluster exists"
  else
    docker rm -f kind-registry kind-git >/dev/null 2>&1 || true
  fi
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  # shellcheck disable=SC2046
  kill $(jobs -p) 2>/dev/null || true
  docker rm -f "$PG_NAME" >/dev/null 2>&1 || true
  if [ "$CLUSTER_UP" = 1 ]; then teardown_cluster; fi
  if [ "$KEEP" = 1 ]; then say "kept: $T (logs: $LOGS)"; else rm -rf "$WORK"; fi
  exit "$rc"
}
# A signal exits with the conventional code and hands over to the EXIT trap, which cleans up and keeps that code.
trap 'exit 130' INT
trap 'exit 143' TERM
trap cleanup EXIT

# step <name> <function>: run the function in a subshell with errexit, log to $LOGS, print one PASS/FAIL line.
step() {
  local name="$1" fn="$2" t0 rc=0 log="$LOGS/$1.log"
  t0=$(date +%s)
  # Never call step in an if/&&/|| list: errexit is ignored inside the subshell there and a step would pass after a
  # failed command. The subshell runs in the background and is waited for so a signal reaches the trap at once.
  ( set -euo pipefail; cd "$T"; "$fn" ) >"$log" 2>&1 &
  wait $!
  rc=$?
  local dt=$(( $(date +%s) - t0 ))
  if [ "$rc" = 0 ]; then
    say "PASS  $name (${dt}s)"; RESULTS+=("PASS  $name (${dt}s)")
  else
    say "FAIL  $name (${dt}s, exit $rc); last lines of $log:"; tail -n 25 "$log" >&2
    RESULTS+=("FAIL  $name (${dt}s)"); FAILED=$((FAILED + 1))
  fi
  return "$rc"
}

# ---------- facts from the fixture and the pack ----------
SURFACES="$(python3 -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["surfaces"]))' "$FIXTURE")"
TENANCY="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tenancy"])' "$FIXTURE")"
has() { case ",$SURFACES," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

# Hidden self-test of step() and of the teardown: PAVEDLINE_SELFTEST=good|bad|bad-in-if|sleep|teardown (used by tests).
st_good() { true; echo ok; }
st_bad() { false; echo after; true; }
st_sleep() { sleep 60; }
if [ "$STAGE" = selftest ]; then
  case "${PAVEDLINE_SELFTEST:-good}" in
    good) step selftest-good st_good ;;
    bad) step selftest-bad st_bad ;;
    bad-in-if) step selftest-bad st_bad; if [ $? = 0 ]; then say "unexpected pass"; fi ;;
    sleep) step selftest-sleep st_sleep ;;
    teardown)
      # As if this run had created the cluster: the EXIT trap tears it down with the same logic as a real run.
      mkdir -p "$T/scripts/local-cluster"
      cp "$ROOT/plugins/pavedline/scripts/local-cluster/down.sh" "$T/scripts/local-cluster/down.sh"
      note_shared_containers
      CLUSTER_UP=1
      ;;
  esac
  if [ "$FAILED" = 0 ]; then exit 0; fi
  exit 1
fi

# ---------- 1. generate ----------
generate() {
  python3 "$PLUGIN/scripts/start_project.py" --target "$T" --name example --mode solo
  python3 "$PLUGIN/scripts/apply_stack.py" --target "$T" --pack nextjs-fastapi --surfaces "$SURFACES" \
    --tenancy "$TENANCY" --name example
  # The example overlay is for this check only: a product never receives it.
  cp -R "$PACK/example/." "$T/"
  # --stage full: the database in its production shape (three instances, backups to the local S3 store).
  if [ "$STAGE" = full ]; then cp -R "$PACK/example-full/." "$T/"; fi
  git init -q
  git add -A
  git -c user.name=starter -c user.email=starter@example.invalid commit -q -m "starter"
}
step generate generate
[ $? = 0 ] || { say "FAIL: cannot generate the tree"; exit 1; }

if [ "$STAGE" = generate ]; then
  echo "$T"
  exit 0
fi

# pnpm: the version in package.json's packageManager; npx fetches it when pnpm is not installed.
PNPM_VERSION="$(python3 -c 'import json; print(json.load(open("'"$T"'/package.json"))["packageManager"].split("@")[1].split("+")[0])' 2>/dev/null || echo 11.28.8)"
pnpm() {
  if command -v pnpm >/dev/null 2>&1 && [ "$(command pnpm --version 2>/dev/null)" = "$PNPM_VERSION" ]; then
    command pnpm "$@"
  else
    npx --yes "pnpm@$PNPM_VERSION" "$@"
  fi
}

# ---------- 2. static ----------
s_boundary() { python3 scripts/web_boundary_check.py; }

s_deploy_manifest() {
  python3 - <<'PY'
import json, os, sys
apps = {a["name"] for a in json.load(open("infra/local-deploy.json"))["apps"]}
charts = {d for d in os.listdir("infra/k8s/apps") if os.path.isdir(os.path.join("infra/k8s/apps", d))}
if apps != charts:
    sys.exit(f"infra/local-deploy.json apps {sorted(apps)} != infra/k8s/apps folders {sorted(charts)}")
print("apps match charts:", ", ".join(sorted(apps)))
PY
}

s_helm_checkov() {
  local out="$LOGS/rendered" chart name env values image
  mkdir -p "$out"
  # Render from a copy: `helm dependency update` writes Chart.lock and charts/, and deploy_local.sh refuses a dirty tree.
  rm -rf "$LOGS/infra"; cp -R infra "$LOGS/infra"
  cd "$LOGS"
  for chart in infra/k8s/apps/*/; do
    name="$(basename "$chart")"
    helm dependency update "$chart"
    helm lint "$chart" -f "$chart/values-staging.yaml"
    for env in staging production; do
      values="$chart/values-$env.yaml"; [ -f "$values" ] || values="$chart/values.yaml"
      helm template "$name" "$chart" -f "$values" --namespace "$name" > "$out/$name-$env.yaml"
    done
  done
  # The scanner image is the one the product's own security workflow pins, by digest.
  image="$(sed -n 's/^ *CHECKOV_IMAGE: *//p' "$T/.github/workflows/security.yml" | head -n 1)"
  [ -n "$image" ] || { echo "no CHECKOV_IMAGE in .github/workflows/security.yml"; exit 1; }
  # Files go in with docker cp, not a bind mount: the temp dir is not shared with a Colima or Docker Desktop VM.
  local cid rc=0
  cid="$(docker create "$image" -d /rendered --framework kubernetes --config-file /checkov.yaml --compact --quiet)"
  docker cp "$out" "$cid:/rendered"
  docker cp "$LOGS/infra/helm/.checkov.yaml" "$cid:/checkov.yaml"
  docker start -a "$cid" || rc=$?
  docker rm -f "$cid" >/dev/null
  return "$rc"
}

# The same pinned image CI runs (scripts/gitleaks.env), over a `git archive HEAD` export of the generated tree. The export
# lives under $HOME: Colima and Docker Desktop VMs share the home directory, not /private/tmp.
s_gitleaks() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "skipping gitleaks: docker is not installed"
    return 0
  fi
  # shellcheck disable=SC1091
  . "$ROOT/scripts/gitleaks.env"
  local export_dir rc=0
  export_dir="$(mktemp -d "$HOME/.pavedline-gitleaks.XXXXXX")"
  if ! git archive HEAD | tar -x -C "$export_dir"; then
    rm -rf "$export_dir"
    echo "gitleaks: git archive export failed"
    return 1
  fi
  docker run --rm -v "$export_dir:/repo:ro" "$GITLEAKS_IMAGE" dir /repo --no-banner --redact || rc=$?
  rm -rf "$export_dir"
  return "$rc"
}

s_actionlint() { actionlint -no-color .github/workflows/*.yml; }

s_records() {
  python3 scripts/sanitize_scan.py
  python3 scripts/dot_check.py --check
  printf 'Gates: TDD ✓ · review ✓ (0 found, 0 fixed) · security ✓ · adversarial n/a · verification ✓\n' > "$LOGS/body-ok.txt"
  printf 'no gates line here\n' > "$LOGS/body-bad.txt"
  python3 scripts/pr_checks.py --body-file "$LOGS/body-ok.txt" --head-ref feature/x
  if python3 scripts/pr_checks.py --body-file "$LOGS/body-bad.txt" --head-ref feature/x; then
    echo "pr_checks accepted a body without the gates line"; exit 1
  fi
}

run_static() {
  if has web || has site; then step static-web-boundary s_boundary; fi
  step static-deploy-manifest s_deploy_manifest
  step static-helm-checkov s_helm_checkov
  step static-actionlint s_actionlint
  step static-gitleaks s_gitleaks
  step static-records s_records
}

# ---------- 3. unit ----------
# Outside the tree: deploy_local.sh refuses a dirty working tree.
export PLAYWRIGHT_BROWSERS_PATH="$WORK/playwright-browsers"

u_install() { pnpm install --frozen-lockfile; }
u_lint() { pnpm -r lint; }
u_typecheck() { pnpm -r typecheck; }
u_test() { pnpm -r test; }
u_generated() { pnpm run check:generated; }
u_build_web() { pnpm --filter @app/web build; }
u_build_site() { pnpm --filter @app/site build; }
u_e2e() {
  local deps=""; [ "${STARTER_PLAYWRIGHT_DEPS:-0}" = 1 ] && deps="--with-deps"
  # shellcheck disable=SC2086
  pnpm --filter @app/web exec playwright install $deps chromium
  pnpm --filter @app/web e2e
}
u_mobile_prebuild() { pnpm --filter @app/mobile exec expo prebuild --no-install --platform android; }

a_sync() { (cd services/api && uv sync --frozen); }
a_ruff() { (cd services/api && uv run ruff check . ../../scripts); }
a_format() { (cd services/api && uv run ruff format --check . ../../scripts); }
a_pyright() { (cd services/api && uv run pyright); }
a_imports() { (cd services/api && uv run lint-imports); }
a_events() { (cd services/api && uv run python ../../scripts/events_check.py --root ../..); }

PG_PORT=""
start_postgres() {
  local image
  image="$(sed -n 's/^ *image: *\(postgres:[^ ]*\)$/\1/p' .github/workflows/ci-api.yml | head -n 1)"
  [ -n "$image" ] || { echo "no pinned postgres image in .github/workflows/ci-api.yml"; exit 1; }
  PG_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
  echo "$PG_PORT" > "$LOGS/pg-port"
  docker run -d --name "$PG_NAME" -p "127.0.0.1:$PG_PORT:5432" -e POSTGRES_PASSWORD=throwaway \
    --health-cmd "pg_isready -U postgres" --health-interval 2s --health-retries 30 "$image" >/dev/null
  local i
  for i in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$PG_NAME")" = healthy ] && return 0
    sleep 2
  done
  echo "postgres did not become healthy"; exit 1
}
a_postgres() { start_postgres; }
pg_url() { echo "postgresql://postgres:throwaway@127.0.0.1:$(cat "$LOGS/pg-port")/postgres"; }
a_pytest() {
  export DATABASE_URL; DATABASE_URL="$(pg_url)"
  cd services/api
  if [ "$TENANCY" = single ]; then uv run pytest -q --ignore=tests/test_tenant_leak.py; else uv run pytest -q; fi
}
a_migrate() {
  export DATABASE_URL; DATABASE_URL="$(pg_url)"
  export DATABASE_OWNER_URL="postgresql://app_owner:owner-pw@127.0.0.1:$(cat "$LOGS/pg-port")/checks"
  cd services/api
  uv run python - <<'PY'
import os
import pathlib

import psycopg
from psycopg import sql

roles = pathlib.Path("db/roles.sql").read_text()
admin = os.environ["DATABASE_URL"]
with psycopg.connect(admin, autocommit=True) as conn:
    conn.execute(roles)
    conn.execute(sql.SQL("ALTER ROLE app_owner PASSWORD 'owner-pw'"))
    conn.execute(sql.SQL("CREATE DATABASE checks OWNER app_owner"))
with psycopg.connect(admin.rsplit("/", 1)[0] + "/checks", autocommit=True) as conn:
    conn.execute(roles)
PY
  uv run alembic upgrade head
}
a_rls() {
  if [ "$TENANCY" = single ]; then echo "RLS check: not applicable (decision 0002)"; return 0; fi
  uv run --project services/api python scripts/rls_check.py \
    --database-url "postgresql://app_owner:owner-pw@127.0.0.1:$(cat "$LOGS/pg-port")/checks" \
    --global-tables services/api/db/global_tables.txt
}
a_contract() {
  DATABASE_URL="$(pg_url)" uv run --project services/api python scripts/contract_check.py \
    --app app.main:app --contract docs/api/openapi.yaml
}

run_unit() {
  if has web || has site || has mobile; then
    step unit-pnpm-install u_install
    step unit-lint u_lint
    step unit-typecheck u_typecheck
    step unit-vitest u_test
    if has web; then
      step unit-generated-files u_generated
      step unit-build-web u_build_web
    fi
    if has site; then step unit-build-site u_build_site; fi
    if has web; then step unit-playwright-axe u_e2e; fi
    if has mobile; then step unit-mobile-prebuild u_mobile_prebuild; fi
  fi
  if has api; then
    step api-uv-sync a_sync
    step api-ruff a_ruff
    step api-format a_format
    step api-pyright a_pyright
    step api-lint-imports a_imports
    step api-events-check a_events
    step api-postgres a_postgres
    step api-pytest a_pytest
    step api-migrate a_migrate
    step api-rls-check a_rls
    step api-contract-check a_contract
  fi
}

# ---------- 4. cluster ----------
c_up() {
  if kind get clusters 2>/dev/null | grep -qx "pavedline-$PROJECT"; then
    echo "a kind cluster pavedline-$PROJECT already exists; remove it (down.sh $PROJECT --all) and rerun"; exit 1
  fi
  if [ "$STAGE" = full ]; then "$T/scripts/local-cluster/up.sh" "$PROJECT" --full; else "$T/scripts/local-cluster/up.sh" "$PROJECT"; fi
}
c_verify() {
  require_kind_context "$CTX"
  if [ "$STAGE" = full ]; then "$T/scripts/local-cluster/verify.sh" "$PROJECT" --full; else "$T/scripts/local-cluster/verify.sh" "$PROJECT"; fi
}
c_deploy() {
  require_kind_context "$CTX"
  export GIT_AUTHOR_NAME=starter GIT_AUTHOR_EMAIL=starter@example.invalid
  export GIT_COMMITTER_NAME=starter GIT_COMMITTER_EMAIL=starter@example.invalid
  "$T/scripts/deploy_local.sh" "$PROJECT" --check "http app.localtest.me /healthz 200" | tee "$LOGS/deploy.out"
  grep -q '^verified (local)' "$LOGS/deploy.out"
}
c_curl() {
  python3 - "$GATEWAY_PORT" <<'PY'
import json, sys, urllib.request
port = sys.argv[1]
bad = 0
for app in json.load(open("infra/local-deploy.json"))["apps"]:
    if not app.get("host"):
        continue
    path = (app.get("checks") or ["/"])[0]
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Host": app["host"]})
    try:
        code = urllib.request.urlopen(req, timeout=20).status
    except Exception as exc:  # any failure is a failed check
        code = f"error {exc}"
    print(f'{app["host"]}{path} -> {code}')
    bad += code != 200
sys.exit(1 if bad else 0)
PY
}

# --stage full: the database is production-shaped and its backups work.
kc() { kubectl --context "$CTX" "$@"; }
f_instances() {
  require_kind_context "$CTX"
  kc -n postgres wait --for=condition=Ready cluster/db --timeout=600s
  local n
  n="$(kc -n postgres get cluster db -o jsonpath='{.status.readyInstances}')"
  [ "$n" = 3 ] || { echo "expected 3 ready instances, got ${n:-none}"; exit 1; }
  echo "3 instances ready"
  kc -n postgres get objectstore db-backups >/dev/null
  kc -n postgres get cluster db -o jsonpath='{.spec.plugins[0].name} archiver={.spec.plugins[0].isWALArchiver}{"\n"}'
}
f_backup() {
  require_kind_context "$CTX"
  # The ScheduledBackup is immediate: its first Backup appears when the cluster is ready.
  local deadline=$(( $(date +%s) + 600 )) name phase=""
  while :; do
    name="$(kc -n postgres get backup -o jsonpath='{range .items[?(@.spec.method=="plugin")]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}' | grep ' completed$' | head -n 1 | cut -d' ' -f1 || true)"
    [ -n "$name" ] && break
    [ "$(date +%s)" -lt "$deadline" ] || { echo "no scheduled backup completed within 600s"; kc -n postgres get backup -o wide || true; exit 1; }
    sleep 5
  done
  echo "backup $name completed"
}
f_drill() {
  require_kind_context "$CTX"
  "$T/scripts/restore_drill.sh" "$PROJECT" | tee "$LOGS/drill.out"
  grep -q '^RESTORE DRILL PASS' "$LOGS/drill.out"
}

# The three alerts (spec 11.11) against a local sink: a pod that records every request. The checker chart is applied
# straight from the tree (helm template | kubectl apply) into its own namespace; each alert is driven red and must
# produce exactly one notify message, a second run inside the repeat window must produce none, and the heartbeat is
# pinged only when everything is green.
f_alerts() {
  require_kind_context "$CTX"
  local ns=alerts-proof chart=infra/k8s/addons/alerts image
  [ -d "$chart" ] || { echo "no $chart in the generated tree"; exit 1; }
  image="$(sed -n 's/^image: //p' "$chart/values.yaml")"
  [ -n "$image" ] || { echo "no image in $chart/values.yaml"; exit 1; }
  kc create namespace "$ns" >/dev/null
  cat > "$LOGS/sink.py" <<'PY'
import http.server, sys

class H(http.server.BaseHTTPRequestHandler):
    def _do(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode() if n else ""
        print("REQ", self.command, self.path, body, flush=True)
        self.send_response(503 if self.path.startswith("/down") else 200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")
    do_GET = do_POST = _do
    def log_message(self, *a): pass

http.server.ThreadingHTTPServer(("", 8080), H).serve_forever()
PY
  kc -n "$ns" create configmap sink-script --from-file=sink.py="$LOGS/sink.py" >/dev/null
  kc -n "$ns" apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata: {name: sink}
spec:
  replicas: 1
  selector: {matchLabels: {app: sink}}
  template:
    metadata: {labels: {app: sink}}
    spec:
      containers:
        - name: sink
          image: ${image}
          command: [python3, -u, /s/sink.py]
          ports: [{containerPort: 8080}]
          volumeMounts: [{name: s, mountPath: /s}]
      volumes: [{name: s, configMap: {name: sink-script}}]
---
apiVersion: v1
kind: Service
metadata: {name: sink}
spec:
  selector: {app: sink}
  ports: [{port: 80, targetPort: 8080}]
---
apiVersion: batch/v1
kind: CronJob
metadata: {name: never-runs}
spec:
  schedule: "0 0 1 1 *"
  suspend: true
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers: [{name: c, image: ${image}, command: [python3, -c, "pass"]}]
YAML
  kc -n "$ns" rollout status deploy/sink --timeout=300s
  kc -n "$ns" create secret generic alerts-targets \
    --from-literal=NOTIFY_URL="http://sink.${ns}.svc/notify" --from-literal=HEARTBEAT_URL="http://sink.${ns}.svc/heartbeat" >/dev/null

  count() { kc -n "$ns" logs deploy/sink | grep -c "$1" || true; }
  deploy_checks() { # $1 = values file body
    printf '%s\n' "enabled: true" "$1" > "$LOGS/alerts-values.yaml"
    helm template alerts "$chart" --namespace "$ns" -f "$LOGS/alerts-values.yaml" | kc apply -f - >/dev/null
  }
  run_checker() {
    local j="proof-$RANDOM"
    # A copy of the CronJob's Job without its owner: the CronJob keeps one finished Job and could delete an owned copy
    # before its log is read.
    kc -n "$ns" create job "$j" --from=cronjob/alerts-check --dry-run=client -o json \
      | python3 -c 'import json, sys; d = json.load(sys.stdin); d["metadata"].pop("ownerReferences", None); json.dump(d, sys.stdout)' \
      | kc -n "$ns" create -f - >/dev/null
    kc -n "$ns" wait --for=condition=complete "job/$j" --timeout=240s || { kc -n "$ns" logs "job/$j" || true; return 1; }
    kc -n "$ns" logs "job/$j"
    kc -n "$ns" delete job "$j" --wait=false >/dev/null
  }
  expect() { # $1 label, $2 what was counted, $3 expected, $4 got
    [ "$3" = "$4" ] || { echo "FAIL $1: expected $3 $2, got $4"; kc -n "$ns" logs deploy/sink || true; exit 1; }
    echo "ok   $1: $4 $2"
  }
  local ok="http://sink.${ns}.svc/ok" down="http://sink.${ns}.svc/down" n0 h0 n1 h1

  # all green: the heartbeat is pinged, nothing is sent to notify
  deploy_checks "checks: {endpoints: [{name: sink, url: \"$ok\"}], backupMaxAge: 36h}"
  n0="$(count 'REQ POST /notify')"; h0="$(count 'REQ GET /heartbeat')"
  run_checker
  expect green-notify "notify messages" 0 $(( $(count 'REQ POST /notify') - n0 ))
  expect green-heartbeat "heartbeat pings" 1 $(( $(count 'REQ GET /heartbeat') - h0 ))

  # alert 1: an endpoint answers 503; a second run inside the repeat window stays silent
  deploy_checks "checks: {endpoints: [{name: down, url: \"$down\"}], backupMaxAge: 36h}"
  n0="$(count 'REQ POST /notify')"; h0="$(count 'REQ GET /heartbeat')"
  run_checker; run_checker
  expect endpoint-notify "notify messages for endpoint-0-down" 1 $(( $(count 'REQ POST /notify .*endpoint-[0-9][0-9]*-down') ))
  expect endpoint-total "notify messages" 1 $(( $(count 'REQ POST /notify') - n0 ))
  expect endpoint-heartbeat "heartbeat pings" 0 $(( $(count 'REQ GET /heartbeat') - h0 ))

  # alert 2: the newest backup is older than the limit (1s, the drill's backup is minutes old)
  deploy_checks "checks: {endpoints: [{name: sink, url: \"$ok\"}], backupMaxAge: 1s}"
  n0="$(count 'REQ POST /notify')"; h0="$(count 'REQ GET /heartbeat')"
  run_checker; run_checker
  expect backup-notify "notify messages for backup-db-daily" 1 "$(count 'REQ POST /notify .*backup-db-daily')"
  expect backup-total "notify messages" 1 $(( $(count 'REQ POST /notify') - n0 ))
  expect backup-heartbeat "heartbeat pings" 0 $(( $(count 'REQ GET /heartbeat') - h0 ))

  # alert 3: a scheduled job that never ran within its window
  sleep 3
  deploy_checks "checks: {endpoints: [{name: sink, url: \"$ok\"}], backupMaxAge: 36h, jobs: [{namespace: $ns, name: never-runs, maxLate: 1s}]}"
  n0="$(count 'REQ POST /notify')"; h0="$(count 'REQ GET /heartbeat')"
  run_checker; run_checker
  expect job-notify "notify messages for job-$ns-never-runs" 1 "$(count "REQ POST /notify .*job-$ns-never-runs")"
  expect job-total "notify messages" 1 $(( $(count 'REQ POST /notify') - n0 ))
  expect job-heartbeat "heartbeat pings" 0 $(( $(count 'REQ GET /heartbeat') - h0 ))

  # least privilege, as the cluster sees it
  kc auth can-i list backups.postgresql.cnpg.io -n postgres --as="system:serviceaccount:${ns}:alerts" | grep -qx yes
  [ "$(kc auth can-i delete backups.postgresql.cnpg.io -n postgres --as="system:serviceaccount:${ns}:alerts" || true)" = no ]
  [ "$(kc auth can-i get secrets -n postgres --as="system:serviceaccount:${ns}:alerts" || true)" = no ]
  echo "alerts: green, endpoint, backup and job all behaved"
}

run_cluster() {
  if kind get clusters 2>/dev/null | grep -qx "pavedline-$PROJECT"; then
    step cluster-up c_up   # fails with the explanation; nothing of ours to tear down
    return
  fi
  # Set here, in the main shell (a step runs in a subshell): teardown must run even if up.sh dies midway.
  note_shared_containers
  CLUSTER_UP=1
  step cluster-up c_up
  if [ $? = 0 ]; then
    step cluster-verify c_verify
    if [ $? = 0 ]; then
      step cluster-deploy c_deploy
      if [ $? = 0 ]; then
        step cluster-curl c_curl
        if [ "$STAGE" = full ]; then
          step full-instances f_instances
          if [ $? = 0 ]; then
            step full-backup f_backup
            if [ $? = 0 ]; then
              step full-restore-drill f_drill
              if [ $? = 0 ]; then step full-alerts f_alerts; fi
            fi
          fi
        fi
      fi
    fi
  fi
}

case "$STAGE" in
  static) run_static ;;
  unit) run_unit ;;
  cluster|full) run_cluster ;;
  all) run_static; run_unit; run_cluster ;;
esac

# ---------- summary ----------
say ""
say "== starter check summary (stage $STAGE, surfaces $SURFACES, tenancy $TENANCY)"
for r in "${RESULTS[@]}"; do say "$r"; done
say "total: $(( $(date +%s) - START_ALL ))s"
if [ "$FAILED" = 0 ]; then say "STARTER CHECK PASS"; exit 0; fi
say "STARTER CHECK FAIL ($FAILED step(s))"
exit 1
