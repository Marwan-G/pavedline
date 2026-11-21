"""The guardrails registry: one skill holds the approach, and every place a decision or a slice is recorded points to it."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PLUGIN = ROOT / "plugins" / "pavedline"
SKILL = PLUGIN / "skills" / "guardrails" / "SKILL.md"


def text(rel):
    return (PLUGIN / rel).read_text()


class GuardrailsSkill(unittest.TestCase):
    def test_one_skill_holds_the_approach(self):
        t = SKILL.read_text()
        self.assertIn("name: guardrails", t)
        self.assertIn("SYSTEM-GUARDRAILS.md", t)
        for status in ("PROPOSED", "APPROVED", "IMPLEMENTED", "TESTED", "VERIFIED", "OPEN"):
            self.assertIn("`%s`" % status, t, status)
        for q in ("Introduces:", "Modifies:", "Removes or supersedes:", "Conflicts with:"):
            self.assertIn(q, t, q)
        for field in ("Rule", "Rationale", "Scope", "Enforcement", "Configuration", "Validation", "Related"):
            self.assertIn("**%s:**" % field, t, field)
        for field in ("Category", "Status", "Source"):
            self.assertIn("**%s**" % field, t, field)

    def test_status_never_rises_on_documentation(self):
        t = SKILL.read_text()
        self.assertIn("never rises on documentation alone", t)
        self.assertIn("`file:line`", t)
        self.assertIn("passing run", t)

    def test_every_step_has_its_duty(self):
        t = SKILL.read_text()
        for step in ("Steps 1–3", "Steps 4–7", "Step 8", "Step 9", "Step 10", "Step 11", "Integration wave", "Step 12"):
            self.assertIn("| %s |" % step, t, step)

    def test_consistency_review_and_adoption(self):
        t = SKILL.read_text()
        self.assertIn("## Consistency review", t)
        self.assertIn("## Adopting the registry in a project that has none", t)
        self.assertIn("never resolved silently", t)


class GuardrailsWiring(unittest.TestCase):
    def test_the_shared_step_rules_point_to_the_skill(self):
        t = text("skills/state/references/step-rules.md")
        self.assertIn("skills/guardrails/SKILL.md", t)
        self.assertIn('"Guardrails" section', t)

    def test_the_state_skill_points_to_the_skill(self):
        self.assertIn("`guardrails` skill", text("skills/state/SKILL.md"))

    def test_new_projects_get_the_guardrails_section(self):
        t = text("templates/decisions/0000-template.md")
        self.assertIn("## Guardrails", t)
        self.assertLess(t.index("## Guardrails"), t.index("## Stale outputs"))


if __name__ == "__main__":
    unittest.main()
