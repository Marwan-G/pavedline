"""The CI templates: stack-neutral ones (copied at step 0) and the nextjs-fastapi pack's (copied at step 6).

Stdlib only: no YAML parser, so each rule is a targeted regex; actionlint (when installed) validates the structure.
"""
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
TEMPLATES = PLUGIN / "templates"
NEUTRAL_WF = TEMPLATES / ".github/workflows"
PACK = PLUGIN / "stacks/nextjs-fastapi"
PACK_WF = PACK / "files/.github/workflows"
START = PLUGIN / "scripts/start_project.py"

SURFACE_FILES = {"api": "ci-api.yml", "web": "ci-web.yml", "site": "ci-site.yml", "mobile": "ci-mobile.yml"}
SHARED_FILES = ["security.yml", "e2e-local.yml", "openapi-diff.yml", "image.yml"]
NEUTRAL_FILES = ["records.yml", "renovate.yml"]
SECRETS_ALLOWED = {"GITHUB_TOKEN", "RENOVATE_TOKEN"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


def all_workflows():
    out = [NEUTRAL_WF / n for n in NEUTRAL_FILES]
    out += [PACK_WF / n for n in list(SURFACE_FILES.values()) + SHARED_FILES]
    return out


def job_names(text):
    m = re.search(r"^jobs:\n(.*)", text, flags=re.M | re.S)
    return re.findall(r"^  ([a-z0-9][a-z0-9_-]*):\s*$", m.group(1), flags=re.M) if m else []


def job_block(text, name):
    m = re.search(r"^  %s:\s*\n(.*?)(?=^  [a-z0-9][a-z0-9_-]*:\s*$|\Z)" % re.escape(name), text, flags=re.M | re.S)
    return m.group(1) if m else ""


class Exists(unittest.TestCase):
    def test_files_exist(self):
        for p in all_workflows():
            self.assertTrue(p.is_file(), p)
        for rel in (".github/CODEOWNERS", ".github/pull_request_template.md", ".github/SOURCES.md", "renovate.json",
                    ".sanitize-denylist", "scripts/pr_checks.py", "scripts/sanitize_scan.py", "scripts/dot_check.py",
                    "scripts/dot_drift.py", "scripts/dependency-files.txt"):
            self.assertTrue((TEMPLATES / rel).is_file(), rel)


class EveryWorkflow(unittest.TestCase):
    def test_every_uses_is_pinned(self):
        seen = 0
        for p in all_workflows():
            for m in re.finditer(r"^\s*-?\s*uses:\s*(\S+)", read(p), flags=re.M):
                ref = m.group(1)
                seen += 1
                if ref.startswith("./"):
                    continue  # a reusable workflow of the same repository
                if ref.startswith("docker://"):
                    self.assertRegex(ref, r"@sha256:[0-9a-f]{64}$", "%s: %s" % (p.name, ref))
                    continue
                self.assertTrue(SHA40.match(ref.rpartition("@")[2]), "%s: %s" % (p.name, ref))
                self.assertRegex(read(p), re.escape(ref) + r" # v?\d", "%s: tag comment for %s" % (p.name, ref))
        self.assertGreater(seen, 20)

    def test_minimal_permissions_concurrency_and_timeouts(self):
        for p in all_workflows():
            t = read(p)
            self.assertRegex(t, r"(?m)^permissions:\n  contents: read\n", p.name)
            self.assertRegex(t, r"(?m)^concurrency:\n  group: ", p.name)
            self.assertNotRegex(t, r"(?m)^permissions:\s*(write-all|read-all)", p.name)
            self.assertEqual(len(re.findall(r"(?m)^    runs-on:", t)), len(re.findall(r"(?m)^    timeout-minutes:", t)), p.name)
            for name in job_names(t):
                blk = job_block(t, name)
                if re.search(r"(?m)^    uses: ", blk):
                    continue  # a job that calls a reusable workflow takes its timeouts from that workflow
                self.assertIn("timeout-minutes:", blk, "%s job %s" % (p.name, name))

    def test_no_pull_request_target_and_no_stray_secrets(self):
        for p in all_workflows():
            t = read(p)
            self.assertNotIn("pull_request_target", t, p.name)
            for m in re.finditer(r"secrets\.([A-Z_]+)", t):
                self.assertIn(m.group(1), SECRETS_ALLOWED, "%s uses secret %s" % (p.name, m.group(1)))

    def test_workflow_has_a_name_and_triggers(self):
        for p in all_workflows():
            t = read(p)
            self.assertRegex(t, r"(?m)^name: \S", p.name)
            self.assertRegex(t, r"(?m)^on:\n", p.name)

    def test_checkout_never_persists_credentials_except_the_tag_bump(self):
        for p in all_workflows():
            t = read(p)
            checkouts = len(re.findall(r"uses: actions/checkout@", t))
            falses = len(re.findall(r"persist-credentials: false", t))
            if p.name == "image.yml":
                self.assertEqual(checkouts, falses + 1, "exactly one checkout keeps credentials: the tag bump")
                self.assertIn("persist-credentials: true", job_block(t, "tag-bump"))
            else:
                self.assertEqual(checkouts, falses, p.name)

    def test_expressions_are_not_interpolated_into_run_scripts(self):
        # Untrusted PR fields (body, head ref, title) reach scripts only through env, never ${{ }} inside run:
        for p in all_workflows():
            for block in re.findall(r"run: \|\n((?:          .*\n|\n)+)", read(p)) + re.findall(r"run: ([^|\n].*)", read(p)):
                self.assertNotRegex(block, r"\$\{\{\s*github\.(event\.pull_request|head_ref|event\.head_commit)", p.name)

    def test_downloads_retry_fail_loudly_and_are_checksum_verified(self):
        for p in all_workflows():
            t = read(p)
            curls = [l for l in t.splitlines() if re.search(r"\bcurl\b", l) and not l.strip().startswith("#")]
            for line in curls:
                for flag in ("--fail", "--retry 6", "--retry-delay 20", "--retry-all-errors"):
                    self.assertIn(flag, line, "%s: %s" % (p.name, line.strip()))
            self.assertEqual(len(re.findall(r"\bcurl\b[^\n]*-O\b", t)), t.count("sha256sum --check --strict"), p.name)

    def test_no_floating_images_or_tools(self):
        for p in all_workflows():
            t = read(p)
            self.assertNotRegex(t, r":latest\b", p.name)
            self.assertNotIn("trivy-action", t, p.name)
            self.assertNotIn("setup-trivy", t, p.name)
            for m in re.finditer(r"\bdocker run\b(?:[^\n]*\\\n)*[^\n]*", t):
                self.assertRegex(m.group(0), r"@sha256:[0-9a-f]{64}|\$\{?[A-Z_]*IMAGE\}?|\"\$\{?[A-Z_]*IMAGE", p.name)
            for m in re.finditer(r"^\s*image: (\S+)", t, flags=re.M):
                self.assertRegex(m.group(1), r"@sha256:[0-9a-f]{64}$", "%s: %s" % (p.name, m.group(1)))
            self.assertNotRegex(t, r"npx (--yes )?@lhci/cli(?!@\d)", p.name)

    def test_no_personal_or_real_names(self):
        for p in all_workflows() + list((TEMPLATES / ".github").glob("*")):
            if p.is_file():
                t = read(p)
                self.assertNotRegex(t, r"@gmail\.", p.name)


class Neutral(unittest.TestCase):
    def test_records_jobs(self):
        t = read(NEUTRAL_WF / "records.yml")
        for j in ("gates-line", "denylist", "diagrams", "gitleaks", "state-size"):
            self.assertIn(j, job_names(t))
        self.assertIn("scripts/pr_checks.py", t)
        self.assertIn("scripts/sanitize_scan.py", t)
        self.assertIn("scripts/dot_check.py", t)
        self.assertIn("scripts/dot_drift.py", t)
        self.assertRegex(t, r"uses: docker://ghcr\.io/gitleaks/gitleaks:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}\n")
        self.assertRegex(t, r"-le 60")
        self.assertIn("pull_request:", t)
        self.assertIn(".sanitize-denylist.local", read(TEMPLATES / "scripts/sanitize_scan.py"))

    def test_renovate_workflow(self):
        t = read(NEUTRAL_WF / "renovate.yml")
        self.assertRegex(t, r"renovatebot/github-action@[0-9a-f]{40} # v\d")
        self.assertIn("secrets.RENOVATE_TOKEN", t)
        self.assertNotIn("secrets.GITHUB_TOKEN", t)
        self.assertRegex(t, r"cron: \"\d+ \d+ \* \* 1\"")  # weekly, Monday
        self.assertIn("workflow_dispatch", t)

    def test_renovate_json(self):
        cfg = json.loads(read(TEMPLATES / "renovate.json"))
        self.assertTrue(cfg["dependencyDashboard"])
        self.assertEqual(cfg["minimumReleaseAge"], "14 days")
        self.assertEqual(cfg["schedule"], ["before 6am on monday"])
        rules = cfg["packageRules"]
        auto = [(i, r) for i, r in enumerate(rules) if r.get("automerge") is True]
        self.assertEqual(len(auto), 1, "exactly one automerge rule: development dependencies (never GitHub Actions)")
        dev = [r for _, r in auto if "matchDepTypes" in r]
        self.assertEqual(len(dev), 1)
        self.assertEqual(dev[0]["matchUpdateTypes"], ["patch"])
        self.assertEqual(set(dev[0]["matchDepTypes"]), {"devDependencies", "dev", "dependency-groups"})
        grouped = [r for r in rules if r.get("groupName") and set(r.get("matchUpdateTypes", [])) == {"minor", "patch"}]
        self.assertTrue(grouped)
        never = [(i, r) for i, r in enumerate(rules) if r.get("automerge") is False]
        self.assertGreater(min(i for i, _ in never), max(i for i, _ in auto), "never-automerge rules come last so they win")
        blob = json.dumps([r for _, r in never]).lower()
        for needle in ("argo", "cloudnative-pg", "dockerfile", "helm", "gateway-api", "envoy", "terraform"):
            self.assertIn(needle, blob, needle)
        # The github-actions manager also extracts `services.<x>.image` and `docker://` steps (datasource docker):
        # those are images and must never be automerged (the Postgres service image, the gitleaks image).
        self.assertIn({"matchManagers": ["github-actions"], "matchDatasources": ["docker"]},
                      [{k: v for k, v in r.items() if k in ("matchManagers", "matchDatasources")} for _, r in never])
        self.assertIn("versions.env", json.dumps(cfg["customManagers"]))
        self.assertGreaterEqual(len(cfg["customManagers"]), 7)

    def test_pavedlines_own_renovate_json_tracks_the_gitleaks_pin_and_never_automerges_it(self):
        cfg = json.loads(read(ROOT / "renovate.json"))
        mgrs = [m for m in cfg["customManagers"] if "gitleaks" in json.dumps(m)]
        self.assertEqual(len(mgrs), 1)
        m = mgrs[0]
        self.assertEqual(m["customType"], "regex")
        self.assertEqual(m["datasourceTemplate"], "docker")
        self.assertIn("gitleaks", " ".join(m["managerFilePatterns"]))
        import re
        line = [l for l in read(ROOT / "scripts/gitleaks.env").splitlines() if l.startswith("GITLEAKS_IMAGE=")][0]
        hit = re.search(m["matchStrings"][0].replace("(?<", "(?P<"), line)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.group("depName"), "ghcr.io/gitleaks/gitleaks")
        self.assertRegex(hit.group("currentValue"), r"^v\d+\.\d+\.\d+$")
        self.assertRegex(hit.group("currentDigest"), r"^sha256:[0-9a-f]{64}$")
        rules = [r for r in cfg["packageRules"] if r.get("automerge") is False and "scripts/gitleaks.env" in r.get("matchFileNames", [])]
        self.assertTrue(rules)

    def test_pavedlines_own_renovate_json_never_automerges_images_either(self):
        cfg = json.loads(read(ROOT / "renovate.json"))
        rules = cfg["packageRules"]
        auto = [i for i, r in enumerate(rules) if r.get("automerge") is True]
        idx = [i for i, r in enumerate(rules) if r.get("automerge") is False
               and r.get("matchManagers") == ["github-actions"] and r.get("matchDatasources") == ["docker"]]
        self.assertTrue(idx)
        self.assertGreater(min(idx), max(auto))

    def test_renovate_config_validator_accepts_both_configs(self):
        npx = shutil.which("npx")
        if not npx:
            self.skipTest("skipped: npx not on PATH (renovate-config-validator)")
        for cfg in (TEMPLATES / "renovate.json", ROOT / "renovate.json"):
            d = pathlib.Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, d, True)
            shutil.copy(cfg, d / "renovate.json")
            r = subprocess.run([npx, "--yes", "-p", "renovate@44.186.4", "renovate-config-validator", "--strict",
                                "renovate.json"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s\n%s%s" % (cfg, r.stdout[-1500:], r.stderr[-1500:]))

    def test_codeowners_uses_a_placeholder_owner(self):
        t = read(TEMPLATES / ".github/CODEOWNERS")
        self.assertRegex(t, r"(?m)^\* @OWNER$")

    def _checker(self):
        spec = importlib.util.spec_from_file_location("tpl_pr_checks", TEMPLATES / "scripts/pr_checks.py")
        sys.path.insert(0, str(TEMPLATES / "scripts"))
        old, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # never leave a __pycache__ in a template
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        finally:
            sys.path.pop(0)
            sys.dont_write_bytecode = old
            sys.modules.pop("dot_drift", None)
        return mod

    def test_pr_template(self):
        t = read(TEMPLATES / ".github/pull_request_template.md")
        self.assertIn("Post-deploy check:", t)
        self.assertIn("diagram unchanged", t)
        mod = self._checker()
        self.assertFalse(mod.has_gates_line(t), "the unedited template must FAIL the gates-line check")
        filled = t.replace("TDD ?", "TDD \u2713").replace("review ?", "review \u2713").replace(
            "security ?", "security \u2713").replace("verification ?", "verification \u2713").replace(
            "(n found, m fixed)", "(2 found, 2 fixed)").replace("\u2713|n/a", "n/a")
        self.assertTrue(mod.has_gates_line(filled), filled)

    def test_scripts_have_no_pavedline_paths(self):
        for f in (TEMPLATES / "scripts").iterdir():
            if f.is_dir():
                self.fail("unexpected directory in templates/scripts (a __pycache__ would be copied into products): %s" % f)
            t = read(f)
            self.assertNotIn("plugins/pavedline", t, f.name)
        deps = read(TEMPLATES / "scripts/dependency-files.txt")
        self.assertNotIn("plugins/pavedline", deps)
        self.assertIn("scripts/local-cluster/versions.env", deps)
        self.assertIn("renovate.json", deps)

    def test_denylist_has_the_generic_patterns_and_cidr_rules(self):
        t = read(TEMPLATES / ".sanitize-denylist")
        for needle in (r"ocid1\.", "PRIVATE KEY", r"ghp_", "AKIA", r"(?!/\d)", r"/\d+\b"):
            self.assertIn(needle, t, needle)

    def test_sources_has_urls_and_dates(self):
        t = read(TEMPLATES / ".github/SOURCES.md")
        for needle in ("actions/checkout", "renovatebot/github-action", "gitleaks", "actionlint", "2026-11-09", "https://"):
            self.assertIn(needle, t, needle)


class PerSurface(unittest.TestCase):
    def test_markers_match_pack_yaml(self):
        pack = read(PACK / "pack.yaml")
        for surface, fname in SURFACE_FILES.items():
            first = read(PACK_WF / fname).splitlines()[0]
            self.assertEqual(first, "# pavedline-surface: " + surface, fname)
            self.assertIn('- "# pavedline-surface: %s"' % surface, pack)
        for fname in SHARED_FILES:
            self.assertNotIn("pavedline-surface", read(PACK_WF / fname), fname)

    def test_api_jobs(self):
        t = read(PACK_WF / "ci-api.yml")
        for j in ("checks", "db-tests", "image"):
            self.assertIn(j, job_names(t))
        for cmd in ("uv sync --frozen", "uv run ruff check . ../../scripts", "uv run ruff format --check . ../../scripts",
                    "uv run pyright", "uv run lint-imports", "uv run pytest -q", "scripts/rls_check.py",
                    "scripts/contract_check.py", "--contract docs/api/openapi.yaml"):
            self.assertIn(cmd, t, cmd)

    def test_db_tests_are_gated_on_the_label_and_main(self):
        t = read(PACK_WF / "ci-api.yml")
        blk = job_block(t, "db-tests")
        self.assertIn("ci:db", blk)
        self.assertIn("github.event_name == 'push'", blk)
        self.assertRegex(t, r"types: \[opened, synchronize, reopened, labeled\]")
        self.assertRegex(blk, r"image: postgres:16\.\d+@sha256:[0-9a-f]{64}")
        self.assertIn("pull_request", blk)
        # lint/types/unit do not run for a label event
        self.assertIn("github.event.action != 'labeled'", job_block(t, "checks"))

    def test_tenancy_env_and_skippable_steps(self):
        t = read(PACK_WF / "ci-api.yml")
        self.assertRegex(t, r"(?m)^  PAVEDLINE_TENANCY: multi\n")
        self.assertIn("not applicable (decision 0002)", t)
        for step in ("RLS check", "Leak fixture"):
            self.assertIn("- name: " + step, t)
        self.assertEqual(t.count("PAVEDLINE_TENANCY"), len(re.findall(r"PAVEDLINE_TENANCY", t)))
        self.assertGreaterEqual(t.count('"$PAVEDLINE_TENANCY" = "single"'), 2)

    def test_image_is_built_on_main_only_and_bumps_a_digest_never_a_sync(self):
        img = read(PACK_WF / "image.yml")
        self.assertIn("workflow_call:", img)
        self.assertNotRegex(img, r"(?m)^  (push|pull_request|schedule):")
        self.assertIn("ubuntu-24.04-arm", img)
        self.assertIn("image.digest", img)
        self.assertIn("values-staging.yaml", img)
        self.assertIn("docker push", img)
        self.assertIn("ghcr.io", img)
        self.assertRegex(img, r"ghcr\.io/aquasecurity/trivy:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertIn("--exit-code 1", img)
        self.assertIn("HIGH,CRITICAL", img)
        self.assertIn("--ignore-unfixed", img)
        self.assertNotRegex(img, r"skip ci|\[skip|ci skip|\[no ci", "no skip-CI marker in the bump commit")
        self.assertNotRegex(img, r"argocd|kubectl|sync", "the bump never syncs a cluster")
        self.assertIn("contents: write", job_block(img, "tag-bump") + img)
        self.assertIn("packages: write", img)
        self.assertRegex(img, r"for attempt in")  # retry on a push race
        for fname in ("ci-api.yml", "ci-web.yml", "ci-site.yml"):
            t = read(PACK_WF / fname)
            blk = job_block(t, "image")
            self.assertIn("uses: ./.github/workflows/image.yml", blk, fname)
            self.assertIn("github.event_name == 'push'", blk, fname)
            self.assertIn("refs/heads/main", blk, fname)
            self.assertIn("contents: write", blk, fname)
            self.assertIn("packages: write", blk, fname)
            self.assertNotRegex(t, r"(?m)^on:\n(?:.*\n)*?  schedule:", fname)

    def test_the_bump_script_rewrites_only_the_digest_of_the_named_workload(self):
        img = read(PACK_WF / "image.yml")
        m = re.search(r"python3 -I - <<'PY'\n(.*?)\n          PY\n", img, flags=re.S)
        self.assertTrue(m)
        script = "\n".join(l[10:] for l in m.group(1).splitlines())
        digest = "sha256:" + "ab" * 32
        for app in ("api", "web", "site"):
            tmp = pathlib.Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, tmp, True)
            dest = tmp / "infra/k8s/apps" / app
            dest.mkdir(parents=True)
            src = PACK / "files/infra/k8s/apps" / app / "values-staging.yaml"
            dest.joinpath("values-staging.yaml").write_text(read(src))
            r = subprocess.run([sys.executable, "-I", "-c", script], cwd=tmp, capture_output=True, text=True,
                               env={"APP": app, "WORKLOAD": app, "DIGEST": digest, "PATH": os.environ["PATH"]})
            self.assertEqual(r.returncode, 0, r.stderr)
            before, after = read(src).splitlines(), read(dest / "values-staging.yaml").splitlines()
            changed = [(a, b) for a, b in zip(before, after) if a != b]
            self.assertEqual(len(changed), 1, changed)
            self.assertEqual(changed[0][1], '      digest: "%s"' % digest)
            self.assertIn("digest: ", changed[0][0])
            self.assertEqual(len(before), len(after))
        r = subprocess.run([sys.executable, "-I", "-c", script], cwd=tmp, capture_output=True, text=True,
                           env={"APP": "site", "WORKLOAD": "nope", "DIGEST": digest, "PATH": os.environ["PATH"]})
        self.assertNotEqual(r.returncode, 0)

    def test_web_jobs(self):
        t = read(PACK_WF / "ci-web.yml")
        for cmd in ("pnpm install --frozen-lockfile", "pnpm -r lint", "pnpm -r typecheck", "pnpm -r test",
                    "pnpm run check:generated", "python3 scripts/web_boundary_check.py", "pnpm --filter @app/web build",
                    "playwright install", "pnpm --filter @app/web e2e"):
            self.assertIn(cmd, t, cmd)

    def test_site_jobs_and_lighthouse_budget(self):
        t = read(PACK_WF / "ci-site.yml")
        self.assertIn("pnpm --filter @app/site build", t)
        self.assertRegex(t, r"@lhci/cli@\d+\.\d+\.\d+")
        cfg = json.loads(read(PACK / "files/apps/site/lighthouserc.json"))
        asserts = cfg["ci"]["assert"]["assertions"]
        self.assertEqual(asserts["categories:accessibility"][1]["minScore"], 0.9)
        self.assertEqual(asserts["categories:seo"][1]["minScore"], 0.9)
        self.assertIn("startServerCommand", cfg["ci"]["collect"])

    def test_mobile_jobs_and_ruling_8_triggers(self):
        t = read(PACK_WF / "ci-mobile.yml")
        for j in ("checks", "android-build", "ios-build"):
            self.assertIn(j, job_names(t))
        for cmd in ("pnpm --filter @app/mobile lint", "pnpm --filter @app/mobile typecheck",
                    "pnpm --filter @app/mobile test", "expo prebuild", "./gradlew assembleDebug",
                    "xcodebuild", "-sdk iphonesimulator", "CODE_SIGNING_ALLOWED=NO"):
            self.assertIn(cmd, t, cmd)
        self.assertIn("apps/mobile/**", t)
        self.assertRegex(t, r"schedule:\n\s+- cron: \"\d+ \d+ \* \* \d\"")
        self.assertIn("runs-on: macos-26", t)
        self.assertRegex(t, r"actions/setup-java@[0-9a-f]{40} # v\d")
        self.assertIn("temurin", t)

    def test_security_jobs(self):
        t = read(PACK_WF / "security.yml")
        for j in ("semgrep", "trivy-fs", "checkov", "web-boundary"):
            self.assertIn(j, job_names(t))
        self.assertRegex(t, r"semgrep/semgrep:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertIn("--config p/default", t)
        self.assertIn("--metrics=off", t)
        self.assertIn("--error", t)
        self.assertRegex(t, r"ghcr\.io/aquasecurity/trivy:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertRegex(t, r"bridgecrew/checkov:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertIn("infra/k8s/apps/*/", t)
        self.assertIn("helm dependency update", t)
        self.assertIn("infra/helm/.checkov.yaml", t)
        for app in ("api", "web", "site", "postgres"):
            self.assertNotRegex(t, r"apps/%s\b" % app, "no surface is hard-coded: " + app)

    def test_openapi_diff(self):
        t = read(PACK_WF / "openapi-diff.yml")
        self.assertIn("docs/api/openapi.yaml", t)
        self.assertRegex(t, r"oasdiff_\d+\.\d+\.\d+_linux_amd64\.tar\.gz")
        self.assertIn("sha256sum --check --strict", t)
        self.assertIn("oasdiff breaking", t)
        self.assertIn("--fail-on ERR", t)
        self.assertIn("/v2", t)  # how a breaking change is allowed
        self.assertIn("skipping", t)

    def test_e2e_local(self):
        t = read(PACK_WF / "e2e-local.yml")
        self.assertIn("ubuntu-24.04-arm", t)
        for needle in ("scripts/local-cluster/up.sh ci", "scripts/deploy_local.sh ci", "zap-baseline.py",
                       "scripts/local-cluster/down.sh ci --all", "httproute", "lhci", "playwright",
                       "playwright.cluster.config.ts"):
            self.assertIn(needle, t, needle)
        self.assertRegex(t, r"ghcr\.io/zaproxy/zaproxy:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertRegex(read(PACK_WF / "e2e-local.yml"), r"if: always\(\)\n\s+run: scripts/local-cluster/down\.sh ci --all")
        for p in ("apps/**", "services/**", "infra/**"):
            self.assertIn(p, t)
        self.assertRegex(t, r"sha256sum --check --strict")
        cfg = read(PACK / "files/apps/web/playwright.cluster.config.ts")
        self.assertIn("E2E_BASE_URL", cfg)
        self.assertNotIn("webServer", cfg)


class FixRound1(unittest.TestCase):
    def test_c2_ci_api_web_site_run_on_every_pull_request(self):
        for f in ("ci-api.yml", "ci-web.yml", "ci-site.yml"):
            t = read(PACK_WF / f)
            pr = re.search(r"(?m)^  pull_request:\n((?:    .*\n)*)", t).group(1)
            self.assertNotIn("paths", pr, f + ": a path filter on a required check stalls unrelated PRs")
        m = read(PACK_WF / "ci-mobile.yml")
        self.assertIn("paths:", re.search(r"(?m)^  pull_request:\n((?:    .*\n)*)", m).group(1))
        self.assertRegex(m, r"never mark ci-mobile as a required check")

    def test_c3_gitops_skill_states_the_bump_needs_a_bypass(self):
        t = read(PLUGIN / "skills/gitops/SKILL.md")
        for needle in ("ruleset", "bypass", "GitHub Actions", "WAITING.md", "GITHUB_TOKEN", "triggers no workflow",
                       "never mark `ci-mobile` as a required check"):
            self.assertIn(needle, t, needle)

    def test_c4_images_are_built_at_least_14_days_before_the_pin_date(self):
        db = read(PACK_WF / "ci-api.yml")
        self.assertIn("postgres:16.14@sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b", db)
        self.assertNotIn("f9a7b9ebf6f56201", db)
        self.assertNotIn("9624669db72f54d8", read(PACK_WF / "e2e-local.yml"))
        src = read(PACK / "SOURCES.md")
        self.assertIn("Image build dates", src)
        for needle in ("2026-08-05", "2026-10-20", "2026-10-21", "2025-12-12", "2026-03-21"):
            self.assertIn(needle, src, needle)

    def test_c5_comments_do_not_point_at_files_products_never_receive(self):
        for p in all_workflows():
            for m in re.finditer(r"[^\s\"(]*SOURCES\.md", read(p)):
                self.assertTrue(m.group(0).endswith("docs/architecture/STACK-SOURCES.md"), "%s: %s" % (p.name, m.group(0)))
            self.assertNotIn("Pavedline stack pack", read(p), p.name)

    def test_r2_a_label_event_does_not_cancel_the_checks_run(self):
        t = read(PACK_WF / "ci-api.yml")
        grp = re.search(r"(?m)^concurrency:\n  group: (.*)$", t).group(1)
        self.assertIn("github.event.action == 'labeled'", grp)

    def test_r3_only_local_hostnames_are_scanned(self):
        t = read(PACK_WF / "e2e-local.yml")
        self.assertIn(r"\.(localtest\.me|localhost)", t)
        self.assertRegex(t, r"not a local hostname")
        self.assertLess(t.index("not a local hostname"), t.index("zap-baseline.py"))

    def test_r4_the_checkers_run_from_the_base_branch(self):
        t = read(NEUTRAL_WF / "records.yml")
        for f in ("scripts/pr_checks.py", "scripts/dot_drift.py", "scripts/dependency-files.txt",
                  "scripts/sanitize_scan.py", ".sanitize-denylist", "scripts/dot_check.py"):
            self.assertIn('git show "$BASE_SHA:%s"' % f, t, f)
        self.assertGreaterEqual(t.count("fetch-depth: 0"), 3)
        owners = read(TEMPLATES / ".github/CODEOWNERS")
        for path in ("/scripts/", "/.github/", "/.sanitize-denylist"):
            self.assertRegex(owners, r"(?m)^%s @OWNER$" % re.escape(path))

    def test_r5_checkov_runs_from_its_image_by_digest(self):
        t = read(PACK_WF / "security.yml")
        self.assertRegex(t, r"bridgecrew/checkov:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}")
        self.assertNotIn("uvx", t)
        self.assertNotIn("setup-uv", t)

    def test_r6_the_bump_script_runs_isolated(self):
        self.assertIn("python3 -I - <<'PY'", read(PACK_WF / "image.yml"))

    def test_r7_no_event_field_is_interpolated_into_any_run_block(self):
        pat = re.compile(r"\$\{\{[^}]*github\.(event\.|head_ref|base_ref)")
        for p in all_workflows():
            lines = read(p).splitlines()
            for i, ln in enumerate(lines):
                if re.match(r"^\s*(- )?run:", ln):
                    body = [ln]
                    indent = len(ln) - len(ln.lstrip())
                    for nxt in lines[i + 1:]:
                        if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent + (2 if ln.lstrip().startswith("- ") else 0):
                            break
                        body.append(nxt)
                    self.assertIsNone(pat.search("\n".join(body)), "%s line %d" % (p.name, i + 1))


class StartProject(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        r = subprocess.run([sys.executable, str(START), "--target", str(self.dir), "--name", "example", "--mode", "solo"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def git_init(self):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "init"]):
            subprocess.run(["git"] + args, cwd=self.dir, check=True, capture_output=True, env=env)

    def test_neutral_files_are_copied_at_step_0(self):
        for rel in (".github/workflows/records.yml", ".github/workflows/renovate.yml", ".github/CODEOWNERS",
                    ".github/pull_request_template.md", "renovate.json", ".sanitize-denylist", "scripts/pr_checks.py"):
            self.assertTrue((self.dir / rel).is_file(), rel)
        self.assertFalse((self.dir / ".github/workflows/ci-api.yml").exists())

    def run_script(self, *args):
        return subprocess.run([sys.executable, *args], cwd=self.dir, capture_output=True, text=True)

    def test_sanitize_scan_runs_in_a_product_tree(self):
        self.git_init()
        r = self.run_script("scripts/sanitize_scan.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (self.dir / "leak.txt").write_text("host " + ".".join(["10", "1", "2", "3"]) + "\n")
        subprocess.run(["git", "add", "leak.txt"], cwd=self.dir, check=True)
        r = self.run_script("scripts/sanitize_scan.py")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("leak.txt:1", r.stdout)

    def test_pr_checks_runs_in_a_product_tree(self):
        body = self.dir / "body.txt"
        body.write_text("x\n")
        self.assertEqual(self.run_script("scripts/pr_checks.py", "--body-file", str(body)).returncode, 1)
        body.write_text(read(self.dir / ".github/pull_request_template.md"))
        self.assertEqual(self.run_script("scripts/pr_checks.py", "--body-file", str(body)).returncode, 1,
                         "an unedited template fails")
        body.write_text("Gates: TDD \u2713 \u00b7 review \u2713 (0 found, 0 fixed) \u00b7 security \u2713 \u00b7 "
                        "adversarial n/a \u00b7 verification \u2713\n")
        self.assertEqual(self.run_script("scripts/pr_checks.py", "--body-file", str(body)).returncode, 0)
        body.write_text("x\n")
        (self.dir / "changed.txt").write_text("renovate.json\npnpm-lock.yaml\n")
        r = self.run_script("scripts/pr_checks.py", "--body-file", str(body), "--head-ref", "renovate/x",
                            "--changed-files-file", str(self.dir / "changed.txt"))
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(shutil.which("dot"), "skipped: dot not on PATH")
    def test_dot_check_runs_in_a_product_tree(self):
        self.git_init()
        r = self.run_script("scripts/dot_check.py", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_dot_drift_runs_in_a_product_tree(self):
        self.git_init()
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.dir, capture_output=True, text=True).stdout.strip()
        r = self.run_script("scripts/dot_drift.py", "--base", base)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Actionlint(unittest.TestCase):
    def test_actionlint_passes_on_both_template_trees(self):
        exe = shutil.which("actionlint")
        if not exe:
            self.skipTest("skipped: actionlint not on PATH")
        script = ROOT / "scripts/actionlint_templates.sh"
        r = subprocess.run(["bash", str(script), exe], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("== actionlint"), 2)


class LongerRetriesInCI(unittest.TestCase):
    def test_cluster_jobs_retry_downloads_longer(self):
        import pathlib as _p
        root = _p.Path(__file__).resolve().parent.parent
        self.assertIn('PAVEDLINE_RETRY_ATTEMPTS: "7"', (root / ".github/workflows/ci.yml").read_text())
        e2e = root / "plugins/pavedline/stacks/nextjs-fastapi/files/.github/workflows/e2e-local.yml"
        self.assertIn('PAVEDLINE_RETRY_ATTEMPTS: "7"', e2e.read_text())


if __name__ == "__main__":
    unittest.main()
