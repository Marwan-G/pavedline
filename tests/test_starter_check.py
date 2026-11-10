import json
import os
import pathlib
import re
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/starter_check.sh"
CI = ROOT / ".github/workflows/ci.yml"
MOBILE = ROOT / ".github/workflows/starter-mobile.yml"
FULL = ROOT / ".github/workflows/starter-full.yml"
FIXTURE = ROOT / "tests/fixtures/starter-answers.json"
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)


class StarterScript(unittest.TestCase):
    def test_exists_executable_and_parses(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_has_every_stage_and_the_keep_flag(self):
        t = SCRIPT.read_text()
        for needle in ("generate", "static", "unit", "cluster", "full", "all", "--keep", "--stage"):
            self.assertIn(needle, t)

    def test_unknown_stage_and_argument_are_refused(self):
        for args in (["--stage", "nope"], ["--bogus"]):
            r = subprocess.run([str(SCRIPT), *args], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, args)

    def test_static_stage_runs_the_pinned_gitleaks_on_a_git_archive_export_under_home(self):
        t = SCRIPT.read_text()
        self.assertIn("static-gitleaks", t)
        self.assertIn("git archive HEAD", t)
        self.assertIn("$HOME", t)
        self.assertIn("GITLEAKS_IMAGE", t)
        self.assertIn("skipping gitleaks", t)

    def test_refuses_a_non_kind_context(self):
        t = SCRIPT.read_text()
        self.assertIn("require_kind_context", t)
        self.assertIn("kind-pavedline-*", t)
        self.assertIn("refusing", t)
        # every kubectl call in the script names the kind context explicitly or goes through the cluster scripts
        for line in t.splitlines():
            if re.match(r"\s*kubectl\s", line):
                self.assertIn("--context", line)

    def test_proof_steps_are_present(self):
        t = SCRIPT.read_text()
        for needle in (
            "web_boundary_check.py", "local-deploy.json", "helm dependency update", "CHECKOV_IMAGE", "actionlint",
            "sanitize_scan.py", "dot_check.py", "pr_checks.py", "--frozen-lockfile", "playwright", "expo prebuild",
            "uv sync --frozen", "ruff format --check", "pyright", "lint-imports", "pytest", "rls_check.py",
            "contract_check.py", "up.sh", "deploy_local.sh", "verified (local)", "down.sh",
            "starter@example.invalid", "example/.", "docker rm -f",
        ):
            self.assertIn(needle, t, needle)

    def test_native_builds_are_not_in_the_script(self):
        t = SCRIPT.read_text()
        self.assertNotIn("gradlew", t)
        self.assertNotIn("xcodebuild", t)

    def test_never_changes_global_git_config(self):
        t = SCRIPT.read_text()
        self.assertIsNone(re.search(r"git config|--global(?![-\w])", t))


def selftest(mode, **kw):
    env = dict(os.environ, PAVEDLINE_SELFTEST=mode, TMPDIR=kw.pop("tmp", tempfile.gettempdir()))
    return subprocess.run([str(SCRIPT), "--stage", "selftest"], capture_output=True, text=True, env=env, **kw)


class StepReportsHonestly(unittest.TestCase):
    """A step function whose first command fails must fail the step, even when step() is called in a condition."""

    def test_multi_command_step_with_early_failure_fails(self):
        r = selftest("bad")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("FAIL  selftest-bad", r.stderr)
        self.assertNotIn("PASS  selftest-bad", r.stderr)

    def test_early_failure_fails_when_step_runs_as_an_if_condition(self):
        r = selftest("bad-in-if")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("FAIL  selftest-bad", r.stderr)

    def test_passing_step_passes(self):
        r = selftest("good")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PASS  selftest-good", r.stderr)

    def test_no_step_is_called_in_a_condition_that_disables_errexit(self):
        for line in SCRIPT.read_text().splitlines():
            code = line.split("#", 1)[0]
            if re.search(r"\bif\s+!?\s*step\b|&&\s*step\b|\|\|\s*step\b|\bstep\s[^;]*(&&|\|\|)", code):
                self.fail("step called inside a condition or list: " + line)

    def test_term_signal_exits_143_and_removes_the_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PAVEDLINE_SELFTEST="sleep", TMPDIR=tmp)
            p = subprocess.Popen([str(SCRIPT), "--stage", "selftest"], env=env, stderr=subprocess.PIPE, text=True)
            for _ in range(100):
                if any(n.startswith("pavedline-starter.") for n in os.listdir(tmp)) and time.sleep(0.5) is None:
                    break
                time.sleep(0.1)
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=30)
            self.assertEqual(p.returncode, 143)
            self.assertEqual([n for n in os.listdir(tmp) if n.startswith("pavedline-starter.")], [])

    def test_int_signal_exits_130(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PAVEDLINE_SELFTEST="sleep", TMPDIR=tmp)
            p = subprocess.Popen([str(SCRIPT), "--stage", "selftest"], env=env, stderr=subprocess.PIPE, text=True)
            time.sleep(1.5)
            p.send_signal(signal.SIGINT)
            p.wait(timeout=30)
            self.assertEqual(p.returncode, 130)

    def test_unwritable_tmpdir_fails_with_2(self):
        r = subprocess.run([str(SCRIPT), "--stage", "static"], capture_output=True, text=True,
                           env=dict(os.environ, TMPDIR="/nonexistent-dir-for-test"))
        self.assertEqual(r.returncode, 2, r.stderr)


