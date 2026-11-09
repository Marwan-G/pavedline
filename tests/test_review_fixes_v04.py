"""Fixes from the whole-branch review of v0.4: each repro is a test."""
import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PACK = PLUGIN / "stacks/nextjs-fastapi"
FILES = PACK / "files"


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


class StepChain(unittest.TestCase):
    def test_no_integration_wave_is_said_to_ship_later(self):
        for p in (PLUGIN / "skills/lessons/SKILL.md", ROOT / "docs/steps/11-learn.md", ROOT / "docs/steps/integration-wave.md"):
            self.assertNotIn("later release", read(p), p.name)

    def test_test_names_are_neutral(self):
        self.assertTrue((ROOT / "tests/test_skill_rules_v04.py").is_file())
        self.assertFalse((ROOT / "tests/test_trial_fixes.py").exists())
        text = read(ROOT / "tests/test_skill_rules_v04.py")
        self.assertIn("class SkillRulesV04", text)
        self.assertNotIn("trial", text.lower())

    def test_changelog_calls_marketing_optional(self):
        t = read(ROOT / "CHANGELOG.md")
        line = [l for l in t.splitlines() if "`marketing`" in l][0]
        self.assertNotIn("new dependency", line)
        self.assertIn("optional", line)


class PostgresPins(unittest.TestCase):
    def test_the_python_base_image_pin_is_identical_everywhere(self):
        files = [FILES / "services/api/Dockerfile", PLUGIN / "templates/infra/k8s/addons/alerts/values.yaml",
                 PLUGIN / "scripts/local-cluster/versions.env"]
        found = []
        for f in files:
            pins = re.findall(r"python:\d+\.\d+\.\d+-slim@sha256:[0-9a-f]{64}", read(f))
            self.assertTrue(pins, f.name)
            found += pins
        self.assertEqual(len(set(found)), 1, found)
        self.assertGreaterEqual(len(found), 4)  # the Dockerfile has two stages

    def test_ci_comment_says_same_major_with_its_own_minor(self):
        t = read(FILES / ".github/workflows/ci-api.yml")
        self.assertIn("same MAJOR", t)
        self.assertIn("its own minor", t)
        self.assertNotIn("Same major as the CloudNativePG image", t)

    def _managers(self, path):
        return json.loads(read(path))["customManagers"]

    def _matches(self, managers, target_file):
        hits = 0
        text = read(target_file)
        for m in managers:
            for ms in m["matchStrings"]:
                if re.search(ms.replace("(?<", "(?P<"), text):
                    hits += 1
        return hits

    def test_renovate_tracks_the_pack_postgres_images_and_the_chart_image(self):
        root = self._managers(ROOT / "renovate.json")
        self.assertEqual(self._matches(root, PACK / "pack.yaml"), 1)
        self.assertEqual(len(re.findall(r"(?m)^\s+(cluster|test): \S+@sha256:", read(PACK / "pack.yaml"))), 4)
        tmpl = self._managers(PLUGIN / "templates/renovate.json")
        self.assertEqual(self._matches(tmpl, FILES / "infra/k8s/apps/postgres/values.yaml"), 1)
        for cfg in (ROOT / "renovate.json", PLUGIN / "templates/renovate.json"):
            c = json.loads(read(cfg))
            rules = [r for r in c["packageRules"] if r.get("automerge") is False
                     and any("postgres" in str(v).lower() for v in r.values())]
            self.assertTrue(rules, cfg)


class ByoBootstrap(unittest.TestCase):
    BOOT = PLUGIN / "templates/infra/profiles/byo-kubernetes/bootstrap.sh"

    def run_boot(self, url):
        return subprocess.run(["bash", str(self.BOOT), "--context", "kind-pavedline-byo", "--repo-url", url, "--print"],
                              capture_output=True, text=True)

    def test_a_repo_url_with_userinfo_is_refused(self):
        for url in ("https://user@github.com/a/b", "https://user:pass@github.com/a/b", "https://tok@github.com/a/b.git"):
            r = self.run_boot(url)
            self.assertEqual(r.returncode, 2, url)
            self.assertIn("credentials", r.stderr, url)
            self.assertNotIn("pass", r.stdout, url)

    def test_a_plain_https_url_is_accepted(self):
        r = self.run_boot("https://github.com/acme/items")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_readme_enables_alerts_where_argo_reads_them(self):
        t = read(self.BOOT.parent / "README.md")
        step = t[t.index("**Enable the alerts**"):][:400]
        self.assertIn("infra/k8s/addons/alerts/values.yaml", step)
        self.assertNotIn("values-<environment>.yaml", step)


class Workflows(unittest.TestCase):
    def test_mobile_workflow_can_be_dispatched_and_watches_its_inputs(self):
        for name in ("starter-mobile.yml", "starter-full.yml"):
            t = read(ROOT / ".github/workflows" / name)
            self.assertRegex(t, r"(?m)^  workflow_dispatch:", name)
            for need in ("plugins/pavedline/scripts/**", "plugins/pavedline/templates/**",
                         "tests/fixtures/starter-answers.json"):
                self.assertEqual(t.count('"%s"' % need), 2, (name, need))  # pull_request and push

    def test_starter_check_help_prints_the_whole_header_and_no_code(self):
        r = subprocess.run(["bash", str(ROOT / "scripts/starter_check.sh"), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[-1].startswith("kind-pavedline-*. Exit 0 only if every step passed"), lines[-3:])
        self.assertNotIn("set -uo pipefail", r.stdout)
        self.assertTrue(all(not l.startswith("# ") for l in lines))


if __name__ == "__main__":
    unittest.main()
