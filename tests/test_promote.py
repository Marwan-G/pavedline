import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/pavedline/stacks/nextjs-fastapi/files/scripts/promote.py"
STG = "sha256:" + "1" * 64
OLD = "sha256:" + "2" * 64
ZERO = "sha256:" + "0" * 64


def values(digest, extra=""):
    return ('workloads:\n  api:\n    image:\n      repository: ghcr.io/acme/items/api\n      digest: "%s"\n'
            "    replicas: 3\n%s" % (digest, extra))


class Promote(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self.tmp.name)
        app = self.d / "infra/k8s/apps/api"
        app.mkdir(parents=True)
        (app / "values-staging.yaml").write_text(values(STG))
        (app / "values-production.yaml").write_text(values(OLD, "    env:\n      APP_ENV: production\n"))
        (self.d / "docs/production").mkdir(parents=True)
        self.git("init", "-q", ".")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "staging build")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.bin = self.d / "bin"
        self.bin.mkdir()
        self.log = self.d / "calls.log"
        real = shutil.which("git")
        # git: logs, then runs the real git (promote may read with `git show`); gh: logs only
        (self.bin / "git").write_text('#!/bin/sh\necho "git $*" >> "%s"\nexec %s "$@"\n' % (self.log, real))
        (self.bin / "gh").write_text('#!/bin/sh\necho "gh $*" >> "%s"\n' % self.log)
        for n in ("git", "gh"):
            (self.bin / n).chmod(0o755)

    def git(self, *a):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *a], cwd=self.d,
                              capture_output=True, text=True, check=True).stdout

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, line):
        (self.d / "docs/production/deployments.md").write_text("# Deployments\n\n" + line + "\n")

    def run_promote(self, sha=None, *extra):
        sha = sha or self.sha
        env = dict(os.environ, PATH="%s:%s" % (self.bin, os.environ["PATH"]))
        return subprocess.run([sys.executable, str(SCRIPT), "--sha", sha, *extra], cwd=self.d, env=env,
                              capture_output=True, text=True)

    def prod(self):
        return (self.d / "infra/k8s/apps/api/values-production.yaml").read_text()

    def test_no_record_refuses(self):
        before = self.prod()
        r = self.run_promote()
        self.assertEqual(r.returncode, 1)
        self.assertIn("refused", r.stdout)
        self.assertEqual(self.prod(), before)

    def test_record_for_other_sha_refuses(self):
        self.record("staging · %s · verified (cloud) · 2026-11-09" % ("b" * 40))
        self.assertEqual(self.run_promote().returncode, 1)

    def test_local_only_record_refuses(self):
        self.record("staging · %s · verified (local) · 2026-11-09" % self.sha)
        self.assertEqual(self.run_promote().returncode, 1)

    def test_record_rewrites_only_digest(self):
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        r = self.run_promote()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.prod(), values(STG, "    env:\n      APP_ENV: production\n"))
        self.assertIn("git switch -c promote/%s" % self.sha[:7], r.stdout)
        self.assertIn("gh pr create", r.stdout)
        self.assertEqual((self.d / "infra/k8s/apps/api/values-staging.yaml").read_text(), values(STG))

    def test_never_calls_git_or_gh(self):
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        self.run_promote()
        calls = self.log.read_text().splitlines() if self.log.exists() else []
        for c in calls:
            self.assertTrue(c.startswith("git show "), c)

    def test_placeholder_staging_digest_refuses(self):
        (self.d / "infra/k8s/apps/api/values-staging.yaml").write_text(values(ZERO))
        self.git("commit", "-q", "-am", "zero")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        before = self.prod()
        self.assertEqual(self.run_promote().returncode, 1)
        self.assertEqual(self.prod(), before)

    def test_digests_come_from_the_verified_sha_not_the_working_tree(self):
        later = "sha256:" + "4" * 64
        (self.d / "infra/k8s/apps/api/values-staging.yaml").write_text(values(later))  # later, unverified build
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        r = self.run_promote()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(STG, self.prod())
        self.assertNotIn(later, self.prod())

    def test_sha_without_a_digest_bump_refuses(self):
        (self.d / "infra/k8s/apps/api/values-staging.yaml").write_text("workloads:\n  api:\n    replicas: 2\n")
        self.git("commit", "-q", "-am", "no bump")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        before = self.prod()
        self.assertEqual(self.run_promote().returncode, 1)
        self.assertEqual(self.prod(), before)

    def test_staging_file_absent_at_sha_refuses(self):
        self.git("rm", "-q", "infra/k8s/apps/api/values-staging.yaml")
        self.git("commit", "-q", "-m", "rm")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        self.assertEqual(self.run_promote().returncode, 1)

    def test_record_inside_a_code_fence_is_an_error(self):
        (self.d / "docs/production/deployments.md").write_text(
            "# D\n\n```\nstaging · %s · verified (cloud) · 2026-11-09\n```\n" % self.sha)
        r = self.run_promote()
        self.assertEqual(r.returncode, 1)
        self.assertIn("inside a code block", r.stdout)

    def test_unclosed_fence_in_record_is_an_error(self):
        (self.d / "docs/production/deployments.md").write_text(
            "# D\n\n```\nnote\nstaging · %s · verified (cloud) · 2026-11-09\n" % self.sha)
        r = self.run_promote()
        self.assertEqual(r.returncode, 1)
        self.assertIn("unclosed", r.stdout)

    def test_printed_arguments_are_shell_quoted(self):
        weird = "infra/k8s/apps; touch pwned"
        shutil.copytree(self.d / "infra/k8s/apps", self.d / weird)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "copy")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.record("staging · %s · verified (cloud) · 2026-11-09" % self.sha)
        r = self.run_promote(self.sha, "--apps-dir", weird)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("git add 'infra/k8s/apps; touch pwned'/*/values-production.yaml", r.stdout)
        self.assertNotIn("git add infra/k8s/apps; touch", r.stdout)

    def test_short_sha_rejected(self):
        self.assertEqual(self.run_promote("abc1234").returncode, 2)

    def test_pack_lists_it_and_exclusions(self):
        pack = (ROOT / "plugins/pavedline/stacks/nextjs-fastapi/pack.yaml").read_text()
        self.assertIn("scripts/promote.py", pack)
        py = (ROOT / "plugins/pavedline/stacks/nextjs-fastapi/files/services/api/pyproject.toml").read_text()
        self.assertEqual(py.count("../../scripts/promote.py"), 2)


