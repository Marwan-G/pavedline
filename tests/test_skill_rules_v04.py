"""Skill wording rules added in v0.4: the needles each rule must keep."""
import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "plugins/pavedline/skills"


def read(rel):
    return (SKILLS / rel).read_text(encoding="utf-8")


class SkillRulesV04(unittest.TestCase):
    def test_go_to_production_proceeds_after_fill_in_approval(self):
        t = read("go-to-production/SKILL.md")
        self.assertIn("proceed straight to filling the values and printing the bootstrap and plan commands", t)
        self.assertIn("with no extra wait", t)
        self.assertIn("From the 5th area on, also offer `default for the rest of this round`", t)
        self.assertIn("default for the rest of this round", read("state/references/step-rules.md"))

    def test_preferences_go_in_the_repo_not_only_memory(self):
        t = read("state/references/step-rules.md")
        self.assertIn("never only into the agent's auto-memory", t)
        self.assertIn("decision (ADR) or `STATE.md`", t)

    def test_content_ops_before_go_live_is_drafts_only(self):
        t = read("content-ops/SKILL.md")
        self.assertIn("before go-live the skill writes briefs and drafts only", t)
        self.assertIn("`draft (pre-launch)`", t)
        self.assertIn("never opens a publishing PR until `STATE.md` shows the product is live", t)


if __name__ == "__main__":
    unittest.main()
