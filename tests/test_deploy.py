"""Step 10: the local deploy script, the release-evidence check and the deploy skill.

The script runs against a real temporary git repository with `kubectl`, `docker` and `curl` replaced by logging stubs
on PATH (rules in a JSON file), so the whole sequence, the refusals and every verification failure are exercised
without a cluster. The real-cluster proof is in the task report.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import signal
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PACK = PLUGIN / "stacks/nextjs-fastapi/files"
DEPLOY = PACK / "scripts/deploy_local.sh"
RELEASE = PACK / "scripts/release_check.py"
CHECKER = PACK / "scripts/post_deploy_check.py"
DEPLOY_JSON = PACK / "infra/local-deploy.json"
PUSH = PLUGIN / "scripts/local-cluster/push.sh"
SKILL = PLUGIN / "skills/deploy/SKILL.md"
SOURCES = PLUGIN / "skills/deploy/references/sources.md"
PAGE = ROOT / "docs/steps/10-deploy.md"

STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, re, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
_envf = pathlib.Path(sys.argv[0]).with_name("stub_env.json")
if _envf.exists():
    for _k, _v in json.loads(_envf.read_text()).items():
        os.environ.setdefault(_k, _v)
d = pathlib.Path(os.environ["STUB_DIR"])
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(name + " " + " ".join(args) + "\n")
line = " ".join(args)
if name == "kubectl" and args[:2] == ["config", "current-context"]:
    print(os.environ.get("STUB_CONTEXT", "kind-pavedline-ci")); sys.exit(0)
if name == "docker":
    if args[:1] == ["build"] and "-t" in args:
        (d / "tag").write_text(args[args.index("-t") + 1].rsplit(":", 1)[1])
    sys.exit(0)
if name == "kubectl" and args and "apply" in args:
    n = len(list(d.glob("applied-*.yaml")))
    (d / ("applied-%d.yaml" % n)).write_text(sys.stdin.read())
    sys.exit(0)
if name == "kubectl" and "patch" in args and "-p" in args:
    body = json.loads(args[args.index("-p") + 1])
    rev = body.get("operation", {}).get("sync", {}).get("revision")
    if rev:
        (d / "rev").write_text(rev)
    (d / "patches").write_text(str(int((d / "patches").read_text() if (d / "patches").exists() else 0) + 1))
    print("patched"); sys.exit(0)
rules = json.loads((d / "rules.json").read_text())
rev = (d / "rev").read_text() if (d / "rev").exists() else "none"
tag = (d / "tag").read_text() if (d / "tag").exists() else "none"
started = "2026-01-01T00:00:%02dZ" % int((d / "patches").read_text() if (d / "patches").exists() else 0)
for r in rules:
    if r["match"] in line and r.get("tool", name) == name:
        if r.get("sleep"):
            import time; time.sleep(r["sleep"])
        sys.stdout.write(r.get("stdout", "").replace("{REV}", rev).replace("{TAG}", tag).replace("{STARTED}", started))
        sys.exit(r.get("rc", 0))
sys.exit(0)
'''

GH_STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
d = pathlib.Path(os.environ["STUB_DIR"])
with open(os.environ["STUB_LOG"], "a") as f:
    f.write("gh " + " ".join(args) + "\n")
line = " ".join(args)
for r in json.loads((d / "gh.json").read_text()):
    if r["match"] in line:
        sys.stdout.write(r["stdout"])
        sys.exit(r.get("rc", 0))
sys.stderr.write("no stub for: " + line + "\n")
sys.exit(1)
'''

APPSET = """apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: %s
spec:
  generators:
    - git:
        repoURL: '{{REPO_URL}}'
        revision: '{{REVISION}}'
  template:
    spec:
      source:
        helm:
          valueFiles: ['values-{{ENVIRONMENT}}.yaml']
