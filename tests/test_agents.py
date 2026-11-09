import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gen_agent_models as gen  # noqa: E402
import lint_skills as lint  # noqa: E402

AGENTS = ROOT / "plugins" / "pavedline" / "agents"
MODELS = ROOT / "plugins" / "pavedline" / "config" / "models.yaml"
FIGMA = "mcp__plugin_figma_figma__"
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
NEW = ["architect", "designer", "design-verifier", "reviewer", "builder", "adversary", "deployer"]


def load(stem):
    text = (AGENTS / f"{stem}.md").read_text()
    front = lint.parse_frontmatter(text)
    return front, text.split("\n---\n", 1)[1]


def allowed(stem):
    return {t.strip() for t in load(stem)[0]["tools"].split(",")}


FIGMA_WRITES = {FIGMA + t for t in (
    "use_figma", "create_new_file", "create_session", "upload_assets", "generate_figma_design",
    "generate_diagram", "add_code_connect_map", "send_code_connect_mappings")}


class AgentTests(unittest.TestCase):
    def test_frontmatter_and_models(self):
        models = gen.parse_models(MODELS.read_text())
        for f in sorted(AGENTS.glob("*.md")):
            front, _ = load(f.stem)
            self.assertEqual(front["name"], f.stem)
            self.assertEqual(front["model"], models[f.stem])

    def test_new_agents_exist(self):
        for n in NEW:
            self.assertTrue((AGENTS / f"{n}.md").exists(), n)

    def test_read_only_agents_use_allowlist(self):
        banned = EDIT_TOOLS | {"Bash"}
        for n in ("design-verifier", "reviewer", "adversary"):
            self.assertFalse(banned & allowed(n), n)
            self.assertNotIn("disallowedTools", load(n)[0], n)

    def test_design_verifier_figma_read_only(self):
        reads = {FIGMA + t for t in ("get_metadata", "get_screenshot", "get_design_context",
                                     "get_variable_defs", "search_design_system",
                                     "get_figjam", "create_session", "get_code_connect_map")}
        figma = {t for t in allowed("design-verifier") if t.startswith("mcp__")}
        self.assertTrue(figma <= reads)
        self.assertEqual(allowed("reviewer"), {"Read", "Grep", "Glob"})

    def test_every_agent_has_an_allowlist(self):
        for f in sorted(AGENTS.glob("*.md")):
            front = load(f.stem)[0]
            self.assertIn("tools", front, f.stem)
            self.assertNotIn("disallowedTools", front, f.stem)

    def test_only_designer_writes_figma(self):
        for f in sorted(AGENTS.glob("*.md")):
            if f.stem not in ("designer", "design-verifier"):
                self.assertFalse({t for t in allowed(f.stem) if t.startswith(FIGMA)}, f.stem)
        d = allowed("designer")
        for t in ("use_figma", "generate_figma_design", "create_new_file", "upload_assets"):
            self.assertIn(FIGMA + t, d)
        self.assertTrue({"Write", "Edit"} <= d)
        self.assertFalse({"Bash", "Agent", "NotebookEdit"} & d)

    def test_architect_allowlist(self):
        self.assertEqual(allowed("architect"),
                         {"Read", "Grep", "Glob", "Write", "Edit", "WebFetch", "WebSearch"})

    def test_researcher_cannot_write(self):
        self.assertFalse((EDIT_TOOLS | {"Bash"}) & allowed("researcher"))

    def test_researcher_renders_with_plugin_playwright_read_tools(self):
        tools = allowed("researcher")
        self.assertIn("mcp__plugin_pavedline_playwright__browser_navigate", tools)
        writes = {"browser_click", "browser_type", "browser_fill_form", "browser_file_upload", "browser_evaluate", "browser_run_code_unsafe"}
        self.assertFalse({"mcp__plugin_pavedline_playwright__" + w for w in writes} & tools)

    def test_verdict_texts(self):
        body = load("reviewer")[1]
        for s in ("VERDICT: APPROVE", "VERDICT: REJECT", "reads the diff, never the summary"):
            self.assertIn(s, body)
        body = load("design-verifier")[1]
        for s in ("DESIGN VERDICT: APPROVE", "DESIGN VERDICT: REJECT", "never approves a visual"):
            self.assertIn(s, body)

    def test_report_first_line_records_model(self):
        for n in NEW:
            self.assertRegex(load(n)[1].lower(), r"first line.*model that ran")

    def test_code_agents(self):
        self.assertEqual(allowed("adversary"), {"Read", "Grep", "Glob"})
        self.assertEqual(allowed("builder"), {"Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebFetch", "WebSearch"})
        self.assertEqual(allowed("deployer"), {"Read", "Write", "Edit", "Bash", "Grep", "Glob"})
        needles = {
            "builder": ["own worktree", "Red first.", "approval quoted in the prompt", "handoff/<branch>.md",
                        "never dispatch reviewers and never merge"],
            "adversary": ["ADVERSARIAL: APPROVE", "ADVERSARIAL: REJECT", "concrete input", "stop rule",
                          "ADVERSARIAL: REJECT — incomplete:"],
            "deployer": ["kind-pavedline-", "never the Synced label",
                         "never runs kubectl apply or helm upgrade against a cloud cluster",
                         "never reads cloud credentials", "git commit-tree"],
            "reviewer": ["scanner output", "code diff", "never check out"],
        }
        for n, ss in needles.items():
            body = load(n)[1]
            for s in ss:
                self.assertIn(s, body, f"{n}: {s}")
        for n in ("builder", "adversary", "deployer"):
            self.assertLessEqual(len(load(n)[1].splitlines()), 40, n)

    def test_growth_agent(self):
        self.assertEqual(allowed("growth"), {"Read", "Write", "Edit", "Grep", "Glob", "WebFetch", "WebSearch", "Skill"})
        body = load("growth")[1]
        for s in ("never pushes", "never merges", "never deploys", "founder's approval quoted",
                  "never creates an account", "GROW DUE", "Search Console"):
            self.assertIn(s, body)
        self.assertRegex(body.lower(), r"first line.*model that ran")
        self.assertNotIn("haiku", load("growth")[0]["model"])
        self.assertLessEqual(len(body.splitlines()), 40)

    def test_incomplete_check_is_a_reject(self):
        for n in ("reviewer", "design-verifier"):
            body = load(n)[1]
            self.assertIn("every required check ran", body, n)
            self.assertIn("REJECT — incomplete:", body, n)


if __name__ == "__main__":
    unittest.main()