class PromoteRealPackTree(unittest.TestCase):
    """The promotion run against the pack's real chart tree (api, web, site, postgres)."""

    def test_chart_without_an_image_digest_is_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            shutil.copytree(ROOT / "plugins/pavedline/stacks/nextjs-fastapi/files/infra/k8s", d / "infra/k8s")
            shutil.copytree(ROOT / "plugins/pavedline/templates/infra/helm", d / "infra/helm")
            for app in ("api", "web", "site"):
                f = d / "infra/k8s/apps" / app / "values-staging.yaml"
                f.write_text(f.read_text().replace("sha256:" + "0" * 64, STG))
            (d / "docs/production").mkdir(parents=True)

            def git(*a):
                return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *a], cwd=d,
                                      capture_output=True, text=True, check=True).stdout
            git("init", "-q", ".")
            git("add", "-A")
            git("commit", "-q", "-m", "staging build")
            sha = git("rev-parse", "HEAD").strip()
            (d / "docs/production/deployments.md").write_text(
                "staging · %s · verified (cloud) · 2026-11-09\n" % sha)
            r = subprocess.run([sys.executable, str(SCRIPT), "--sha", sha], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("skipped: infra/k8s/apps/postgres/values-production.yaml (no image to promote)", r.stdout)
            for app in ("api", "web", "site"):
                self.assertIn(STG, (d / "infra/k8s/apps" / app / "values-production.yaml").read_text())
            self.assertNotIn("promotion NOT done", r.stdout)


if __name__ == "__main__":
    unittest.main()
