import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "plugins" / "pavedline" / "skills"
RULES = SKILLS / "state" / "references" / "step-rules.md"
POINTER = "Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`."


def read(name):
    d = SKILLS / name
    parts = [(d / "SKILL.md").read_text(), RULES.read_text()]
    for f in sorted((d / "references").glob("*.md")) if (d / "references").is_dir() else []:
        parts.append(f.read_text())
    return "\n".join(parts)


class PlanGraph(unittest.TestCase):
    def test_needles(self):
        t = read("plan-graph")
        for s in ("superpowers:writing-plans", "thin vertical slice", "STEP: 9 — Build", "plan_graph.py check",
                  "plan_graph.py dot", "accepted intents", "docs/plans/", "approve the wave",
                  "Continue when `STATE.md` says `STEP: 8 — Plan`", POINTER,
                  "### Slice <wave>.<n>: <title>", "Depends on:", "3b", "never a layer alone", "Deferred: AT-"):
            self.assertIn(s, t)

    def test_decisions_read_in_full(self):
        t = (SKILLS / "plan-graph/SKILL.md").read_text()
        self.assertIn("Read in full", t)
        for s in ("surfaces decision (0005)", "tenancy (0002)", "compliance (0003)", "backend and auth",
                  "data and API decisions", "deployment and threat decisions", "design decision",
                  "every decision marked accepted since", "decisions index"):
            self.assertIn(s, t)

    def test_wave_approval_is_its_own_question(self):
        t = (SKILLS / "plan-graph/SKILL.md").read_text()
        for s in ('Approve wave <n> as planned?', "Never infer approval", "explicit yes"):
            self.assertIn(s, t)

    def test_gate_never_answered_by_default_for_round(self):
        t = RULES.read_text()
        self.assertIn("never answered by `default for the rest of this round`", t)

    def test_close_and_go(self):
        t = (SKILLS / "plan-graph/SKILL.md").read_text()
        tail = t.split("## 6. Close step 8")[1]
        self.assertIn("STEP: 9 — Build", tail)
        self.assertIn("NEXT: step 9 — build slice", tail)
        self.assertIn("go?", tail)

    def test_no_product_words(self):
        t = read("plan-graph").lower() + (ROOT / "plugins/pavedline/skills/spec/SKILL.md").read_text().lower()
        for w in ("cli" + "nic", "pati" + "ent", "appoint" + "ment", "book" + "ing"):
            self.assertNotIn(w, t)

    def test_size(self):
        self.assertLessEqual(len((SKILLS / "plan-graph/SKILL.md").read_text().splitlines()), 150)

    def test_rules_intro_covers_all_steps(self):
        intro = RULES.read_text().split("## Read first")[0]
        self.assertNotIn("steps 4 to 7", intro)
        self.assertIn("plan-graph", intro)
        self.assertIn("lessons", intro)

    def test_step_page(self):
        self.assertIn("08-plan.md", (ROOT / "docs/steps/07-figma.md").read_text())
        t = (ROOT / "docs/steps/08-plan.md").read_text()
        self.assertIn("STEP: 9 — Build", t)
        self.assertRegex(t.strip().splitlines()[-1], r"^Next:")

    def test_slice_commit_rule(self):
        t = read("plan-graph")
        self.assertIn("Slice <id>", t)
        self.assertIn("subject", t)


class ChainAndIntent(unittest.TestCase):
    def test_step_chain_7_to_8(self):
        close = (SKILLS / "design-system-contract/SKILL.md").read_text().split("## 6. Close step 7")[1]
        m = re.search(r"STEP: (\d+ — \S+)", close)
        self.assertIn("STEP: " + m.group(1), (SKILLS / "plan-graph/SKILL.md").read_text())

    def test_spec_change_mode(self):
        t = (SKILLS / "spec/SKILL.md").read_text()
        self.assertIn("## Change mode", t)
        sect = t.split("## Change mode")[1]
        for s in ("Status: accepted", "docs/spec/SPEC.md", "supersedes", "STATE.md ▶ STALE", "AT-NNN",
                  "never renumbers", "Intent: docs/intent/", "specced in decision", "plan-graph"):
            self.assertIn(s, sect)
        self.assertIn("## 6. Close step 3", t)

    def test_intake_writes_structured_surfaces_line(self):
        t = (SKILLS / "architecture-intake/SKILL.md").read_text().split("## Question 5: surfaces")[1].split("## Question 6")[0]
        self.assertIn("Surfaces: web, api, site, mobile", t)

    def test_intent_template_headings(self):
        t = (ROOT / "plugins/pavedline/templates/docs/intent/0000-template.md").read_text()
        self.assertIn("Status: proposed | accepted | rejected", t)
        for h in ("Problem", "Proposed outcome", "Affected users and systems", "Constraints", "Open questions"):
            self.assertIn("## " + h, t)


