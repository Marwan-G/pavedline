#!/usr/bin/env bash
# Deploy the committed code of this product to the LOCAL kind cluster kind-pavedline-<project> through Argo CD, then
# verify what runs (never the Synced label). Local only: it refuses any other kubeconfig context before it runs anything.
#
#   scripts/deploy_local.sh <project> [--apps a,b] [--no-build] [--revision <sha>] [--check "<check line>"]...
#
#   --apps a,b        deploy only these apps of infra/local-deploy.json (default: all, in the file's order)
#   --revision <sha>  deploy that earlier deploy commit again, without building (the rollback); implies --no-build
#   --no-build        do not build images (only valid with --revision)
#   --check "<line>"  one check of the PR's `Post-deploy check:`, repeatable, in the allow-listed language of
#                     scripts/post_deploy_check.py (`http <host> <path> <status>`, `kubectl-get <ns> <kind>[/<name>] ...`,
#                     `log-event <ns> <deployment> <event>`).
#                     No shell: anything else is rejected (exit 2) before the deploy starts. All must pass.
#
# What it does: builds each selected app image with a unique tag <git short sha>-<unix time>, pushes it to the local
# registry, makes a DEPLOY COMMIT (HEAD's tree plus the new image tag in each built app's values-local.yaml, made with
# git commit-tree on a temporary index, so your branch, index and working tree are never touched), pushes that commit to
# the in-cluster git server as main, creates the secrets, applies the two ApplicationSets, waits for the add-ons, syncs
# each app with an Argo CD operation (CreateNamespace=true, revision = the deploy commit) and verifies the running state.
# Exit 0 only after `verified (local)`; otherwise it prints `NOT verified: ...` and the rollback command, exit 1.
set -euo pipefail

usage() {
  echo 'usage: scripts/deploy_local.sh <project> [--apps a,b] [--no-build] [--revision <sha>] [--check "<check line>"]...' >&2
  exit 2
}

PROJECT=""
APPS=""
NO_BUILD=0
REVISION=""
CHECKS=""
CHECK_GIVEN=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --apps) [ "$#" -ge 2 ] || usage; APPS="$2"; shift 2 ;;
    --revision) [ "$#" -ge 2 ] || usage; REVISION="$2"; shift 2 ;;
    --check) [ "$#" -ge 2 ] || usage; CHECKS="${CHECKS}${2}"$'\n'; CHECK_GIVEN=1; shift 2 ;;
    --no-build) NO_BUILD=1; shift ;;
    -*) usage ;;
    *) [ -z "$PROJECT" ] || usage; PROJECT="$1"; shift ;;
  esac
done
[ -n "$PROJECT" ] || usage
if ! [[ "$PROJECT" =~ ^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$ ]]; then
  echo "error: project must be a lowercase DNS label (a-z, 0-9, -), got: $PROJECT" >&2
  exit 2
fi
if [ -n "$REVISION" ]; then NO_BUILD=1; fi
if [ "$NO_BUILD" -eq 1 ] && [ -z "$REVISION" ]; then
  echo "error: --no-build deploys an earlier deploy commit; give it with --revision <sha>" >&2
  exit 2
fi

CTX="kind-pavedline-${PROJECT}"
ENVIRONMENT=local

# 1. Kind only, checked before anything else runs: the current context must be this project's kind cluster.
current="$(kubectl config current-context 2>/dev/null || true)"
if [ "$current" != "$CTX" ]; then
  echo "error: refusing to deploy: the current kubeconfig context is '${current:-none}', not ${CTX}. This script only deploys to the local kind cluster made by local-cluster/up.sh ${PROJECT}; switch with: kubectl config use-context ${CTX}" >&2
  exit 2
fi
k() { kubectl --context "$CTX" "$@"; }
# ...and that context must point at THIS project's kind control-plane node (not a cloud cluster with a kind-looking name).
if ! kubectl --context "$CTX" get nodes -o name 2>/dev/null | grep -Eq "(^|/)pavedline-${PROJECT}-control-plane$"; then
  echo "error: refusing to deploy: context ${CTX} does not point at the kind node pavedline-${PROJECT}-control-plane." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "error: $ROOT is not a git repository" >&2; exit 2; }

# The checks are parsed before anything runs; a rejected line stops the deploy (exit 2). No shell ever sees them.
if [ "$CHECK_GIVEN" -eq 1 ]; then
  [ -f "$ROOT/scripts/post_deploy_check.py" ] || { echo "error: scripts/post_deploy_check.py is missing" >&2; exit 2; }
  printf '%s' "$CHECKS" | python3 "$ROOT/scripts/post_deploy_check.py" "$PROJECT" --validate-only || exit 2
