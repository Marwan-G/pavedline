import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/pavedline/scripts/plan_graph.py"
TEMPLATES = ROOT / "plugins/pavedline/templates/docs"

SPEC = """# Spec

## 5. Acceptance tests

- AT-001 (Web app): Given a user, when they sign in, then they see items.
- AT-002 (Web app): Given a user, when they add an item, then it is listed.
- AT-003 (Mobile app): Given a user, when they open the app, then they see items.

## 6. Non-functional needs

Nothing about AT-099 here.
"""

DECISION_5 = """# 0005. Surfaces

- Date: 2026-11-09
- Status: accepted

## Decision

Web app and API only.
"""

PLAN = """# Wave 1

### Slice 1.1: Sign in
Tests: AT-001
Surfaces: web, api
Branch: slice-1-1-sign-in
Depends on: none

### Slice 1.2: Add item
Tests: AT-002
Surfaces: web, api
Branch: slice-1-2-add-item
Depends on: 1.1
"""

PLAN_FULL = PLAN + """
### Slice 1.3: Mobile list
Tests: AT-003
Surfaces: api
Branch: slice-1-3-mobile-list
Depends on: 1.1
"""


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          cwd=repo, capture_output=True, text=True, check=True)


class PlanGraph(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = pathlib.Path(self.tmp)
        git(self.repo, "init", "-q", "-b", "main")
        self.write("docs/spec/SPEC.md", SPEC)
        self.write("decisions/0005-surfaces.md", DECISION_5)
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN_FULL)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def run_(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--repo", str(self.repo)],
                              capture_output=True, text=True)

    def commit(self, msg):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg)

    def test_clean_plan_passes(self):
        r = self.run_("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unmapped_test_exit_1(self):
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN)
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unmapped: AT-003", r.stdout)

    def test_non_acceptance_section_ids_ignored(self):
        self.assertNotIn("AT-099", self.run_("check").stdout)

    def test_duplicate_slice_exit_1(self):
        self.write("docs/plans/2026-11-10-wave-2.md",
                   "### Slice 1.1: Again\nTests: AT-001\nSurfaces: api\nBranch: b\nDepends on: none\n")
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicate slice id: 1.1", r.stdout)

    def test_unknown_test_exit_1(self):
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN_FULL.replace("Tests: AT-002", "Tests: AT-002, AT-050"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown test: AT-050", r.stdout)

    def test_cycle_exit_1(self):
        self.write("docs/plans/2026-11-09-wave-1.md",
                   PLAN_FULL.replace("Depends on: none", "Depends on: 1.2"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cycle", r.stdout)

    def test_unknown_dependency_exit_1(self):
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN_FULL.replace("Depends on: 1.1\n\n###", "Depends on: 9.9\n\n###"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown dependency", r.stdout)

    def test_test_mapped_twice_warns(self):
        self.write("docs/plans/2026-11-10-wave-2.md",
                   "### Slice 2.1: More\nTests: AT-001\nSurfaces: api\nBranch: b\nDepends on: none\n")
        r = self.run_("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("warning: AT-001 mapped twice", r.stdout)

    def test_re_tests_not_a_second_mapping(self):
        self.write("docs/plans/2026-11-10-wave-2.md",
                   "### Slice 2.1: More\nTests: none\nRe-tests: AT-001\nSurfaces: api\nBranch: b\nDepends on: none\n")
        r = self.run_("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("mapped twice", r.stdout)

    def test_surface_not_in_decision_exit_1(self):
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN_FULL.replace("Surfaces: api\n", "Surfaces: mobile\n"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("surface not selected", r.stdout)

    def test_surface_decision_missing_warns(self):
        (self.repo / "decisions/0005-surfaces.md").unlink()
        r = self.run_("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("warning: decision 0005", r.stdout)

    def test_accepted_intent_warns(self):
        self.write("docs/intent/2026-11-09-export.md", "# Export\n\nStatus: accepted\nDate: 2026-11-09\n")
        self.write("docs/intent/2026-11-09-done.md", "# Done\n\nStatus: accepted → specced in decision 0008\n")
        self.write("docs/intent/2026-11-09-idea.md", "# Idea\n\nStatus: proposed\n")
        r = self.run_("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("accepted intents not yet specced", r.stdout)
        self.assertIn("2026-11-09-export.md", r.stdout)
        self.assertNotIn("2026-11-09-done.md", r.stdout)
        self.assertNotIn("2026-11-09-idea.md", r.stdout)

    def test_no_spec_exit_2(self):
        (self.repo / "docs/spec/SPEC.md").unlink()
        self.assertEqual(self.run_("check").returncode, 2)

    def test_status_not_complete_until_all_merged(self):
        self.commit("start")
        r = self.run_("status")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("feature-complete", r.stdout)
        self.assertIn("1.1", r.stdout)
        self.commit_slice("1.1")
        self.commit_slice("1.2")
        r = self.run_("status")
        self.assertEqual(r.returncode, 1)
        self.assertIn("open: 1.3", r.stdout)
        self.assertNotIn("feature-complete", r.stdout)
        self.commit_slice("1.3")
        r = self.run_("status")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("feature-complete", r.stdout)

    def commit_slice(self, sid):
        self.write("f%s.txt" % sid, sid)
        self.commit("Slice %s: done\n\nGates: ok" % sid)

    def test_slice_id_match_is_exact(self):
        self.commit("start")
        self.commit_slice("1.10")
        self.assertIn("open: 1.1", self.run_("status").stdout)

    def test_status_with_unmapped_test_not_complete(self):
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN)
        self.commit("start")
        self.commit_slice("1.1")
        self.commit_slice("1.2")
        r = self.run_("status")
        self.assertEqual(r.returncode, 1)
        self.assertIn("AT-003", r.stdout)

    def test_dot_writes_and_validates(self):
        plan = self.repo / "docs/plans/2026-11-09-wave-1.md"
        r = subprocess.run([sys.executable, str(SCRIPT), "dot", str(plan)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dot = plan.with_suffix(".dot")
        t = dot.read_text()
        self.assertIn("digraph", t)
        self.assertIn('"1.1" -> "1.2"', t)
        self.assertIn("cluster_wave_1", t)
        if shutil.which("dot"):
            v = subprocess.run(["dot", "-Tcanon", "-o", "/dev/null", str(dot)], capture_output=True, text=True)
            self.assertEqual(v.returncode, 0, v.stderr)

    def test_dot_without_plan_exit_2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "dot", str(self.repo / "nope.md")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def commit_msg(self, msg):
        self.write("g%d.txt" % len(msg), msg)
        self.commit(msg)

    def merge_all_but(self):
        self.commit("start")
        for s in ("1.1", "1.2", "1.3"):
            self.commit_slice(s)

    def test_revert_unmerges_slice(self):
        self.merge_all_but()
        self.assertIn("feature-complete", self.run_("status").stdout)
        self.commit_msg('Revert "Slice 1.2: done"\n\nThis reverts Slice 1.2: done')
        r = self.run_("status")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("feature-complete", r.stdout)
        self.assertIn("open: 1.2", r.stdout)
        self.commit_msg('Revert "Revert "Slice 1.2: done""')
        self.assertIn("feature-complete", self.run_("status").stdout)

    def test_body_prose_not_merged(self):
        self.commit("start")
        self.commit_msg("Fix typo\n\nThis follows Slice 1.2 and Slice 1.1")
        self.assertIn("open: 1.1, 1.2, 1.3", self.run_("status").stdout)

    def test_trailer_counts(self):
        self.commit("start")
        self.commit_msg("Add sign in\n\nSlice: 1.1")
        self.assertIn("open: 1.2, 1.3", self.run_("status").stdout)

    def test_default_branch_preferred_over_feature_checkout(self):
        self.commit("start")
        git(self.repo, "checkout", "-q", "-b", "feature")
        self.commit_slice("1.1")
        self.assertIn("open: 1.1", self.run_("status").stdout)

    def test_check_prints_test_count(self):
        self.assertIn("3 acceptance tests", self.run_("check").stdout)
        self.write("docs/spec/SPEC.md", "# Spec\n\n## 5. Acceptance tests\n\nnone yet\n")
        r = self.run_("check")
        self.assertIn("0 acceptance tests", r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_deferred_tests_pass_check_but_never_complete(self):
        self.write("docs/plans/2026-11-09-wave-1.md",
                   PLAN.replace("# Wave 1\n", "# Wave 1\n\nDeferred: AT-003 (later waves)\n"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("1 tests deferred to later waves: AT-003", r.stdout)
        self.commit("start")
        self.commit_slice("1.1")
        self.commit_slice("1.2")
        r = self.run_("status")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("feature-complete", r.stdout)
        self.assertIn("AT-003", r.stdout)

    def test_deferred_unknown_test_exit_1(self):
        self.write("docs/plans/2026-11-09-wave-1.md",
                   PLAN_FULL.replace("# Wave 1\n", "# Wave 1\n\nDeferred: AT-077\n"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown test: AT-077", r.stdout)

    def test_structured_surfaces_beat_negated_text(self):
        self.write("decisions/0005-surfaces.md",
                   "# 0005\n\nSurfaces: web, api\n\n## Decision\n\nNo mobile app for now.\n")
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN_FULL.replace("Surfaces: api\n", "Surfaces: mobile\n"))
        r = self.run_("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("surface not selected", r.stdout)
        self.assertNotIn("falling back", r.stdout)

    def test_free_text_fallback_warns(self):
        r = self.run_("check")
        self.assertIn("warning: decision 0005 has no `Surfaces:` line; falling back to words", r.stdout)


class IntentAndPlanTemplates(unittest.TestCase):
    def test_intent_template(self):
        t = (TEMPLATES / "intent/0000-template.md").read_text()
        self.assertIn("Status: proposed | accepted | rejected", t)
        self.assertIn("Source: founder | retro <date> | incident <id>", t)
        for h in ("Problem", "Proposed outcome", "Affected users and systems", "Constraints", "Open questions"):
            self.assertRegex(t, r"(?m)^## %s$" % h)

    def test_readmes_short_and_in_rules_index(self):
        for rel in ("intent/README.md", "plans/README.md"):
            self.assertLessEqual(len((TEMPLATES / rel).read_text().splitlines()), 10, rel)
        idx = (TEMPLATES / "rules-index.md").read_text()
        for home in ("docs/intent/", "docs/plans/", "docs/retros/", "docs/reviews/"):
            self.assertRegex(idx, r"\|[^|\n]+\| `" + home + r"` \|", home)

    def test_plans_readme_has_slice_format(self):
        t = (TEMPLATES / "plans/README.md").read_text()
        for s in ("### Slice <wave>.<n>: <title>", "Tests:", "Surfaces:", "Branch:", "Depends on:", "Deferred: AT-"):
            self.assertIn(s, t)


if __name__ == "__main__":
    unittest.main()
