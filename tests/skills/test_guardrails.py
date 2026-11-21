"""The guardrails registry: one skill holds the approach, and every place that records a decision, plans, builds,
reviews, learns or launches points to it."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PLUGIN = ROOT / "plugins" / "pavedline"
SKILL = PLUGIN / "skills" / "guardrails" / "SKILL.md"


def text(rel):
    return (PLUGIN / rel).read_text()


def flat(t):
    return re.sub(r"\s+", " ", t)


class GuardrailsSkill(unittest.TestCase):
    def setUp(self):
        self.t = flat(SKILL.read_text())

    def test_one_skill_holds_the_approach(self):
        self.assertIn("name: guardrails", self.t)
        for status in ("PROPOSED", "APPROVED", "IMPLEMENTED", "TESTED", "VERIFIED", "OPEN", "SUPERSEDED"):
            self.assertIn("| `%s` |" % status, self.t, status)
        for q in ("Introduces:", "Modifies:", "Removes or supersedes:", "Conflicts with:"):
            self.assertIn(q, self.t, q)
        for field in ("Rule", "Rationale", "Scope", "Enforcement", "Configuration", "Validation", "Related"):
            self.assertIn("**%s:**" % field, self.t, field)

    def test_evidence_and_ownership(self):
        self.assertIn("never rises on documentation alone", self.t)
        self.assertIn("only the session on `OWNER` writes it", self.t)
        self.assertIn("never resolved silently", self.t)

    def test_every_step_has_its_duty(self):
        for step in ("Steps 1–3", "Steps 4–7", "Step 8", "Step 9", "Step 10", "Step 11", "Integration wave", "Step 12"):
            self.assertIn("| %s |" % step, self.t, step)

    def test_one_review_cadence(self):
        self.assertIn("at adoption, before step 8, before step 12, and whenever the founder asks", self.t)
        self.assertIn("## Adopting the registry in a project that has none", SKILL.read_text())


class GuardrailsWiring(unittest.TestCase):
    """Each pointer is one line; the approach itself lives only in the skill."""

    def assert_points(self, rel, *needles):
        t = flat(text(rel))
        for n in needles:
            self.assertIn(n, t, "%s: %s" % (rel, n))

    def test_records_and_read_first_lists(self):
        self.assert_points("skills/state/references/step-rules.md", "skills/guardrails/SKILL.md",
                           '"Guardrails" section', "`SYSTEM-GUARDRAILS.md` if it exists")
        self.assert_points("skills/state/SKILL.md", "`guardrails` skill", "`SYSTEM-GUARDRAILS.md` if it exists")

    def test_decision_template_and_rules_index(self):
        t = text("templates/decisions/0000-template.md")
        self.assertLess(t.index("## Guardrails"), t.index("## Stale outputs"))
        self.assert_points("templates/docs/rules-index.md", "`SYSTEM-GUARDRAILS.md`")

    def test_step_0_and_step_3(self):
        self.assert_points("skills/start/SKILL.md", "`guardrails` skill")
        self.assert_points("skills/spec/SKILL.md", "`guardrails` skill")

    def test_plan_names_guardrails_per_slice(self):
        self.assert_points("skills/plan-graph/SKILL.md", "Guardrails: <guardrail IDs", "consistency review")
        self.assert_points("templates/docs/plans/README.md", "`Guardrails: <IDs or none>`")

    def test_builder_reports_and_owner_folds(self):
        self.assert_points("agents/builder.md", "`SYSTEM-GUARDRAILS.md` if it exists", "`Guardrails:` line",
                           "the owner folds your list in")
        self.assert_points("skills/quality-gates/SKILL.md", "`Guardrails:` line",
                           "guardrail list into `SYSTEM-GUARDRAILS.md`")

    def test_lessons_and_launch(self):
        self.assert_points("skills/lessons/SKILL.md", "`guardrails` skill")
        self.assert_points("skills/go-to-production/SKILL.md", "`guardrails` skill")
        self.assert_points("skills/go-to-production/references/launch.md", "`SYSTEM-GUARDRAILS.md`")
        self.assert_points("templates/docs/production/LAUNCH.md", "- [ ] The guardrail consistency review")


if __name__ == "__main__":
    unittest.main()