fi

# 2. Deploy what is committed: HEAD's tree is what ships, so untracked files are ignored; tracked changes refuse.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "error: the working tree has uncommitted changes; deploy what is committed (commit or stash first)" >&2
  exit 1
fi

# 3. The local-cluster scripts: the product's copy, else PAVEDLINE_LOCAL_CLUSTER_DIR.
if [ -f "$ROOT/scripts/local-cluster/push.sh" ]; then
  LC="$ROOT/scripts/local-cluster"
elif [ -n "${PAVEDLINE_LOCAL_CLUSTER_DIR:-}" ] && [ -f "${PAVEDLINE_LOCAL_CLUSTER_DIR}/push.sh" ]; then
  LC="$PAVEDLINE_LOCAL_CLUSTER_DIR"
else
  echo "error: the local-cluster scripts are missing: expected scripts/local-cluster/ in this repository, or set PAVEDLINE_LOCAL_CLUSTER_DIR to the plugin's scripts/local-cluster directory" >&2
  exit 1
fi
REGISTRY_PORT=5001
if [ -f "$LC/versions.env" ]; then
  # shellcheck disable=SC1091
  . "$LC/versions.env"
fi
REG="localhost:${REGISTRY_PORT}"

POLL="${PAVEDLINE_POLL_SECONDS:-3}"
TIMEOUT="${PAVEDLINE_DEPLOY_TIMEOUT:-420}"
REFNAME="refs/pavedline/local-deploy/${PROJECT}"
REPO_URL="git://kind-git:9418/${PROJECT}.git"
FAILS=""
fail() { FAILS="${FAILS}$1"$'\n'; }
now() { date +%s; }

# The app list: one tab-separated line per selected app: name, image(1|0), context, dockerfile, wait, host, checks.
# (Python sits in variables, not in $(...) heredocs: bash 3.2, the macOS default, mis-parses quotes inside those.)
read -r -d '' PLAN_PY <<'PY' || true
import json, os, sys
path, only, apps_dir = sys.argv[1:4]
try:
    data = json.load(open(path))
except (OSError, ValueError) as e:
    sys.exit("error: cannot read infra/local-deploy.json: %s" % e)
apps = data.get("apps", [])
names = [a["name"] for a in apps]
want = [x for x in only.split(",") if x] if only else names
for w in want:
    if w not in names:
        sys.exit("error: --apps names '%s', which is not in infra/local-deploy.json (%s)" % (w, ", ".join(names)))
for a in apps:
    if a["name"] in want:
        if not os.path.isdir(os.path.join(apps_dir, a["name"])):
            sys.exit("error: infra/local-deploy.json lists '%s' but infra/k8s/apps/%s does not exist" % (a["name"], a["name"]))
        img = a.get("image")
        print("\t".join([a["name"], "1" if img else "0", (img or {}).get("context") or "-", (img or {}).get("dockerfile") or "-",
                         a.get("wait") or "rollout", a.get("host") or "-", ",".join(a.get("checks") or []) or "-"]))
PY
plan="$(python3 -c "$PLAN_PY" "$ROOT/infra/local-deploy.json" "$APPS" "$ROOT/infra/k8s/apps")" || exit 2
[ -n "$plan" ] || { echo "error: no apps to deploy" >&2; exit 2; }
NAMES="$(printf '%s\n' "$plan" | cut -f1 | paste -sd, - | sed 's/,/, /g')"

read -r -d '' COMMIT_PY <<'PY' || true
import json, os, re, subprocess, sys, tempfile
root, deploy_json, tag, built, prev = sys.argv[1:6]
built = set(x for x in built.split(",") if x)


