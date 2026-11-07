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

    def test_agent_installs_after_announcing(self):
        for name in ("start", "doctor"):
            t = read(name)
            self.assertNotIn("Never install", t, name)
            self.assertIn("what it will install", t, name)
            self.assertIn("which Pavedline step needs it", t, name)
            self.assertIn("exact command", t, name)
            self.assertIn("permission prompt", t, name)
            self.assertIn("sudo", t, name)
            self.assertIn("WAITING.md", t, name)
        d = read("doctor")
        self.assertIn("not on its list", d)
        self.assertIn("paid service, account or spend", d)

    def test_no_install_pattern_is_preapproved(self):
        import pathlib
        for f in pathlib.Path(SKILLS).glob("*/SKILL.md"):
            for line in f.read_text().splitlines():
                if line.startswith("allowed-tools:"):
                    for bad in ("brew", "colima", "claude plugin"):
                        self.assertNotIn(bad, line, str(f))

    def test_old_install_phrases_are_gone(self):
        import pathlib
        root = pathlib.Path(SKILLS).parents[2]
        files = list(pathlib.Path(SKILLS).glob("*/SKILL.md"))
        files += [root / "README.md"] + list((root / "docs").rglob("*.md"))
        files += list((root / "plugins/pavedline/scripts/local-cluster").glob("*.sh"))
        for f in files:
            if "superpowers" in f.parts:
                continue
            t = f.read_text()
            for old in ("Relay each fix exactly", "without the user's go", "install only with the user's go"):
                self.assertNotIn(old, t, str(f))

    def test_start_privacy_first(self):
        t = read("start")
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


class StepOneContracts(unittest.TestCase):
    def test_teardown_requires_sources(self):
        t = read("competitor-teardown")
        self.assertIn("URL", t)
        self.assertIn("definite, inferred or unknown", t)

    def test_review_sites_rule(self):
        self.assertIn("manual export or official APIs", read("competitor-teardown"))

    def test_seo_strategy_output(self):
        t = read("competitor-teardown")
        self.assertIn("SEO-STRATEGY.md", t)
        self.assertIn("target query", t)

    def test_market_size_marks_assumptions(self):
        t = read("market-size")
        self.assertIn("assumption", t)
        self.assertIn("top-down", t)
        self.assertIn("bottom-up", t)


class StepTwoThreeContracts(unittest.TestCase):
    def test_spec_has_four_surfaces(self):
        t = read("spec").lower()
        for surface in ("website", "blog", "web app", "mobile app"):
            self.assertIn(surface, t)

    def test_spec_has_acceptance_tests(self):
        t = read("spec")
        for needle in ("acceptance tests", "non-goals", "site map", "URL plan"):
            self.assertIn(needle, t)

    def test_registry_never_values(self):
        t = read("project-registry")
        self.assertIn("never the value", t)
        for f in ("RUN.md", "SERVICES.md", "LINKS.md"):
            self.assertIn(f, t)

    def test_diagram_uses_canon(self):
        t = read("diagram")
        self.assertIn("-Tcanon", t)
        self.assertIn("-Tsvg", t)


def read_from(text_by_name, name):
    return text_by_name[name]


class FixRound1Contracts(unittest.TestCase):
    """Each check takes a text getter so it can be run against older text (RED proof)."""
    NAMES = ("competitor-teardown", "pricing-model", "market-size", "spec")
    get = staticmethod(read)

    def test_business_paths_everywhere(self):
        bare = re.compile(r"(?<!docs/business/)\b(BRIEF\.md|SEO-STRATEGY\.md)")
        for n in self.NAMES:
            self.assertIsNone(bare.search(self.get(n)), n)
        self.assertIn("docs/business/SEO-STRATEGY.md", self.get("competitor-teardown"))
        self.assertNotIn("(repo root)", self.get("competitor-teardown"))

    def test_teardown_waits_for_approval(self):
        t = self.get("competitor-teardown")
        self.assertIn("NEXT: waiting for the founder to approve docs/business/BRIEF.md", t)
        self.assertLess(t.index("Only after an explicit go"), t.index("`STEP: 2 — Grill`"))

    def test_step2_to_3_handoff_owned(self):
        self.assertIn("`STEP: 3 — Spec`", self.get("competitor-teardown"))
        sp = self.get("spec")
        self.assertIn("`STEP: 2 — Grill`", sp)
        self.assertIn("decisions are complete", sp)
        self.assertIn("STEP: 4 — System design", sp)

    def test_spec_updates_business_brief(self):
        self.assertIn("edit the pricing section of `docs/business/BRIEF.md`", self.get("spec"))

    def test_spec_fixed_surface_list_in_one_place(self):
        self.assertTrue(re.search(r"\*\*Website\*\*, \*\*Blog\*\*, \*\*Web app\*\*, \*\*Mobile app\*\*",
                                  self.get("spec")))

    def test_review_export_location(self):
        self.assertIn("docs/business/reviews/", self.get("competitor-teardown"))


if __name__ == "__main__":
    unittest.main()
