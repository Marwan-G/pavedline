import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "plugins" / "pavedline" / "skills"
sys.path.insert(0, str(ROOT / "scripts"))

import lint_skills as lint  # noqa: E402

PRIVACY = "Pavedline collects nothing. Every answer stays in your own repository."
COMPLIANCE = ("Should we design with compliance in mind (privacy laws such as GDPR, "
              "health or payment rules)? Recommended: yes.")
CLOUD_QUESTION = re.compile(r"(which|what|pick|choose)[^.\n]*\bcloud\b[^.\n]*\?|cloud provider\?", re.I)


def read(name):
    return (SKILLS / name / "SKILL.md").read_text()


class StepZeroContracts(unittest.TestCase):
    def test_start_asks_product_first(self):
        t = read("start")
        self.assertIn("What are you building", t)
        self.assertIn("multi-tenant", t.lower())
        self.assertLess(t.index("What are you building"), t.lower().index("multi-tenant"))

    def test_start_frontmatter(self):
        t = read("start")
        self.assertIn("disable-model-invocation: true", t)
        self.assertIn("Bash(python3 *)", t)

    def test_compliance_exact_wording(self):
        self.assertIn(COMPLIANCE, read("compliance"))

    def test_compliance_no_path_recorded(self):
        t = read("compliance")
        self.assertIn("compliance not in scope", t)
        self.assertIn("launch checklist", t)

    def test_privacy_line_present(self):
        self.assertIn(PRIVACY, read("start"))

    def test_cloud_not_asked_at_step0(self):
        for name in ("start", "architecture-intake"):
            t = read(name)
            self.assertIn("chosen at step 12", t, name)
            self.assertIsNone(CLOUD_QUESTION.search(t), name)

    def test_state_skill_covers_records(self):
        t = read("state")
        for needle in ("60 lines", "WAITING.md", "handoff/", "date", "remote"):
            self.assertIn(needle, t)

    def test_start_question_order(self):
        t = read("start")
        marks = ["**What are you building?**", "**Multi-tenant?**", "**Compliance.**",
                 "**Solo or team?**", "**Surfaces.**", "**Database:", "**Local runtime.**"]
        idx = [t.index(m) for m in marks]
        self.assertEqual(idx, sorted(idx))

    def test_intake_question_order(self):
        t = read("architecture-intake")
        idx = [t.index("## Question %d" % n) for n in (2, 4, 5, 6, 7)]
        self.assertEqual(idx, sorted(idx))

    def test_compliance_order(self):
        t = read("compliance")
        idx = [t.index(m) for m in (COMPLIANCE, "## If yes", "## If no")]
        self.assertEqual(idx, sorted(idx))
        self.assertIn("stay in", t)
        self.assertIn("repository", t)

    def test_start_never_installs_and_privacy_first(self):
        t = read("start")
        self.assertIn("Never install", t)
        self.assertLess(t.index(PRIVACY), t.index("**What are you building?**"))
        self.assertIn("go?", t)

    def test_start_one_adr_per_question(self):
        t = read("start")
        self.assertIn("0001–0007", t)
        self.assertIn("git rev-parse --is-inside-work-tree", t)
        self.assertIn("Bash(git commit *)", t)

    def test_cloud_regex_catches_questions(self):
        for s in ("Which cloud do you use?", "Pick a cloud provider?", "cloud provider?"):
            self.assertTrue(CLOUD_QUESTION.search(s), s)

    def test_linter_passes(self):
        self.assertEqual(lint.check_skills(SKILLS), [])


if __name__ == "__main__":
    unittest.main()