class UpRetriesKindCreate(unittest.TestCase):
    def test_kind_create_is_retried_with_cleanup_of_the_partial_cluster(self):
        up = (ROOT / "plugins/pavedline/scripts/local-cluster/up.sh").read_text()
        block = up.split("kind create cluster", 1)
        self.assertEqual(len(block), 2)
        self.assertIn("kind delete cluster --name", up)
        self.assertRegex(up, r"for attempt in 1 2 3")


class StarterFixture(unittest.TestCase):
    def test_parses_and_is_neutral_multi_tenant_with_four_surfaces(self):
        data = json.loads(FIXTURE.read_text())
        self.assertEqual(data["surfaces"], ["api", "web", "site", "mobile"])
        self.assertEqual(data["tenancy"], "multi")


class StarterWorkflows(unittest.TestCase):
    def test_starter_job_in_ci(self):
        t = CI.read_text()
        job = t.split("\n  starter:\n", 1)[1].split("\n  pr-body:\n", 1)[0]
        self.assertIn("ubuntu-24.04-arm", job)
        self.assertRegex(job, r"timeout-minutes: \d+")
        self.assertIn("scripts/starter_check.sh --stage all", job)
        self.assertNotIn("if:", job)
        for tool in ("kind v0.33.0", "helm v4.3.1", "actionlint v1.7.12"):
            self.assertIn(tool + " (checksum verified)", job)
        self.assertIn("sha256sum --check --strict", job)
        self.assertRegex(job, r'version: "\d+\.\d+\.\d+"')
        self.assertRegex(job, r'node-version: "\d+\.\d+\.\d+"')
        self.assertIn("pnpm@11.28.8", job)

    def test_full_stage_runs_backups_and_the_drill(self):
        text = SCRIPT.read_text()
        for needle in ("--stage full", 'up.sh" "$PROJECT" --full', 'verify.sh" "$PROJECT" --full', "example-full",
                       "full-instances", "full-backup", "full-restore-drill", "RESTORE DRILL PASS", "readyInstances"):
            self.assertIn(needle, text, needle)
        # `all` stays as it was: the full stage is separate
        self.assertIn("all) run_static; run_unit; run_cluster ;;", text)

    def test_full_stage_drives_each_alert_red_against_a_sink(self):
        text = SCRIPT.read_text()
        for needle in ("full-alerts", "f_alerts", "REQ POST /notify", "REQ GET /heartbeat", "endpoint-0-down",
                       "backup-db-daily", "never-runs", "--from=cronjob/alerts-check", "backupMaxAge: 1s", "auth can-i"):
            self.assertIn(needle, text, needle)

    def test_proof_jobs_are_not_owned_by_the_cronjob(self):
        # The CronJob keeps one finished Job; a copy it owns can be deleted before its log is read.
        text = SCRIPT.read_text()
        body = text[text.index("run_checker() {"):]
        body = body[:body.index("\n  }\n")]
        self.assertIn("--dry-run=client -o json", body)
        self.assertIn('pop("ownerReferences"', body)
        self.assertIn('create -f -', body)

    def test_full_is_a_known_stage(self):
        text = SCRIPT.read_text()
        self.assertIn("generate|static|unit|cluster|full|all|selftest) ;;", text)

    def test_starter_full_workflow_has_filters_schedule_dispatch_and_the_stage(self):
        t = FULL.read_text()
        self.assertIn("starter-full:", t)
        self.assertIn("ubuntu-24.04-arm", t)
        for path in ("plugins/pavedline/stacks/**", "plugins/pavedline/templates/infra/**", "plugins/pavedline/scripts/local-cluster/**"):
            self.assertIn(f'"{path}"', t, path)
        self.assertIn("schedule:", t)
        self.assertIn("workflow_dispatch:", t)
        self.assertIn("scripts/starter_check.sh --stage full", t)
        self.assertIn("PAVEDLINE_RETRY_ATTEMPTS", t)
        for tool in ("kind v0.33.0", "helm v4.3.1"):
            self.assertIn(tool + " (checksum verified)", t)
        self.assertIn("required check", t)

    def test_mobile_jobs_have_filters_schedule_and_native_builds(self):
        t = MOBILE.read_text()
        self.assertIn("starter-mobile-android:", t)
        self.assertIn("starter-mobile-ios:", t)
        self.assertIn("macos-26", t)
        self.assertIn("plugins/pavedline/stacks/**", t)
        self.assertIn("scripts/starter_check.sh", t)
        self.assertIn("schedule:", t)
        self.assertIn("./gradlew assembleDebug", t)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", t)
        self.assertIn("--stage generate", t)
        self.assertIn("required check", t)

    def test_actions_are_pinned_by_sha_and_credentials_not_persisted(self):
        for path in (CI, MOBILE, FULL):
            text = path.read_text()
            for ref in USES.findall(text):
                if ref.startswith("docker://"):
                    self.assertRegex(ref, r"@sha256:[0-9a-f]{64}$", ref)
                else:
                    self.assertRegex(ref, r"@[0-9a-f]{40}$", ref)
            self.assertEqual(text.count("actions/checkout@"), text.count("persist-credentials: false"), path.name)
            self.assertRegex(text, r"(?m)^permissions:\n  contents: read\n")


if __name__ == "__main__":
    unittest.main()