def git(*args, inp=None, env=None):
    r = subprocess.run(["git", "-C", root] + list(args), input=inp, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit("error: git %s: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


TAG_RE = re.compile(r'(?m)^(\s*tag:\s*)(["\']?)[^"\'\s#]+\2')
fd, idx = tempfile.mkstemp(prefix="pl-index-")
os.close(fd)
os.unlink(idx)
env = dict(os.environ, GIT_INDEX_FILE=idx)
try:
    git("read-tree", "HEAD", env=env)
    for app in json.load(open(deploy_json))["apps"]:
        if not app.get("image"):
            continue
        rel = "infra/k8s/apps/%s/values-local.yaml" % app["name"]
        text = git("show", "HEAD:" + rel)
        want = None
        if app["name"] in built:
            want = tag
        elif prev:
            m = TAG_RE.search(git("show", prev + ":" + rel))
            want = m.group(0).split(":", 1)[1].strip().strip("\"'") if m else None
        if want is None:
            continue
        if not TAG_RE.search(text):
            sys.exit("error: %s has no image tag line" % rel)
        new = TAG_RE.sub(lambda m: '%s"%s"' % (m.group(1), want), text, count=1)
        if new == text:
            continue
        mode = git("ls-tree", "HEAD", "--", rel).split()[0]
        blob = git("hash-object", "-w", "--stdin", inp=new).strip()
        git("update-index", "--cacheinfo", "%s,%s,%s" % (mode, blob, rel), env=env)
    tree = git("write-tree", env=env).strip()
finally:
    if os.path.exists(idx):
        os.unlink(idx)
print(git("commit-tree", tree, "-p", "HEAD", "-m", "local deploy " + tag).strip())
PY
SHORT="$(git rev-parse --short HEAD)"
PREV="$(git rev-parse --verify --quiet "${REFNAME}^{commit}" || true)"

# 4. Build and push each selected image with a unique tag; 5. make the deploy commit.
if [ -n "$REVISION" ]; then
  COMMIT="$(git rev-parse --verify --quiet "${REVISION}^{commit}" || true)"
  if [ -z "$COMMIT" ]; then echo "error: --revision ${REVISION} is not a commit of this repository" >&2; exit 2; fi
  subject="$(git log -1 --format=%s "$COMMIT")"
  TAG="${subject#local deploy }"
  [ "$TAG" != "$subject" ] || TAG="unknown"
else
  stamp="$(now)"
  if [ -n "$PREV" ]; then
    prev_tag="$(git log -1 --format=%s "$PREV")"
    prev_tag="${prev_tag#local deploy }"
    if [[ "$prev_tag" =~ ^${SHORT}-([0-9]+)$ ]] && [ "${BASH_REMATCH[1]}" -ge "$stamp" ]; then
      stamp=$(( BASH_REMATCH[1] + 1 ))
    fi
  fi
  TAG="${SHORT}-${stamp}"
  BUILT=""
  while IFS=$'\t' read -r -u 3 name img ctxdir dockerfile _wait _host _checks; do
    [ "$img" = "1" ] || continue
    context="$ROOT"
    [ "$ctxdir" = "." ] || context="$ROOT/$ctxdir"
    if ! docker build -f "$ROOT/$dockerfile" -t "$REG/$name:$TAG" "$context" || ! docker push "$REG/$name:$TAG"; then
      echo "NOT verified: the image build or push of ${name} failed (nothing was deployed)"
      exit 1
    fi
    BUILT="${BUILT:+$BUILT,}$name"
  done 3<<<"$plan"
  COMMIT="$(python3 -c "$COMMIT_PY" "$ROOT" "$ROOT/infra/local-deploy.json" "$TAG" "$BUILT" "$PREV")" || { echo "error: could not make the deploy commit" >&2; exit 1; }
fi

# Push the deploy commit as main of the in-cluster git server. The developer's branch is not touched.
"$LC/push.sh" "$PROJECT" "$COMMIT"
git update-ref --create-reflog "$REFNAME" "$COMMIT"

# 6. Secrets, then the two ApplicationSets (placeholders filled), then wait for the add-ons.
if [ -f "$ROOT/scripts/local_secrets.sh" ]; then
  "$ROOT/scripts/local_secrets.sh" "$PROJECT"
fi
for f in addons apps; do
  file="$ROOT/infra/k8s/applicationsets/$f.yaml"
  if ! grep -q '{{REPO_URL}}' "$file"; then
    echo "error: $file has no {{REPO_URL}} placeholder; the local deploy renders the ApplicationSets itself" >&2
    exit 1
  fi
  sed -e "s|{{REPO_URL}}|${REPO_URL}|g" -e "s|{{REVISION}}|main|g" -e "s|{{ENVIRONMENT}}|${ENVIRONMENT}|g" "$file" | k apply -f - >/dev/null
done

addon_count=0
for d in "$ROOT"/infra/k8s/addons/*/; do [ -d "$d" ] && addon_count=$(( addon_count + 1 )); done
addons_ready() {
  k -n argocd get applications -o json 2>/dev/null | python3 -c '
import json, sys
want = int(sys.argv[1])
try:
    items = json.load(sys.stdin).get("items", [])
except ValueError:
    sys.exit(1)
addons = [a for a in items if a["metadata"]["name"].startswith("addon-")]
bad = [a["metadata"]["name"] for a in addons
       if (a.get("status", {}).get("sync") or {}).get("status") != "Synced" or (a.get("status", {}).get("health") or {}).get("status") != "Healthy"]
sys.exit(0 if len(addons) >= want and not bad else 1)' "$addon_count"
}
deadline=$(( $(now) + TIMEOUT ))
until addons_ready; do
  if [ "$(now)" -ge "$deadline" ]; then fail "the add-ons are not all Synced and Healthy after ${TIMEOUT}s"; break; fi
  sleep "$POLL"
done

# 7. Sync each app, in order, with an Argo CD operation at the deploy commit.
app_status() { # prints: phase operation-revision sync-revision health operation-startedAt ("-" when unknown)
  k -n argocd get application "app-$1" -o json 2>/dev/null | python3 -c '
import json, sys
try:
    s = json.load(sys.stdin).get("status", {})
except ValueError:
    print("- - - - -"); sys.exit(0)
op = s.get("operationState") or {}
print(op.get("phase") or "-", (op.get("syncResult") or {}).get("revision") or "-",
      (s.get("sync") or {}).get("revision") or "-", (s.get("health") or {}).get("status") or "-", op.get("startedAt") or "-")' || echo "- - - - -"
}
SYNC_PATCH='{"operation":{"sync":{"revision":"'"$COMMIT"'","syncOptions":["CreateNamespace=true"]}}}'

sync_app() { # name -> 0 when the operation Succeeded at the deploy commit and the app is Healthy
  local n="$1" attempt=1 deadline phase oprev srev health started before
  while :; do
    deadline=$(( $(now) + TIMEOUT ))
    # The operation already on the Application (an earlier sync, a failed first attempt) must never be mistaken for ours:
    # note its start time, and accept a result only from an operation that started after the patch.
    read -r phase oprev srev health before <<<"$(app_status "$n")"
    until k -n argocd patch application "app-$n" --type merge -p "$SYNC_PATCH" >/dev/null 2>&1; do
      if [ "$(now)" -ge "$deadline" ]; then fail "app-$n: the sync could not be started (no such Application yet?)"; return 1; fi
      sleep "$POLL"
    done
    while :; do
      read -r phase oprev srev health started <<<"$(app_status "$n")"
      if [ "$oprev" = "$COMMIT" ] && [ "$started" != "-" ] && [ "$started" != "$before" ]; then
        case "$phase" in
          Succeeded) break 2 ;;
          Failed|Error)
            if [ "$attempt" -eq 1 ]; then attempt=2; sleep "$POLL"; continue 2; fi
            fail "app-$n: the sync operation ${phase} (a PreSync migration or a manifest was rejected); see: kubectl --context ${CTX} -n argocd get application app-$n -o yaml"
            return 1 ;;
        esac
      fi
      if [ "$(now)" -ge "$deadline" ]; then fail "app-$n: the sync operation did not start or finish within ${TIMEOUT}s (phase ${phase}; started ${started}, before ${before})"; return 1; fi
      sleep "$POLL"
    done
  done
  deadline=$(( $(now) + TIMEOUT ))
  while :; do
    read -r phase oprev srev health started <<<"$(app_status "$n")"
    [ "$health" = "Healthy" ] && return 0
    if [ "$(now)" -ge "$deadline" ]; then fail "app-$n is ${health}, not Healthy, ${TIMEOUT}s after its sync"; return 1; fi
    sleep "$POLL"
  done
}

wait_cluster() { # <namespace>/<name>: the Cluster object may not exist for a few seconds after the sync
  local deadline=$(( $(now) + TIMEOUT ))
  until k -n "${1%%/*}" wait --for=condition=Ready "cluster/${1#*/}" --timeout=20s >/dev/null 2>&1; do
    if [ "$(now)" -ge "$deadline" ]; then fail "database cluster ${1} is not Ready after ${TIMEOUT}s"; return 1; fi
    sleep "$POLL"
  done
}