"""

MINI = {
    "version": 1,
    "apps": [
        {"name": "postgres", "surface": "api", "image": None, "wait": "cnpg-cluster:postgres/db", "host": None, "checks": []},
        {"name": "api", "surface": "api", "image": {"context": "services/api", "dockerfile": "services/api/Dockerfile"},
         "wait": "rollout", "host": "api.localtest.me", "checks": ["/healthz", "/readyz"]},
        {"name": "web", "surface": "web", "image": {"context": ".", "dockerfile": "apps/web/Dockerfile"},
         "wait": "rollout", "host": "app.localtest.me", "checks": ["/healthz", "/"]},
    ],
}


def app_json(**over):
    st = {"operationState": {"phase": "Succeeded", "startedAt": "{STARTED}", "syncResult": {"revision": "{REV}"}},
          "sync": {"status": "Synced", "revision": "{REV}"}, "health": {"status": "Healthy"}}
    st.update(over)
    return json.dumps({"status": st})


def pods_json(repo, tag="{TAG}", restarts=0, ready="True", extra=None):
    pod = {"metadata": {"name": repo + "-1"},
           "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": ready}],
                      "containerStatuses": [{"restartCount": restarts}]},
           "spec": {"containers": [{"image": "localhost:5001/%s:%s" % (repo, tag)}]}}
    return json.dumps({"items": [pod] + (extra or [])})


def sh(cmd, cwd, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError("%s failed: %s" % (cmd, r.stderr))
    return r


class DeployCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pl-deploy-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "product"
        self.bin = self.tmp / "bin"
        self.stub = self.tmp / "stub"
        self.lc = self.tmp / "lc"
        for p in (self.repo, self.bin, self.stub, self.lc):
            p.mkdir()
        self.log = self.tmp / "log.txt"
        self.log.write_text("")
        for n in ("kubectl", "docker", "curl"):
            (self.bin / n).write_text(STUB)
            (self.bin / n).chmod(0o755)
        (self.bin / "stub_env.json").write_text(json.dumps({"STUB_LOG": str(self.log), "STUB_DIR": str(self.stub), "STUB_CONTEXT": "kind-pavedline-ci"}))
        (self.lc / "push.sh").write_text('#!/bin/sh\necho "push.sh $*" >> "$STUB_LOG"\n')
        (self.lc / "push.sh").chmod(0o755)
        (self.lc / "versions.env").write_text("REGISTRY_PORT=5001\n")
        # the product
        r = self.repo
        (r / "scripts").mkdir()
        shutil.copy(DEPLOY, r / "scripts/deploy_local.sh")
        shutil.copy(CHECKER, r / "scripts/post_deploy_check.py")
        (r / "scripts/local_secrets.sh").write_text('#!/bin/sh\necho "local_secrets.sh $*" >> "$STUB_LOG"\n')
        (r / "scripts/local_secrets.sh").chmod(0o755)
        (r / "infra/k8s/applicationsets").mkdir(parents=True)
        for n in ("addons", "apps"):
            (r / "infra/k8s/applicationsets" / (n + ".yaml")).write_text(APPSET % n)
        (r / "infra/k8s/addons/gateway").mkdir(parents=True)
        (r / "infra/k8s/addons/gateway/gateway.yaml").write_text("kind: Gateway\n")
        (r / "infra/local-deploy.json").write_text(json.dumps(MINI, indent=2))
        for app in ("postgres", "api", "web"):
            (r / "infra/k8s/apps" / app).mkdir(parents=True)
            if app == "postgres":
                (r / "infra/k8s/apps/postgres/values-local.yaml").write_text("cluster:\n  instances: 1\n")
            else:
                (r / "infra/k8s/apps" / app / "values-local.yaml").write_text(
                    "workloads:\n  %s:\n    image:\n      repository: localhost:5001/%s\n      tag: \"local-0001\"\n    replicas: 1\n" % (app, app))
        self.env = dict(os.environ)
        self.env.update({
            "PATH": "%s:%s" % (self.bin, os.environ["PATH"]), "STUB_LOG": str(self.log), "STUB_DIR": str(self.stub),
            "STUB_CONTEXT": "kind-pavedline-ci", "PAVEDLINE_LOCAL_CLUSTER_DIR": str(self.lc),
            "PAVEDLINE_POLL_SECONDS": "0", "PAVEDLINE_DEPLOY_TIMEOUT": "2",
            "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        })
        sh(["git", "init", "-q", "-b", "main"], r, self.env)
        sh(["git", "add", "-A"], r, self.env)
        sh(["git", "commit", "-q", "-m", "init"], r, self.env)
        self.set_rules()

    # ---- helpers
    def set_rules(self, **over):
        apps = {"postgres": app_json(), "api": app_json(), "web": app_json()}
        pods = {"api": pods_json("api"), "web": pods_json("web")}
        codes = {}
        extra = []
        for k, v in over.items():
            if k.startswith("kind_"):
                extra.append({"tool": "kubectl", "match": "get " + k[5:], "stdout": v})
            elif k.startswith("app_"):
                apps[k[4:]] = v
            elif k.startswith("pods_"):
                pods[k[5:]] = v
            elif k.startswith("code_"):
                codes[k[5:]] = v
        rules = [{"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"},
                 {"tool": "kubectl", "match": "get nodes", "stdout": over.get("nodes", "node/pavedline-ci-control-plane\n")},
                 {"tool": "kubectl", "match": "get applications", "stdout": json.dumps({"items": [
            {"metadata": {"name": "addon-gateway"}, "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}}}]})}]
        for n, v in apps.items():
            rules.append({"tool": "kubectl", "match": "get application app-%s -o" % n, "stdout": v})
        for n, v in pods.items():
            rules.append({"tool": "kubectl", "match": "-n %s get pods -o" % n, "stdout": v})
        for key, code in codes.items():
            rules.append({"tool": "curl", "match": key, "stdout": code})
        rules.extend(extra)
        rules.append({"tool": "curl", "match": "127.0.0.1:8080", "stdout": "200"})
        (self.stub / "rules.json").write_text(json.dumps(rules))

    def run_deploy(self, *args, cwd=None, env=None):
        return subprocess.run(["bash", str(self.repo / "scripts/deploy_local.sh"), *args],
                              cwd=cwd or self.repo, env=env or self.env, capture_output=True, text=True)

    def log_lines(self):
        return self.log.read_text().splitlines()

    def git(self, *a):
        return sh(["git", *a], self.repo, self.env).stdout.strip()

    def deploy_commit(self):
        return self.git("rev-parse", "refs/pavedline/local-deploy/ci")


class Refusals(DeployCase):
    def test_other_context_refused_before_anything_else(self):
        for ctx in ("docker-desktop", "kind-pavedline-other", "prod-cluster"):
            self.log.write_text("")
            self.env["STUB_CONTEXT"] = ctx
            r = self.run_deploy("ci")
            self.assertEqual(r.returncode, 2, ctx)
            self.assertIn("kind-pavedline-ci", r.stderr)
            self.assertEqual(self.log_lines(), ["kubectl config current-context"], ctx)

    def test_bad_project_name(self):
        for bad in ("Bad_Name", "a;b", "../x"):
            self.log.write_text("")
            r = self.run_deploy(bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertEqual(self.log_lines(), [], bad)

    def test_usage_errors(self):
        self.assertEqual(self.run_deploy().returncode, 2)
        self.assertEqual(self.run_deploy("ci", "--nope").returncode, 2)
        self.assertEqual(self.run_deploy("ci", "--no-build").returncode, 2)  # needs --revision
        self.assertEqual(self.run_deploy("ci", "--apps", "ghost").returncode, 2)

    def test_untracked_files_do_not_block(self):
        (self.repo / "untracked.txt").write_text("x")
        r = self.run_deploy("ci")
        self.assertNotIn("deploy what is committed", r.stderr)

    def test_staged_tracked_change_refused(self):
        (self.repo / "infra/k8s/apps/web/values-local.yaml").write_text("staged\n")
        self.git("add", "infra/k8s/apps/web/values-local.yaml")
        r = self.run_deploy("ci")
        self.assertEqual(r.returncode, 1)
        self.assertIn("deploy what is committed", r.stderr)
        self.assertFalse([ln for ln in self.log_lines() if ln.startswith(("docker", "push.sh"))])

    def test_modified_tracked_file_refused(self):
        (self.repo / "infra/k8s/apps/web/values-local.yaml").write_text("changed\n")
        self.assertEqual(self.run_deploy("ci").returncode, 1)

    def test_missing_local_cluster_scripts(self):
        env = dict(self.env)
        del env["PAVEDLINE_LOCAL_CLUSTER_DIR"]
        r = self.run_deploy("ci", env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("local-cluster", r.stderr)
        self.assertFalse([ln for ln in self.log_lines() if ln.startswith("docker")])

    def test_product_local_cluster_dir_is_used_first(self):
        (self.repo / "scripts/local-cluster").mkdir()
        (self.repo / "scripts/local-cluster/push.sh").write_text('#!/bin/sh\necho "product push.sh $*" >> "$STUB_LOG"\n')
        (self.repo / "scripts/local-cluster/push.sh").chmod(0o755)
        sh(["git", "add", "-A"], self.repo, self.env)
        sh(["git", "commit", "-q", "-m", "lc"], self.repo, self.env)
        r = self.run_deploy("ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue([ln for ln in self.log_lines() if ln.startswith("product push.sh")])
        self.assertFalse([ln for ln in self.log_lines() if ln.startswith("push.sh")])


class Sequence(DeployCase):
    def test_full_deploy_verifies(self):
        head = self.git("rev-parse", "HEAD")
        status = self.git("status", "--porcelain")
        branch_before = self.git("rev-parse", "main")
        index_before = self.git("write-tree")
        r = self.run_deploy("ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        m = re.search(r"verified \(local\): (.+) at (\S+) \((\w+)\)", r.stdout)
        self.assertTrue(m, r.stdout)
        self.assertEqual(m.group(1), "postgres, api, web")
        tag = m.group(2)
        self.assertRegex(tag, r"^%s-\d+$" % head[:7])
        # the developer's branch, index and working tree are untouched
        self.assertEqual(self.git("rev-parse", "main"), branch_before)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("write-tree"), index_before)
        self.assertEqual(self.git("status", "--porcelain"), status)
        self.assertIn('"local-0001"', (self.repo / "infra/k8s/apps/api/values-local.yaml").read_text())
        # the deploy commit: parent HEAD, tree = HEAD + the two tag bumps, subject local deploy <tag>
        dc = self.deploy_commit()
        self.assertEqual(self.git("rev-parse", dc + "^"), head)
        self.assertEqual(self.git("log", "-1", "--format=%s", dc), "local deploy " + tag)
        self.assertNotRegex(self.git("log", "-1", "--format=%B", dc).lower(), r"skip ci|ci skip|no ci|skip actions|actions skip|no_ci")
        changed = sorted(self.git("diff", "--name-only", head, dc).splitlines())
        self.assertEqual(changed, ["infra/k8s/apps/api/values-local.yaml", "infra/k8s/apps/web/values-local.yaml"])
        for app in ("api", "web"):
            self.assertIn('tag: "%s"' % tag, self.git("show", "%s:infra/k8s/apps/%s/values-local.yaml" % (dc, app)))
        self.assertTrue(m.group(3).startswith(dc[:len(m.group(3))]))

    def test_calls(self):
        r = self.run_deploy("ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.log_lines()
        dc = self.deploy_commit()
        self.assertEqual(lines[0], "kubectl config current-context")
        builds = [ln for ln in lines if ln.startswith("docker build")]
        self.assertEqual(len(builds), 2)
        self.assertTrue(any(re.search(r"-f \S+services/api/Dockerfile -t localhost:5001/api:\S+ \S+services/api$", b) for b in builds), builds)
        self.assertTrue(any(re.search(r"-f \S+apps/web/Dockerfile -t localhost:5001/web:\S+ \S+$", b) for b in builds), builds)
        self.assertEqual(len([ln for ln in lines if ln.startswith("docker push localhost:5001/")]), 2)
        self.assertIn("push.sh ci %s" % dc, lines)
        self.assertIn("local_secrets.sh ci", lines)
        # every kubectl call but the context read names the kind context explicitly
        for ln in lines:
            if ln.startswith("kubectl ") and not ln.startswith("kubectl config current-context"):
                self.assertIn("--context kind-pavedline-ci", ln)
        # push happens before the secrets, the applicationsets and the syncs
        idx = {k: i for i, k in enumerate(lines)}
        self.assertLess(lines.index("push.sh ci %s" % dc), lines.index("local_secrets.sh ci"))
        patches = [ln for ln in lines if " patch application " in ln]
        self.assertEqual([re.search(r"application (app-\w+)", p).group(1) for p in patches], ["app-postgres", "app-api", "app-web"])
        for p in patches:
            self.assertIn('"syncOptions":["CreateNamespace=true"]', p.replace(" ", ""))
            self.assertIn(dc, p)
        self.assertLess(lines.index("local_secrets.sh ci"), lines.index(patches[0]))
        self.assertTrue([ln for ln in lines if "-n postgres wait --for=condition=Ready cluster/db" in ln])
        self.assertTrue(idx)

    def test_applicationsets_are_rendered(self):
        self.assertEqual(self.run_deploy("ci").returncode, 0)
        applied = sorted(p.read_text() for p in self.stub.glob("applied-*.yaml"))
        self.assertEqual(len(applied), 2)
        for text in applied:
            self.assertNotIn("{{REPO_URL}}", text)
            self.assertIn("git://kind-git:9418/ci.git", text)
            self.assertIn("revision: 'main'", text)
        self.assertTrue(any("values-local.yaml" in t for t in applied))
        self.assertTrue(all("{{ENVIRONMENT}}" not in t for t in applied))

    def test_apps_filter_and_carry_over(self):
        self.assertEqual(self.run_deploy("ci").returncode, 0)
        first = self.deploy_commit()
        first_api = self.git("show", first + ":infra/k8s/apps/api/values-local.yaml")
        self.log.write_text("")
        r = self.run_deploy("ci", "--apps", "web")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.log_lines()
        builds = [ln for ln in lines if ln.startswith("docker build")]
        self.assertEqual(len(builds), 1)
        self.assertIn("localhost:5001/web:", builds[0])
        patches = [ln for ln in lines if " patch application " in ln]
        self.assertEqual(len(patches), 1)
        self.assertIn("app-web", patches[0])
        second = self.deploy_commit()
        self.assertNotEqual(first, second)
        self.assertNotEqual(self.git("show", first + ":infra/k8s/apps/web/values-local.yaml"),
                            self.git("show", second + ":infra/k8s/apps/web/values-local.yaml"))
        # the api tag of the earlier deploy is carried, not reset to local-0001
        self.assertEqual(self.git("show", second + ":infra/k8s/apps/api/values-local.yaml"), first_api)
        self.assertIn("verified (local): web at", r.stdout)

    def test_tags_are_never_reused(self):
        tags = []
        for _ in range(2):
            r = self.run_deploy("ci", "--apps", "web")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            tags.append(re.search(r" at (\S+) \(", r.stdout).group(1))
        self.assertNotEqual(tags[0], tags[1])

    def test_rollback_revision_without_build(self):
        self.assertEqual(self.run_deploy("ci").returncode, 0)
        first = self.deploy_commit()
        self.assertEqual(self.run_deploy("ci", "--apps", "web").returncode, 0)
        self.log.write_text("")
        (self.stub / "tag").write_text(self.git("log", "-1", "--format=%s", first).replace("local deploy ", ""))
        r = self.run_deploy("ci", "--revision", first, "--no-build")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse([ln for ln in self.log_lines() if ln.startswith("docker")])
        self.assertIn("push.sh ci %s" % first, self.log_lines())
        self.assertIn("verified (local)", r.stdout)

    def test_revision_must_be_a_commit(self):
        r = self.run_deploy("ci", "--revision", "deadbeef", "--no-build")
        self.assertEqual(r.returncode, 2)


class Verification(DeployCase):
    def fails(self, needle, **rules):
        self.set_rules(**rules)
        r = self.run_deploy("ci")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("NOT verified", r.stdout + r.stderr)
        self.assertNotIn("verified (local)", r.stdout)
        self.assertIn(needle, r.stdout + r.stderr)
        return r

    def test_restart_count(self):
        self.fails("restart", pods_api=pods_json("api", restarts=1))

    def test_wrong_image(self):
        self.fails("image", pods_web=pods_json("web", tag="local-0001"))

    def test_old_pod_still_running(self):
        old = {"metadata": {"name": "web-old"}, "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}],
               "containerStatuses": [{"restartCount": 0}]}, "spec": {"containers": [{"image": "localhost:5001/web:old"}]}}
        self.fails("image", pods_web=pods_json("web", extra=[old]))

    def test_not_ready(self):
        self.fails("ready", pods_api=pods_json("api", ready="False"))

    def test_no_pods(self):
        self.fails("no pods", pods_api=json.dumps({"items": []}))

    def test_wrong_revision(self):
        self.fails("revision", app_web=app_json(sync={"status": "Synced", "revision": "deadbeef"}))

    def test_failed_operation(self):
        self.fails("app-api", app_api=app_json(operationState={"phase": "Failed", "syncResult": {"revision": "{REV}"}}))

    def test_check_not_200(self):
        self.fails("/readyz", **{"code_Host: api.localtest.me http://127.0.0.1:8080/readyz": "503"})

    def test_user_check_fails(self):
        self.set_rules(**{"kind_deployment/web": "0"})
        r = self.run_deploy("ci", "--check", "kubectl-get web deployment/web --jsonpath={.status.readyReplicas} --equals=1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT verified", r.stdout + r.stderr)
        self.assertIn("--check", r.stdout + r.stderr)

    def test_user_check_passes(self):
        self.set_rules(**{"kind_deployment/web": "1"})
        r = self.run_deploy("ci", "--check", "kubectl-get web deployment/web --jsonpath={.status.readyReplicas} --equals=1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_injection_is_rejected_before_anything_runs(self):
        marker = self.tmp / "pwned"
        for bad in ("true; touch %s" % marker, "$(touch %s)" % marker, "`touch %s`" % marker, "false", "",
                    "http x.example.com / 200", "kubectl-get default secret/foo"):
            self.log.write_text("")
            r = self.run_deploy("ci", "--check", bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("rejected check", r.stderr, bad)
            self.assertFalse(marker.exists(), bad)
            self.assertFalse([ln for ln in self.log_lines() if ln.startswith(("docker", "push.sh", "git"))], bad)

    def test_checks_never_run_through_a_shell(self):
        self.assertNotIn("bash -c", DEPLOY.read_text())
        self.assertNotIn("eval ", DEPLOY.read_text())

    def test_failure_prints_the_rollback_command(self):
        self.assertEqual(self.run_deploy("ci").returncode, 0)
        good = self.deploy_commit()
        self.set_rules(pods_api=pods_json("api", restarts=3))
        r = self.run_deploy("ci", "--apps", "api")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--revision %s --no-build" % good, r.stdout + r.stderr)

    def test_hits_gateway_with_host_header(self):
        self.assertEqual(self.run_deploy("ci").returncode, 0)
        curls = [ln for ln in self.log_lines() if ln.startswith("curl ")]
        for host, path in (("api.localtest.me", "/healthz"), ("api.localtest.me", "/readyz"),
                           ("app.localtest.me", "/healthz"), ("app.localtest.me", "/")):
            self.assertTrue(any("Host: %s" % host in c and c.endswith("http://127.0.0.1:8080" + path) for c in curls), (host, path))


class NodeCheckAndStaleState(DeployCase):
    def test_context_must_point_at_the_kind_node(self):
        for nodes in ("node/some-prod-node\n", "", "node/pavedline-other-control-plane\n"):
            self.log.write_text("")
            self.set_rules(nodes=nodes)
            r = self.run_deploy("ci")
            self.assertEqual(r.returncode, 2, nodes)
            self.assertIn("pavedline-ci-control-plane", r.stderr)
            self.assertEqual(self.log_lines()[0], "kubectl config current-context")
            self.assertFalse([ln for ln in self.log_lines() if ln.startswith(("docker", "push.sh"))])
            self.assertTrue(all(ln.startswith("kubectl") for ln in self.log_lines()), self.log_lines())

    def test_a_stale_succeeded_operation_is_never_accepted(self):
        stale = app_json(operationState={"phase": "Succeeded", "startedAt": "2020-01-01T00:00:00Z",
                                         "syncResult": {"revision": "{REV}"}})
        self.set_rules(app_web=stale)
        r = self.run_deploy("ci", "--apps", "web")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("NOT verified", r.stdout)
        self.assertIn("did not start", r.stdout)

    def test_redeploy_of_the_same_revision_waits_for_a_newer_operation(self):
        self.assertEqual(self.run_deploy("ci").returncode, 0)
        first = self.deploy_commit()
        (self.stub / "tag").write_text(self.git("log", "-1", "--format=%s", first).replace("local deploy ", ""))
        r = self.run_deploy("ci", "--revision", first, "--no-build")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PostDeployChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pl-pdc-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (self.tmp / "stub").mkdir()
        (self.tmp / "log.txt").write_text("")
        (bin_ / "kubectl").write_text(STUB)
        (bin_ / "kubectl").chmod(0o755)
        (bin_ / "stub_env.json").write_text(json.dumps({"STUB_LOG": str(self.tmp / "log.txt"), "STUB_DIR": str(self.tmp / "stub")}))
        (self.tmp / "stub/rules.json").write_text(json.dumps([
            {"tool": "kubectl", "match": "get deployment/web", "stdout": "1"},
            {"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"}]))
        self.env = dict(os.environ, PATH="%s:%s" % (bin_, os.environ["PATH"]), SECRET_TOKEN="topsecret")

    def run_check(self, *lines, validate=False):
        cmd = [sys.executable, str(CHECKER), "ci", "--retries", "1"] + (["--validate-only"] if validate else [])
        return subprocess.run(cmd, input="\n".join(lines) + "\n", env=self.env, capture_output=True, text=True)

    def test_valid_lines(self):
        for line in ("http app.localtest.me /healthz 200", "http api.localhost /readyz 200",
                     "kubectl-get web deployment/web", "kubectl-get web pod --jsonpath={.items[0].status.phase} --equals=Running",
                     "kubectl-get postgres cluster/db", "kubectl-get api httproute", "kubectl-get api job", "kubectl-get api configmap/x",
                     "kubectl-get api service/app-api-api"):
            r = self.run_check(line, validate=True)
            self.assertEqual(r.returncode, 0, line + r.stderr)

    def test_log_event_lines(self):
        for line in ("log-event api api request.unhandled_error", "log-event web web-app job.created_now"):
            r = self.run_check(line, validate=True)
            self.assertEqual(r.returncode, 0, line + r.stderr)
        for line in ("log-event api api JobCreated", "log-event api api job", "log-event Bad_NS api job.created",
                     "log-event api api/x job.created", "log-event api api job.created extra", "log-event api api",
                     "log-event api api job.created;id", "log-event api api $(id)"):
            r = self.run_check(line, validate=True)
            self.assertEqual(r.returncode, 2, line)
            self.assertIn("rejected check", r.stderr, line)

    def test_log_event_passes_on_a_matching_json_line(self):
        (self.tmp / "stub/rules.json").write_text(json.dumps([
            {"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"},
            {"tool": "kubectl", "match": "logs deployment/api", "stdout": 'plain text\n{"event": "webhook.accepted", "provider": "stripe"}\n'}]))
        r = self.run_check("log-event api api webhook.accepted")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = (self.tmp / "log.txt").read_text()
        self.assertIn("--context kind-pavedline-ci -n api logs deployment/api --all-pods=true --since=15m", log)
        self.assertIn("--limit-bytes=5000000", log)

    def test_log_event_timeout_is_reported_not_a_traceback(self):
        (self.tmp / "stub/rules.json").write_text(json.dumps([
            {"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"},
            {"tool": "kubectl", "match": "logs deployment/api", "stdout": "", "sleep": 30}]))
        self.env["PAVEDLINE_CHECK_TIMEOUT"] = "2"
        start = time.time()
        r = self.run_check("log-event api api webhook.accepted")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertLess(time.time() - start, 20)
        self.assertIn("timed out", r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_log_event_reads_lines_with_the_all_pods_prefix(self):
        (self.tmp / "stub/rules.json").write_text(json.dumps([
            {"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"},
            {"tool": "kubectl", "match": "logs deployment/api",
             "stdout": '[pod/api-7d9f-abc/api] {"event": "other.thing"}\n[pod/api-7d9f-xyz/api] {"event": "webhook.accepted"}\n'}]))
        r = self.run_check("log-event api api webhook.accepted")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_log_event_fails_without_printing_the_logs(self):
        (self.tmp / "stub/rules.json").write_text(json.dumps([
            {"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"},
            {"tool": "kubectl", "match": "logs deployment/api", "stdout": '{"event": "other.thing", "token": "SENTINEL"}\nnot json\n'}]))
        r = self.run_check("log-event api api webhook.accepted")
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("has event webhook.accepted", out)
        self.assertNotIn("SENTINEL", out)
        self.assertNotIn("other.thing", out)

    def test_rejected_lines(self):
        marker = self.tmp / "x"
        bad = ["", "true", "echo hi", "http x.example.com / 200", "http app.localtest.me.evil.com / 200", "http app.localtest.me healthz 200",
               "http app.localtest.me /a;b 200", "http app.localtest.me / 20", "kubectl-get default secret/foo", "kubectl-get default secrets",
               "kubectl-get default node", "kubectl-get default pod -o yaml", "kubectl-get default pod --token=x",
               "kubectl-get default pod --jsonpath={.a}|cat", "kubectl-get default pod/$(id)", "kubectl-get Bad_NS pod",
               "kubectl-get default pod --equals=x", "kubectl-get default pod; touch %s" % marker, "kubectl-get default pod `id`",
               "kubectl-get default pod > %s" % marker, "kubectl-get default pod &", "kubectl-get default pod\\n", "sql-count a/b t = 1",
               "http app.localtest.me / 200 extra", "kubectl-get default pod --context=prod"]
        for line in bad:
            r = self.run_check(line, validate=True)
            self.assertEqual(r.returncode, 2, repr(line))
            self.assertIn("rejected check", r.stderr, repr(line))
        self.assertFalse(marker.exists())

    def test_one_bad_line_rejects_all_and_runs_nothing(self):
        r = self.run_check("kubectl-get web deployment/web", "true; id")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("get deployment/web", (self.tmp / "log.txt").read_text())

    def test_kubectl_check_runs_with_forced_context_minimal_env_and_temp_kubeconfig(self):
        (self.tmp / "bin/kubectl").write_text(STUB.replace("line = \" \".join(args)", "line = \" \".join(args)\nwith open(os.environ['STUB_LOG'], 'a') as f:\n    f.write('ENV ' + json.dumps(sorted(os.environ)) + ' KUBECONFIG=' + os.environ.get('KUBECONFIG', '') + '\\n')", 1))
        r = self.run_check("kubectl-get web deployment/web --jsonpath={.status.readyReplicas} --equals=1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = (self.tmp / "log.txt").read_text()
        self.assertIn("--context kind-pavedline-ci -n web get deployment/web", log)
        self.assertNotIn("SECRET_TOKEN", log.split("get deployment/web")[1])
        m = re.search(r"KUBECONFIG=(\S+)", log.split("get deployment/web")[1])
        self.assertTrue(m and m.group(1), log)
        self.assertFalse(pathlib.Path(m.group(1)).exists(), "the temp kubeconfig must be deleted")

    def test_equals_mismatch_fails_without_printing_the_observed_value(self):
        r = self.run_check("kubectl-get web deployment/web --jsonpath={.status.readyReplicas} --equals=2")
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("does not equal", out)
        self.assertIn(".status.readyReplicas", out)
        self.assertNotIn("'1'", out)
        self.assertNotRegex(out, r"is '?1'?")

    def test_jsonpath_allow_list(self):
        for bad in ("{.spec.containers[*].env}", "{.data}", "{.metadata.annotations}", "{.stringData}", "{.spec.template.spec}",
                    "{.items[*].spec.containers[0].env}", "{.status}{.data}", "{.metadata.name.x}", "{..env}", "{.status..data}"):
            r = self.run_check("kubectl-get web configmap/x --jsonpath=%s --equals=a" % bad, validate=True)
            self.assertEqual(r.returncode, 2, bad)
        for good in ("{.status.phase}", "{.status.readyReplicas}", "{.items[0].status.phase}", "{.items[*].status.phase}",
                     "{.spec.replicas}", "{.metadata.name}", "{.metadata.labels}", "{.status.conditions[0].status}"):
            r = self.run_check("kubectl-get web pod --jsonpath=%s" % good, validate=True)
            self.assertEqual(r.returncode, 0, good + r.stderr)

    def test_too_many_checks(self):
        ok = "kubectl-get web deployment/web"
        self.assertEqual(self.run_check(*([ok] * 20), validate=True).returncode, 0)
        r = self.run_check(*([ok] * 21), validate=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("too many checks", r.stderr)

    def test_total_time_is_capped(self):
        self.env["PAVEDLINE_CHECK_TIMEOUT"] = "0"
        r = self.run_check("kubectl-get web deployment/web")
        self.assertEqual(r.returncode, 1)
        self.assertIn("checks timed out", r.stdout + r.stderr)

    def test_sigterm_removes_the_temp_files(self):
        (self.tmp / "stub/rules.json").write_text(json.dumps([
            {"tool": "kubectl", "match": "config view", "stdout": "apiVersion: v1\n"},
            {"tool": "kubectl", "match": "get deployment/web", "stdout": "1", "sleep": 30}]))
        tmpdir = self.tmp / "tmpdir"
        tmpdir.mkdir()
        self.env["TMPDIR"] = str(tmpdir)
        for sig in (signal.SIGTERM, signal.SIGHUP):
            p = subprocess.Popen([sys.executable, str(CHECKER), "ci", "--retries", "1"], stdin=subprocess.PIPE, env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p.stdin.write("kubectl-get web deployment/web\n")
            p.stdin.close()
            self.addCleanup(p.stdout.close)
            self.addCleanup(p.stderr.close)
            deadline = time.time() + 10
            while time.time() < deadline and not list(tmpdir.glob("pl-check-*/kubeconfig-*")):
                time.sleep(0.05)
            self.assertTrue(list(tmpdir.glob("pl-check-*/kubeconfig-*")), "the check never started")
            p.send_signal(sig)
            p.wait(timeout=15)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(list(tmpdir.glob("pl-check-*")) + list(tmpdir.glob("pl-home-*")), [], sig)

    def test_http_check(self):
        import http.server
        import threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if self.headers.get("Host") == "app.localtest.me" and self.path == "/healthz" else 404)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.env["PAVEDLINE_GATEWAY_PORT"] = str(srv.server_address[1])
        self.assertEqual(self.run_check("http app.localtest.me /healthz 200").returncode, 0)
        self.assertEqual(self.run_check("http app.localtest.me /nope 200").returncode, 1)
        self.assertEqual(self.run_check("http app.localtest.me /nope 404").returncode, 0)


class Static(unittest.TestCase):
    def setUp(self):
        self.text = DEPLOY.read_text()

    def test_script_shape(self):
        self.assertIn("set -euo pipefail", self.text)
        self.assertIn("CreateNamespace=true", self.text)
        self.assertIn("kind-pavedline-", self.text)
        self.assertIn("commit-tree", self.text)
        self.assertIn("GIT_INDEX_FILE", self.text)
        self.assertIn("deploy what is committed", self.text)
        self.assertIn("verified (local)", self.text)
        self.assertIn("NOT verified", self.text)
        self.assertEqual(subprocess.run(["bash", "-n", str(DEPLOY)], capture_output=True).returncode, 0)
        self.assertNotIn("git commit ", self.text)  # never a commit on the developer's branch
        self.assertNotIn("git add", self.text)
        self.assertNotIn("sudo", self.text)

    def test_refusal_comes_before_any_other_command(self):
        guard = self.text.find("kubectl config current-context")
        self.assertGreater(guard, 0)
        for later in ("git rev-parse --is-inside-work-tree", "git status --porcelain", "docker build", "docker push", "push.sh"):
            self.assertLess(guard, self.text.find(later), later)

    def test_every_kubectl_names_the_context(self):
        for ln in self.text.splitlines():
            s = ln.strip()
            if s.startswith("#") or "kubectl" not in s:
                continue
            if "config current-context" in s or "command -v" in s:
                continue
            self.assertTrue('--context "$CTX"' in s or "k()" in s or s.startswith(("echo", "fail ")) or "error:" in s or "usage" in s, ln)

    def test_environment_is_validated(self):
        self.assertRegex(self.text, r"local\|staging\|production|local\)|ENVIRONMENT")

    def test_local_deploy_json_matches_the_app_folders(self):
        data = json.loads(DEPLOY_JSON.read_text())
        names = [a["name"] for a in data["apps"]]
        folders = sorted(p.name for p in (PACK / "infra/k8s/apps").iterdir() if p.is_dir())
        self.assertEqual(sorted(names), folders)
        self.assertEqual(names[0], "postgres")  # the database first (the API's migration needs it)
        by = {a["name"]: a for a in data["apps"]}
        for a in data["apps"]:
            for k in ("name", "surface", "image", "wait", "host", "checks"):
                self.assertIn(k, a)
        self.assertIsNone(by["postgres"]["image"])
        self.assertTrue(by["postgres"]["wait"].startswith("cnpg-cluster:postgres/"))
        for n in ("api", "web", "site"):
            a = by[n]
            self.assertEqual(a["wait"], "rollout")
            self.assertTrue((PACK / a["image"]["dockerfile"]).is_file(), a)
            self.assertTrue((PACK / a["image"]["context"]).is_dir() or a["image"]["context"] == ".", a)
            self.assertIn("/healthz", a["checks"])
            values = (PACK / "infra/k8s/apps" / n / "values-local.yaml").read_text()
            self.assertIn(a["host"], values)
            self.assertIn('tag: "local-0001"', values)
        self.assertIn("/readyz", by["api"]["checks"])

    def test_surfaces_exist_in_the_pack(self):
        import re as _re
        pack = (PACK.parent / "pack.yaml").read_text()
        surfaces = set(_re.findall(r"^  (\w+):$", pack.split("surfaces:")[1].split("\nshared:")[0], _re.M))
        for a in json.loads(DEPLOY_JSON.read_text())["apps"]:
            self.assertIn(a["surface"], surfaces)

    def test_post_deploy_check_is_in_the_pack_and_executable(self):
        self.assertTrue(os.access(CHECKER, os.X_OK))
        self.assertIn("scripts/post_deploy_check.py", (PACK.parent / "pack.yaml").read_text())
        # apply_stack copies it through the pack.yaml `deploy:` block (no hard-coded list)
        self.assertIn("deploy", (PLUGIN / "scripts/apply_stack.py").read_text())
        pp = (PACK / "services/api/pyproject.toml").read_text()
        self.assertEqual(pp.count("../../scripts/post_deploy_check.py"), 2)

    def test_pack_lists_the_new_files(self):
        pack = (PACK.parent / "pack.yaml").read_text()
        for needle in ("scripts/deploy_local.sh", "scripts/release_check.py", "infra/local-deploy.json"):
            self.assertIn(needle, pack)

    def test_scripts_are_executable(self):
        self.assertTrue(os.access(DEPLOY, os.X_OK))
        self.assertTrue(os.access(RELEASE, os.X_OK))


class PushAcceptsACommit(unittest.TestCase):
    def test_push_sha_to_main(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pl-push-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        bin_ = tmp / "bin"
        bin_.mkdir()
        bare = tmp / "server.git"
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null",
                   GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.com")
        sh(["git", "init", "-q", "--bare", "--initial-branch=main", str(bare)], tmp, env)
        (bin_ / "docker").write_text(
            '#!/bin/sh\ncase "$1" in\n inspect) echo true;;\n exec) shift 3; svc="${1#git-}"; exec git "$svc" "%s";;\nesac\n' % bare)
        (bin_ / "docker").chmod(0o755)
        env["PATH"] = "%s:%s" % (bin_, env["PATH"])
        repo = tmp / "repo"
        repo.mkdir()
        sh(["git", "init", "-q", "-b", "work"], repo, env)
        (repo / "f").write_text("1")
        sh(["git", "add", "f"], repo, env)
        sh(["git", "commit", "-q", "-m", "one"], repo, env)
        first = sh(["git", "rev-parse", "HEAD"], repo, env).stdout.strip()
        (repo / "f").write_text("2")
        sh(["git", "commit", "-q", "-am", "two"], repo, env)
        # a dangling commit (not on any branch), pushed by its sha
        tree = sh(["git", "rev-parse", "HEAD^{tree}"], repo, env).stdout.strip()
        dangling = sh(["git", "commit-tree", tree, "-p", first, "-m", "dangling"], repo, env).stdout.strip()
        r = subprocess.run(["bash", str(PUSH), "demo", dangling], cwd=repo, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sh(["git", "--git-dir", str(bare), "rev-parse", "refs/heads/main"], tmp, env).stdout.strip(), dangling)
        # a branch still works
        r = subprocess.run(["bash", str(PUSH), "demo", "work"], cwd=repo, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sh(["git", "--git-dir", str(bare), "rev-parse", "refs/heads/main"], tmp, env).stdout.strip(),
                         sh(["git", "rev-parse", "work"], repo, env).stdout.strip())
        # an unknown name is refused
        r = subprocess.run(["bash", str(PUSH), "demo", "nope"], cwd=repo, env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
ZERO = "sha256:" + "0" * 64


def values_b64(digest=DIGEST, tag=None):
    import base64
    body = 'workloads:\n  api:\n    image:\n      repository: ghcr.io/o/r/api\n'
    body += '      digest: "%s"\n' % digest
    if tag:
        body += '      tag: "%s"\n' % tag
    return json.dumps({"encoding": "base64", "content": base64.b64encode(body.encode()).decode()})


class ReleaseCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="pl-release-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        (self.tmp / "bin/gh").write_text(GH_STUB)
        (self.tmp / "bin/gh").chmod(0o755)
        self.log = self.tmp / "log.txt"
        self.log.write_text("")
        self.env = dict(os.environ, PATH="%s:%s" % (self.tmp / "bin", os.environ["PATH"]),
                        STUB_LOG=str(self.log), STUB_DIR=str(self.tmp))
        self.product = self.tmp / "product"
        (self.product / "infra/k8s/apps/api").mkdir(parents=True)
        (self.product / "infra/k8s/apps/api/values-staging.yaml").write_text("x: 1\n")
        self.good = {
            "run": [{"name": "ci-api", "status": "completed", "conclusion": "success"}],
            "msg": "Add a thing (#12)\n\nbody",
            "bumps": [{"sha": "c" * 40, "commit": {"message": "chore: api image digest for aaaaaaa"}}],
            "file": values_b64(),
        }

    def gh(self, **over):
        d = dict(self.good)
        d.update(over)
        rules = [
            {"match": "run list", "stdout": json.dumps(d["run"])},
            {"match": "commits/" + SHA, "stdout": json.dumps({"sha": SHA, "commit": {"message": d["msg"]}})},
            {"match": "commits?path=infra/k8s/apps/api/values-staging.yaml", "stdout": json.dumps(d["bumps"])},
            {"match": "contents/infra/k8s/apps/api/values-staging.yaml", "stdout": d["file"]},
        ]
        (self.tmp / "gh.json").write_text(json.dumps(rules))

    def run_check(self, *args):
        return subprocess.run([sys.executable, str(RELEASE), "--sha", SHA, *args], cwd=self.product, env=self.env,
                              capture_output=True, text=True)

    def test_all_hold(self):
        self.gh()
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("release evidence ok", r.stdout)

    def test_repo_is_passed_to_gh(self):
        self.gh()
        r = self.run_check("--repo", "acme/widgets")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("acme/widgets", self.log.read_text())

    def test_no_run(self):
        self.gh(run=[])
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no CI run", r.stdout + r.stderr)

    def test_failed_run(self):
        self.gh(run=[{"name": "ci-api", "status": "completed", "conclusion": "failure"}])
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("failure", r.stdout + r.stderr)

    def test_unfinished_run(self):
        self.gh(run=[{"name": "ci-api", "status": "in_progress", "conclusion": ""}])
        self.assertEqual(self.run_check().returncode, 1)

    def test_only_skipped_runs(self):
        self.gh(run=[{"name": "ci-api", "status": "completed", "conclusion": "skipped"}])
        self.assertEqual(self.run_check().returncode, 1)

    def test_skipped_beside_success_is_fine(self):
        self.gh(run=[{"name": "ci-api", "status": "completed", "conclusion": "success"},
                     {"name": "ci-web", "status": "completed", "conclusion": "skipped"}])
        self.assertEqual(self.run_check().returncode, 0)

    def test_each_skip_marker(self):
        for marker in ("[skip ci]", "[ci skip]", "[no ci]", "[skip actions]", "[actions skip]", "***NO_CI***", "[SKIP CI]"):
            self.gh(msg="Change (#1)\n\nbody %s" % marker)
            r = self.run_check()
            self.assertEqual(r.returncode, 1, marker)
            self.assertIn("skip", (r.stdout + r.stderr).lower(), marker)

    def test_no_bump_commit(self):
        self.gh(bumps=[{"sha": "d" * 40, "commit": {"message": "chore: api image digest for 1234567"}}])
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("bump", r.stdout + r.stderr)

    def test_tag_not_digest(self):
        self.gh(file=json.dumps({"encoding": "base64", "content": __import__("base64").b64encode(
            b'workloads:\n  api:\n    image:\n      repository: r\n      tag: "latest"\n').decode()}))
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("digest", r.stdout + r.stderr)

    def test_placeholder_digest(self):
        self.gh(file=values_b64(ZERO))
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("digest", r.stdout + r.stderr)

    def test_malformed_digest(self):
        self.gh(file=values_b64("sha256:abc"))
        self.assertEqual(self.run_check().returncode, 1)

    def test_tag_beside_digest(self):
        self.gh(file=values_b64(tag="v1"))
        self.assertEqual(self.run_check().returncode, 1)

    def test_all_failures_printed(self):
        self.gh(run=[], msg="x [skip ci]")
        r = self.run_check()
        out = r.stdout + r.stderr
        self.assertIn("no CI run", out)
        self.assertIn("skip", out.lower())

    def test_bad_sha(self):
        r = subprocess.run([sys.executable, str(RELEASE), "--sha", "not-a-sha"], cwd=self.product, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_required_app_without_bump(self):
        self.gh()
        r = self.run_check("--app", "web")
        self.assertEqual(r.returncode, 1)

    def test_gh_failure_is_a_failure(self):
        (self.tmp / "gh.json").write_text(json.dumps([{"match": "", "stdout": "", "rc": 1}]))
        self.assertEqual(self.run_check().returncode, 1)


class DeploySkill(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text()

    def test_files(self):
        self.assertTrue(SKILL.is_file())
        self.assertTrue(SOURCES.is_file())
        self.assertLessEqual(len(self.text.splitlines()), 150)

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: deploy\n"))
        self.assertIn("description:", self.text.split("---")[1])

    def test_needles(self):
        for needle in ("never the Synced label", "verified (local)", "PreSync", "CreateNamespace=true", "release_check.py",
                       "STEP: 11 — Learn", "pavedline:deployer", "deploy_local.sh", "Post-deploy check:",
                       "step-rules.md", "STEP: 10", "kind-pavedline-", "skip-CI", "NOT verified", "--revision"):
            self.assertIn(needle, self.text, needle)

    def test_what_local_cannot_prove(self):
        for needle in ("DNS", "TLS", "tunnel", "IAM", "multi-node", "load", "webhooks", "verified (cloud)"):
            self.assertIn(needle, self.text, needle)

    def test_the_deployer_never_syncs_a_cloud_cluster(self):
        self.assertRegex(self.text, r"never (syncs|applies|runs)[^.]*cloud")

    def test_sources_have_dates(self):
        self.assertRegex(SOURCES.read_text(), r"20\d\d-\d\d-\d\d")

    def test_post_deploy_check_language(self):
        for needle in ("post_deploy_check.py", "http <host> <path> <status>", "kubectl-get", "never executed", "human",
                       ".status.", ".spec.replicas", ".metadata.labels", "never prints the observed value", "20 lines", "300 s"):
            self.assertIn(needle, self.text, needle)
        self.assertNotIn("paste", self.text.lower().replace("never paste", ""))
        t = (PLUGIN / "templates/.github/pull_request_template.md").read_text()
        self.assertIn("kubectl-get", t)
        self.assertIn("http ", t)
        self.assertIn("kubectl-get", PAGE.read_text())

    def test_shared_rules_cover_step_skills_generally(self):
        rules = (PLUGIN / "skills/state/references/step-rules.md").read_text()
        self.assertNotIn("(steps 4 to 7)", rules.splitlines()[0])
        state = (PLUGIN / "skills/state/SKILL.md").read_text()
        self.assertNotIn("Steps 4 to 7 share", state)


class StepPage(unittest.TestCase):
    def test_page(self):
        t = PAGE.read_text()
        self.assertTrue(t.startswith("# Step 10: Deploy to local"))
        for h in ("## What it is for", "## Before you start", "## Output files", "## Checks and gate", "## Hand-off"):
            self.assertIn(h, t)
        self.assertIn("STATE.md", t)
        self.assertRegex(t.strip().splitlines()[-1], r"^Next:")


if __name__ == "__main__":
    unittest.main()
