import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PLUGIN = ROOT / "plugins" / "pavedline"
SKILL = PLUGIN / "skills" / "go-to-production"
RULES = PLUGIN / "skills/state/references/step-rules.md"
POINTER = "Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`."


def skill():
    """The body, after the frontmatter (whose description repeats key phrases)."""
    return (SKILL / "SKILL.md").read_text().split("\n---\n", 1)[1]


def allrefs():
    return skill() + "\n".join(f.read_text() for f in sorted((SKILL / "references").glob("*.md")))


class Step12(unittest.TestCase):
    def test_files_exist(self):
        for f in ("SKILL.md", "references/intake.md", "references/launch.md", "references/sources.md"):
            self.assertTrue((SKILL / f).is_file(), f)
        for f in ("INFRA.md", "NEEDS.md", "LAUNCH.md"):
            self.assertTrue((PLUGIN / "templates/docs/production" / f).is_file(), f)

    def test_question_order(self):
        t = skill()
        a = t.index("Is it time to go to production?")
        b = t.index("what do you already have?")
        c = t.index("What I need from you")
        d = t.index("Provision")
        e = t.index("Go live?")
        self.assertTrue(a < b < c < d < e)
        intake = (SKILL / "references/intake.md").read_text().lower()
        order = ["cloud account", "existing cluster", "regions", "domain and dns", "container registry",
                 "secrets store", "object storage", "managed database", "email domain", "budget ceiling"]
        pos = [intake.index(o) for o in order]
        self.assertEqual(pos, sorted(pos))
        self.assertIn("one adr per answer", t.lower())

    def test_refusal_before_feature_complete_and_integration_wave(self):
        t = skill()
        self.assertIn("plan_graph.py status", t)
        for s in ("refuse", "feature-complete", "`integration wave: done`"):
            self.assertIn(s, t)
        self.assertLess(t.index("plan_graph.py status"), t.index("Is it time to go to production?"))

    def test_waits_for_the_line_plan_graph_prints(self):
        # Contract with plan_graph.py status (integration wave section): the exact line step 12 waits for.
        src = (ROOT / "plugins/pavedline/scripts/plan_graph.py").read_text()
        self.assertIn("integration wave: ", src)
        self.assertIn('"done"', src)

    def test_needs_mirrored_to_waiting(self):
        t = skill()
        for s in ("docs/production/NEEDS.md", "WAITING.md", "also a line in `WAITING.md`"):
            self.assertIn(s, t)

    def test_every_apply_is_the_founders(self):
        t = skill()
        for s in ("the founder's", "never run kubectl, helm, tofu or terraform against a cloud context",
                  "never into chat", "vault"):
            self.assertIn(s, t)
        self.assertIn("The agent prints each command and stops", t)

    def test_plan_check_before_apply_for_oci(self):
        t = skill()
        self.assertIn("plan_check.py", t)
        self.assertLess(t.index("plan_check.py"), t.index("the founder applies only after"))
        self.assertIn("0 to destroy", t)
        self.assertIn("oci-oke/SOURCES.md", (SKILL / "references/sources.md").read_text())
        for p in ("byo-kubernetes", "oci-oke"):
            self.assertIn("templates/infra/profiles", t)
            self.assertIn(p, t)

    def test_staging_before_production(self):
        t = skill()
        self.assertLess(t.index("Cloud staging first"), t.index("buffer wave"))
        self.assertLess(t.index("buffer wave"), t.index("Production** is promoted"))
        for s in ("verified (cloud)", "promote.py", "by pull request", "deployments.md", "sitemap"):
            self.assertIn(s, t)

    def test_launch_gate_and_go_live(self):
        t = skill()
        self.assertIn("launch_check.py", t)
        self.assertIn("\"Go live\" is refused unless it exits 0", t)
        self.assertLess(t.index("launch_check.py"), t.index("Go live?"))

    def test_go_live_points_at_grow(self):
        tail = skill().split("## 7.")[1]
        self.assertIn("STEP: Grow", tail)
        self.assertIn('date "+%Y-%m-%d %H:%M"', tail)
        self.assertIn("go?", tail)

    def test_pointer_and_size(self):
        self.assertIn(POINTER, skill())
        self.assertLessEqual(len(skill().splitlines()), 500)

    def test_launch_template_items(self):
        t = (PLUGIN / "templates/docs/production/LAUNCH.md").read_text().lower()
        items = re.findall(r"^- \[ \] (.*)$", t, re.M)
        self.assertGreaterEqual(len(items), 10)
        for s in ("processor agreements", "payment and sms", "store approvals", "legal pages", "compliance",
                  "restore tested in the cloud", "restore_drill.sh", "load targets", "accessibility audit",
                  "three alerts", "observability decision"):
            self.assertIn(s, t)

    def test_run_md_sections(self):
        t = (PLUGIN / "templates/RUN.md").read_text()
        self.assertIn("## Secret rotation", t)
        self.assertIn("## Break-glass", t)

    def test_deploy_and_agents(self):
        d = (PLUGIN / "skills/deploy/SKILL.md").read_text()
        for s in ("go-to-production", "promote.py", "verified (cloud)", "deployments.md"):
            self.assertIn(s, d)
        dep = (PLUGIN / "agents/deployer.md").read_text()
        self.assertIn("never run kubectl, helm, tofu or terraform against a cloud context", dep)
        self.assertIn("go-to-production", (PLUGIN / "agents/architect.md").read_text())

    def test_eval_case(self):
        for f in ("case.yaml", "prompt.md", "scaffold.sh"):
            self.assertTrue((PLUGIN / "evals/go-to-production" / f).is_file(), f)

    def test_no_secrets_words(self):
        self.assertNotIn("paste the key", allrefs().lower())


if __name__ == "__main__":
    unittest.main()