while IFS=$'\t' read -r -u 3 name _img _ctx _dockerfile wait _host _checks; do
  if sync_app "$name"; then
    case "$wait" in
      cnpg-cluster:*) wait_cluster "${wait#cnpg-cluster:}" || true ;;
    esac
  fi
done 3<<<"$plan"

# 8. Verify the running state, never the Synced label.
verify_pods() { # <name> <expected tag> -> prints one problem per line
  k -n "$1" get pods -o json 2>/dev/null | python3 -c '
import json, sys
name, tag, reg = sys.argv[1:4]
repo = "%s/%s" % (reg, name)
try:
    items = json.load(sys.stdin).get("items", [])
except ValueError:
    print("could not read the pods of namespace %s" % name); sys.exit(0)
seen = 0
for p in items:
    meta, st = p.get("metadata", {}), p.get("status", {})
    images = [c.get("image", "") for c in p.get("spec", {}).get("containers", [])]
    if not any(i.startswith(repo + ":") for i in images):
        continue
    if st.get("phase") in ("Succeeded",) or meta.get("deletionTimestamp"):
        continue  # a finished migration Job pod, or an old pod on its way out
    seen += 1
    pn = meta.get("name", "?")
    for i in images:
        if i.startswith(repo + ":") and i != "%s:%s" % (repo, tag):
            print("pod %s runs image %s, not %s:%s" % (pn, i, repo, tag))
    ready = [c for c in st.get("conditions", []) if c.get("type") == "Ready"]
    if not ready or ready[0].get("status") != "True":
        print("pod %s is not ready" % pn)
    n = sum(c.get("restartCount", 0) for c in st.get("containerStatuses", []))
    if n:
        print("pod %s restarted %d time(s)" % (pn, n))
if not seen:
    print("no pods run %s:%s" % (repo, tag))' "$1" "$2" "$REG"
}