class QualityGates(unittest.TestCase):
    def test_needles(self):
        t = read("quality-gates")
        for s in ("TDD", "own worktree", "scanner output", "VERDICT: APPROVE", "security-review", "pavedline:adversary",
                  "one narrow re-check", "the check bites", "data", "rebase", "STEP: 10", "handoff/<branch>.md",
                  "ci:db", "accepted — <reason>", "Light path", POINTER,
                  "Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓",
                  "Continue when `STATE.md` says `STEP: 9 — Build`"):
            self.assertIn(s, t)
        for s in ("auth", "tenancy", "IAM", "infra", "CI", "secrets", "input parsing", "payments", "migrations"):
            self.assertIn(s, t.split("**3b, the adversarial review")[1].split("**Fix rounds")[0])

    def test_worktree_place_and_docker_preflight(self):
        t = read("quality-gates")
        for s in (".worktrees/<slice-id>", "docker info", "WAITING"):
            self.assertIn(s, t)
        b = (ROOT / "plugins/pavedline/agents/builder.md").read_text()
        for s in (".worktrees/<slice-id>", "docker info"):
            self.assertIn(s, b)
        g = (ROOT / "plugins/pavedline/stacks/nextjs-fastapi/files/.gitignore").read_text()
        self.assertIn(".worktrees/", g.splitlines())
        d = (ROOT / "ARCHITECTURE.dot").read_text()
        self.assertIn("8 required checks + CodeQL; starter runs on every PR", d)

    def test_five_gates_in_order(self):
        t = (SKILLS / "quality-gates/SKILL.md").read_text()
        heads = [t.index(h) for h in ("Gate 1", "Gate 2", "Gate 3", "Gate 4", "Gate 5")]
        self.assertEqual(heads, sorted(heads))

    def test_full_review_only_after_high_fix(self):
        t = read("quality-gates")
        self.assertIn("HIGH", t)
        self.assertIn("full new review", t)

    def test_size_and_lint(self):
        self.assertLessEqual(len((SKILLS / "quality-gates/SKILL.md").read_text().splitlines()), 200)

    def test_step_chain_8_9_10(self):
        qg = (SKILLS / "quality-gates/SKILL.md").read_text()
        plan_close = (SKILLS / "plan-graph/SKILL.md").read_text().split("## 6. Close step 8")[1]
        m = re.search(r"STEP: (\d+ — \S+)", plan_close)
        self.assertIn("STEP: " + m.group(1), qg)
        close = qg.split("## 7. Close")[1]
        m = re.search(r"STEP: (\d+)", close)
        self.assertIn("`STATE.md` says `STEP: %s`" % m.group(1), (SKILLS / "deploy/SKILL.md").read_text())

    def test_gates_line_accepted_by_pr_checks(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import pr_checks
        self.assertTrue(pr_checks.has_gates_line(
            "Gates: TDD ✓ · review ✓ (3 found, 3 fixed) · security ✓ · adversarial n/a · verification ✓"))

    def test_step_page(self):
        t = (ROOT / "docs/steps/09-build.md").read_text()
        self.assertIn("STEP: 10", t)
        self.assertRegex(t.strip().splitlines()[-1], r"^Next:")


class Lessons(unittest.TestCase):
    def test_needles(self):
        t = read("lessons")
        for s in ("docs/retros/", "retro", "mattpocock-skills", "rules-index.md", "docs/intent/", "Source: retro",
                  "feature-complete", "STEP: 8 — Plan", "docs/archive/", "STATE.md", "60 lines", "150 lines",
                  "plan_graph.py", "docs/reviews/", "dropped", "Never a second copy",
                  "Continue when `STATE.md` says `STEP: 11 — Learn`", POINTER, "/mattpocock-skills:retro",
                  "retro skill was not used"):
            self.assertIn(s, t)
        self.assertNotIn("the Skill tool", t)

    def test_close(self):
        t = (SKILLS / "lessons/SKILL.md").read_text()
        tail = t.split("## 6. Close step 11")[1]
        self.assertIn("STEP: 8 — Plan", tail)
        self.assertIn("NEXT: step 8 — plan wave", tail)
        self.assertIn("NEXT: the integration wave (ships in a later release)", tail)
        self.assertIn("go?", tail)

    def test_size(self):
        self.assertLessEqual(len((SKILLS / "lessons/SKILL.md").read_text().splitlines()), 150)

    def test_step_chain_10_to_11(self):
        close = (SKILLS / "deploy/SKILL.md").read_text().split("## 7. Close step 10")[1]
        m = re.search(r"STEP: (\d+ — \S+)", close)
        self.assertEqual(m.group(1), "11 — Learn")
        self.assertIn("STEP: " + m.group(1), (SKILLS / "lessons/SKILL.md").read_text())

    def test_step_chain_11_to_8(self):
        close = (SKILLS / "lessons/SKILL.md").read_text().split("## 6. Close step 11")[1]
        m = re.search(r"STEP: (\d+ — \S+)", close)
        self.assertIn("Continue when `STATE.md` says `STEP: %s`" % m.group(1), (SKILLS / "plan-graph/SKILL.md").read_text())

    def test_templates(self):
        d = ROOT / "plugins/pavedline/templates/docs/retros"
        t = (d / "0000-template.md").read_text()
        for h in ("What shipped", "What went well", "What hurt", "Gate findings by class", "Lessons"):
            self.assertIn("## " + h, t)
        self.assertIn("rule in", t)
        self.assertIn("intent", t)
        self.assertIn("dropped", t)
        self.assertTrue((d / "README.md").is_file())

    def test_step_page(self):
        self.assertIn("11-learn.md", (ROOT / "docs/steps/10-deploy.md").read_text())
        t = (ROOT / "docs/steps/11-learn.md").read_text()
        self.assertIn("08-plan.md", t)
        self.assertRegex(t.strip().splitlines()[-1], r"^Next:")


if __name__ == "__main__":
    unittest.main()


class BuilderAnswersInRecords(unittest.TestCase):
    def test_answers_to_open_points_go_into_the_handoff(self):
        text = (SKILLS / "quality-gates" / "SKILL.md").read_text()
        self.assertIn("write every answer into `handoff/<branch>.md`", text)
        self.assertIn("records, not chat", text)
