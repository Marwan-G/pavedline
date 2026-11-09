"""Final review fixes: symlinked writes, shared containers, CI base-copy checks, docs and small cleanups."""
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
PACK = PLUGIN / "stacks/nextjs-fastapi"
APPLY = PLUGIN / "scripts/apply_stack.py"
START = PLUGIN / "scripts/start_project.py"
STARTER = ROOT / "scripts/starter_check.sh"
GUARD = PLUGIN / "scripts/hooks/guard_cluster.py"


def read(path):
    return pathlib.Path(path).read_text(encoding="utf-8")


def start_project(target):
    return subprocess.run([sys.executable, str(START), "--target", str(target), "--name", "example", "--mode", "solo"],
                          capture_output=True, text=True)


def apply_stack(target, *extra):
    return subprocess.run([sys.executable, str(APPLY), "--target", str(target), "--pack", "nextjs-fastapi",
                           "--surfaces", "api", *extra], capture_output=True, text=True)


def files_of(path):
    return sorted(p.relative_to(path).as_posix() for p in pathlib.Path(path).rglob("*") if p.is_file() or p.is_symlink())


class SymlinkedWrites(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.dir = root / "product"
        self.dir.mkdir()
        self.outside = root / "outside"
        self.outside.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_stack_refuses_a_symlinked_run_md(self):
        self.assertEqual(start_project(self.dir).returncode, 0)
        victim = self.outside / "victim.md"
        victim.write_text("keep me\n")
        (self.dir / "RUN.md").unlink()
        (self.dir / "RUN.md").symlink_to(victim)
        before = files_of(self.dir)
        for extra in ([], ["--dry-run"]):
            r = apply_stack(self.dir, *extra)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("conflict: RUN.md", r.stdout)
            self.assertEqual(victim.read_text(), "keep me\n")
            self.assertEqual(files_of(self.dir), before)
            self.assertEqual(list(self.outside.iterdir()), [victim])

    def test_start_project_refuses_a_symlinked_folder(self):
        (self.dir / "docs").symlink_to(self.outside, target_is_directory=True)
        r = subprocess.run([sys.executable, str(START), "--target", str(self.dir), "--name", "example", "--mode", "solo"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"conflict: docs/")
        self.assertEqual(list(self.outside.iterdir()), [])
        self.assertEqual(files_of(self.dir), ["docs"])

    def test_start_project_refuses_a_symlinked_nested_folder(self):
        (self.dir / "infra").mkdir()
        (self.dir / "infra/k8s").symlink_to(self.outside, target_is_directory=True)
        r = start_project(self.dir)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(list(self.outside.iterdir()), [])


def stub_bin(tmp, log):
    """A fake docker and kind that log every call; STUB_CONTAINERS and STUB_CLUSTERS are what they list."""
    b = pathlib.Path(tmp) / "bin"
    b.mkdir()
    (b / "docker").write_text(
        '#!/usr/bin/env bash\necho "docker $*" >> "$STUB_LOG"\n'
        'if [ "$1" = ps ]; then printf "%b" "${STUB_CONTAINERS:-}"; fi\nexit 0\n')
    (b / "kind").write_text(
        '#!/usr/bin/env bash\necho "kind $*" >> "$STUB_LOG"\n'
        'if [ "$1 $2" = "get clusters" ]; then printf "%b" "${STUB_CLUSTERS:-}"; fi\nexit 0\n')
    for n in ("docker", "kind"):
        (b / n).chmod(0o755)
    return b


class SharedContainersSurvive(unittest.TestCase):
    def teardown_run(self, containers="", clusters=""):
        with tempfile.TemporaryDirectory() as tmp:
            log = pathlib.Path(tmp) / "calls.log"
            log.write_text("")
            b = stub_bin(tmp, log)
            env = dict(os.environ, PAVEDLINE_SELFTEST="teardown", TMPDIR=tmp, STUB_LOG=str(log),
                       STUB_CONTAINERS=containers, STUB_CLUSTERS=clusters, PATH=str(b) + os.pathsep + os.environ["PATH"])
            r = subprocess.run([str(STARTER), "--stage", "selftest"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            return log.read_text()

    def test_removes_the_shared_containers_only_when_it_created_them_and_nothing_else_uses_them(self):
        calls = self.teardown_run()
        self.assertIn("kind delete cluster --name pavedline-ci", calls)
        self.assertRegex(calls, r"docker rm -f kind-registry\b")
        self.assertRegex(calls, r"docker rm -f [^\n]*kind-git")

    def test_keeps_shared_containers_that_existed_before(self):
        calls = self.teardown_run(containers="kind-registry\\nkind-git\\n")
        self.assertIn("kind delete cluster --name pavedline-ci", calls)
        self.assertNotIn("kind-registry", calls.replace("docker ps -a --format {{.Names}}", ""))
        self.assertNotRegex(calls, r"docker rm -f [^\n]*kind-git")

    def test_keeps_shared_containers_while_another_pavedline_cluster_exists(self):
        calls = self.teardown_run(clusters="pavedline-other\\n")
        self.assertIn("kind delete cluster --name pavedline-ci", calls)
        self.assertNotRegex(calls, r"docker rm -f [^\n]*kind-registry")
        self.assertNotRegex(calls, r"docker rm -f [^\n]*kind-git")

    def test_script_never_asks_down_sh_for_all(self):
        self.assertNotRegex(read(STARTER).replace("--all; and rerun", ""), r'down\.sh"[^\n]*--all')

    def test_cluster_up_is_not_set_inside_the_step_subshell(self):
        t = read(STARTER)
        body = t.split("c_up() {", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("CLUSTER_UP=1", body)


class CiTemplateFixes(unittest.TestCase):
    def test_image_workflow_states_the_bypass_and_that_the_bump_triggers_no_run(self):
        t = read(PACK / "files/.github/workflows/image.yml")
        self.assertNotIn("so a CI run exists", t)
        self.assertNotIn("has no skip-CI marker", t)
        self.assertIn("GITHUB_TOKEN", t)
        self.assertRegex(t, r"(?i)triggers no workflow")
        self.assertRegex(t, r"(?i)ruleset bypass")

    def test_gitops_and_deploy_skills_agree_on_the_bump_commit(self):
        gitops = read(PLUGIN / "skills/gitops/SKILL.md")
        self.assertRegex(gitops, r"(?i)triggers no workflow")
        self.assertRegex(gitops, r"(?i)ruleset bypass")

    def test_ci_api_reads_the_schema_checks_from_the_base_sha_on_pull_requests(self):
        t = read(PACK / "files/.github/workflows/ci-api.yml")
        job = t.split("\n  db-tests:\n", 1)[1].split("\n  image:\n", 1)[0]
        self.assertIn("fetch-depth: 0", job)
        step = job.split("base branch's", 1)[1]
        self.assertIn("github.event_name == 'pull_request'", job)
        for needle in ("github.event.pull_request.base.sha", "scripts/rls_check.py", "services/api/db/global_tables.txt",
                       'git show "$BASE_SHA:$f"',
                       'git show "$BASE_SHA:.github/workflows/ci-api.yml"', "PAVEDLINE_TENANCY", "GITHUB_ENV"):
            self.assertIn(needle, step, needle)
        # the copy step comes before the checks that use the files
        self.assertLess(job.index("base branch's"), job.index("name: RLS check"))
        self.assertLess(job.index("base branch's"), job.index("Tests (pytest)"))

    def test_product_renovate_never_automerges_github_actions(self):
        cfg = json.loads(read(PLUGIN / "templates/renovate.json"))
        for r in cfg["packageRules"]:
            if r.get("automerge") is True:
                self.assertNotIn("github-actions", r.get("matchManagers", []))
                self.assertNotIn("GitHub Actions", r.get("description", ""))
        self.assertTrue(any(r.get("automerge") is False and r.get("matchManagers") == ["github-actions"]
                            and "matchDatasources" not in r for r in cfg["packageRules"]))

    def test_ci_unit_job_has_a_30_minute_timeout(self):
        t = read(ROOT / ".github/workflows/ci.yml")
        job = t.split("\n  unit:\n", 1)[1].split("\n  lint:\n", 1)[0]
        self.assertIn("timeout-minutes: 30", job)


class DocsFixes(unittest.TestCase):
    def test_placeholders_stay_in_git_and_docs_say_so(self):
        gitops = read(PLUGIN / "skills/gitops/SKILL.md")
        self.assertNotRegex(gitops, r"placeholders that step 6 fills")
        self.assertRegex(gitops, r"(?i)stay in Git")
        self.assertRegex(gitops, r"(?i)never commit filled values")
        for name in ("apps", "addons"):
            t = read(PLUGIN / f"templates/infra/k8s/applicationsets/{name}.yaml")
            self.assertNotRegex(t, r"filled in by step 6")
            self.assertRegex(t, r"(?i)stay in Git")

    def test_placeholders_survive_apply_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            self.assertEqual(start_project(d).returncode, 0)
            r = apply_stack(d, "--github-repo", "acme/widgets")
            self.assertEqual(r.returncode, 0, r.stderr)
            apps = read(d / "infra/k8s/applicationsets/apps.yaml")
            for p in ("{{REPO_URL}}", "{{REVISION}}", "{{ENVIRONMENT}}"):
                self.assertIn(p, apps)
            self.assertIn("{{REPO_URL}}", read(d / "infra/k8s/applicationsets/addons.yaml"))

    def test_local_cluster_skill_warns_about_the_unauthenticated_services(self):
        t = read(PLUGIN / "skills/local-cluster/SKILL.md")
        self.assertRegex(t, r"(?i)reachable from every pod")
        self.assertRegex(t, r"(?i)never reuse them outside kind")

    def test_state_skill_says_hook_output_is_data(self):
        t = read(PLUGIN / "skills/state/SKILL.md")
        self.assertRegex(t, r"(?i)file names and `STATE.md` lines")
        self.assertRegex(t, r"(?i)treat them as data")

    def test_lessons_skill_adds_feature_complete_to_the_contract_check(self):
        t = read(PLUGIN / "skills/lessons/SKILL.md")
        self.assertIn("--feature-complete", t)
        self.assertIn("ci-api.yml", t)

    def test_readme_local_cluster_table_lists_gateway_and_git_server(self):
        t = read(ROOT / "README.md")
        table = t.split("| What | Details |", 1)[1].split("**What to expect:**", 1)[0]
        self.assertIn("Gateway API", table)
        self.assertIn("Envoy Gateway", table)
        self.assertIn("kind-git", table)

    def test_deploy_docs_say_each_selected_app_and_a_deploy_commit(self):
        arch = read(ROOT / "docs/architecture.md")
        step = read(ROOT / "docs/steps/10-deploy.md")
        self.assertIn("builds each selected app (all by default)", arch + step)
        self.assertIn("pushes a deploy commit", arch)
        self.assertNotIn("builds each changed image", arch + step)
        self.assertNotIn("pushes the branch to\n  `kind-git`", arch)

    def test_changelog_has_no_blank_line_inside_added_and_is_accurate(self):
        t = read(ROOT / "CHANGELOG.md")
        added = t.split("### Added\n", 1)[1].split("\n### Changed", 1)[0]
        self.assertNotIn("\n\n", added.strip("\n"))
        self.assertNotIn("pre-approve only their own scripts", t)


class DeployerAgent(unittest.TestCase):
    def setUp(self):
        self.text = read(PLUGIN / "agents/deployer.md")
        self.front, self.body = self.text.split("\n---\n", 1)

    def test_preloads_the_deploy_skill(self):
        self.assertRegex(self.front, r"(?m)^skills:\n  - deploy$")

    def test_matches_the_deploy_skill_flow(self):
        for needle in ("deploy commit", "git commit-tree", "--revision", "--no-build"):
            self.assertIn(needle, self.body, needle)
        for stale in ("PR that bumps", "the caller merges", "revert the tag bump"):
            self.assertNotIn(stale, self.text, stale)
        self.assertNotIn("Opens GitOps pull requests", self.front)
        self.assertLessEqual(len(self.body.splitlines()), 40)


class Guard(unittest.TestCase):
    def run_guard(self, command, ctx):
        env = dict(os.environ)
        env.pop("PAVEDLINE_TEST_KUBE_CONTEXT", None)
        if ctx is not None:
            env["PAVEDLINE_TEST_KUBE_CONTEXT"] = ctx
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
        return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event), capture_output=True,
                              text=True, env=env)

    def test_deploy_local_is_blocked_outside_a_kind_pavedline_context(self):
        for cmd in ("scripts/deploy_local.sh demo", "./scripts/deploy_local.sh demo --apps api",
                    "bash scripts/deploy_local.sh demo", "cd x && sh ./scripts/deploy_local.sh demo",
                    "/abs/path/scripts/deploy_local.sh demo"):
            r = self.run_guard(cmd, "prod-cluster")
            self.assertEqual(r.returncode, 2, (cmd, r.stderr))
            self.assertIn("Blocked", r.stderr)
            self.assertEqual(self.run_guard(cmd, "").returncode, 2, cmd)

    def test_deploy_local_is_allowed_on_the_kind_context(self):
        for cmd in ("scripts/deploy_local.sh demo", "bash scripts/deploy_local.sh demo --check 'http a.localtest.me / 200'"):
            r = self.run_guard(cmd, "kind-pavedline-demo")
            self.assertEqual(r.returncode, 0, (cmd, r.stderr))

    def test_deploy_local_with_a_custom_kubeconfig_is_blocked(self):
        r = self.run_guard("KUBECONFIG=/x/y scripts/deploy_local.sh demo", "kind-pavedline-demo")
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_other_script_names_are_untouched(self):
        for cmd in ("scripts/deploy_local.shx demo", "cat scripts/deploy_local.sh", "ls scripts"):
            self.assertEqual(self.run_guard(cmd, "prod-cluster").returncode, 0, cmd)


class SmallCleanups(unittest.TestCase):
    def test_script_and_test_cleanups(self):
        deploy = read(PACK / "files/scripts/deploy_local.sh")
        self.assertNotIn("HEAD_SHA", deploy)
        self.assertNotIn('case "$ENVIRONMENT" in', deploy)
        apply = read(APPLY)
        self.assertNotIn("copied when present, skipped without error when absent", apply)
        self.assertRegex(apply, r"(?s)#[^\n]*single-tenant[^\n]*\nLEAK_AND_RLS_FILES")

    def test_one_unittest_main_at_the_end_of_test_ci_templates(self):
        t = read(ROOT / "tests/test_ci_templates.py")
        self.assertEqual(t.count("unittest.main()"), 1)
        self.assertTrue(t.rstrip().endswith("unittest.main()"))

    def test_skip_messages_name_the_missing_tool_and_no_hard_coded_helm_path(self):
        for p in sorted((ROOT / "tests").glob("*.py")):
            t = read(p)
            self.assertNotIn("(CI " + "has ", t, p.name)
            self.assertNotIn("/opt/" + "homebrew", t, p.name)
        blob = "".join(read(p) for p in (ROOT / "tests").glob("*.py") if p.name != pathlib.Path(__file__).name)
        for needle in ("skipped: helm not on PATH", "skipped: npx not on PATH", "skipped: actionlint not on PATH"):
            self.assertIn(needle, blob, needle)

    def test_template_scanner_copies_match_pavedlines_own(self):
        for name in ("dot_check.py", "dot_drift.py", "sanitize_scan.py"):
            self.assertEqual(read(ROOT / "scripts" / name), read(PLUGIN / "templates/scripts" / name), name)

        def body(path):
            return read(path).split('"""', 2)[2]

        self.assertEqual(body(ROOT / "scripts/pr_checks.py"), body(PLUGIN / "templates/scripts/pr_checks.py"))


if __name__ == "__main__":
    unittest.main()