gateway_code() { # <host> <path>
  curl -sS -o /dev/null -w '%{http_code}' --max-time 10 -H "Host: $1" "http://127.0.0.1:8080$2" 2>/dev/null || true
}

while IFS=$'\t' read -r -u 3 name img _ctx _dockerfile _wait host checks; do
  read -r phase oprev srev health started <<<"$(app_status "$name")"
  [ "$phase" = "Succeeded" ] || fail "app-$name: the last sync operation is ${phase}, not Succeeded"
  [ "$oprev" = "$COMMIT" ] || fail "app-$name: the synced revision is ${oprev}, not the deploy commit ${COMMIT}"
  [ "$srev" = "$COMMIT" ] || fail "app-$name: the Application's revision is ${srev}, not the deploy commit ${COMMIT}"
  [ "$health" = "Healthy" ] || fail "app-$name: health is ${health}, not Healthy"
  if [ "$img" = "1" ]; then
    want_tag="$(git show "${COMMIT}:infra/k8s/apps/${name}/values-local.yaml" | python3 -c '
import re, sys
m = re.search(r"(?m)^\s*tag:\s*[\"\x27]?([^\"\x27\s#]+)", sys.stdin.read())
print(m.group(1) if m else "")')"
    deadline=$(( $(now) + TIMEOUT ))
    while :; do
      problems="$(verify_pods "$name" "$want_tag")"
      [ -z "$problems" ] && break
      if [ "$(now)" -ge "$deadline" ]; then
        while IFS= read -r p; do fail "app-$name: $p"; done <<<"$problems"
        break
      fi
      sleep "$POLL"
    done
  fi
  if [ "$host" != "-" ] && [ "$checks" != "-" ]; then
    IFS=',' read -r -a paths <<<"$checks"
    for path in "${paths[@]}"; do
      deadline=$(( $(now) + (TIMEOUT < 90 ? TIMEOUT : 90) ))
      while :; do
        code="$(gateway_code "$host" "$path")"
        [ "$code" = "200" ] && break
        if [ "$(now)" -ge "$deadline" ]; then fail "check http://${host}:8080${path} answered ${code:-nothing}, not 200"; break; fi
        sleep "$POLL"
      done
    done
  fi
done 3<<<"$plan"

if [ "$CHECK_GIVEN" -eq 1 ]; then
  printf '%s' "$CHECKS" | python3 "$ROOT/scripts/post_deploy_check.py" "$PROJECT" || fail "the --check lines failed (see the FAILED lines above)"
fi

# 9. The verdict.
if [ -z "$FAILS" ]; then
  echo "verified (local): ${NAMES} at ${TAG} ($(git rev-parse --short "$COMMIT"))"
  exit 0
fi
first="$(printf '%s' "$FAILS" | head -n 1)"
echo "NOT verified: ${first}"
printf '%s' "$FAILS" | tail -n +2 | sed 's/^/  also: /'
if [ -n "$PREV" ]; then
  echo "roll back: scripts/deploy_local.sh ${PROJECT} --revision ${PREV} --no-build"
else
  echo "no earlier local deploy to roll back to: fix forward and deploy again"
fi
exit 1
