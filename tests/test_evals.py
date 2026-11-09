import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVALS = ROOT / "plugins" / "pavedline" / "evals"

# Allowed keys, from https://code.claude.com/docs/en/plugin-evals.md (read 2026-11-09).
PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome", "model",
               "max_turns", "timeout_seconds", "allowed_tools", "append_system_prompt", "env"}
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
COMMON = {"type", "weight", "arm"}
GRADER_KEYS = {
    "regex": COMMON | {"pattern", "flags", "match", "target"},
    "tool_used": COMMON | {"tool", "input_match", "min", "max"},
    "tool_order": COMMON | {"before", "after"},
    "file_exists": COMMON | {"path", "exists"},
    "llm": COMMON | {"criteria", "focus"},
    "baseline": COMMON | {"baseline_file", "criteria"},
}
CASE_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome",
            "context", "execution", "graders"}
CONTEXT_KEYS = {"scaffold_script", "history_file", "add_dirs"}


def frontmatter(path):
    lines = path.read_text().splitlines()
    assert lines and lines[0].strip() == "---", "%s: no frontmatter" % path
    keys, body = {}, None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1:])
            break
        if line and not line.startswith((" ", "\t", "-", "#")) and ":" in line:
            k, _, v = line.partition(":")
            keys[k.strip()] = v.strip()
    assert body is not None, "%s: unterminated frontmatter" % path
    return keys, body


def top_keys(path):
    out = []
    for line in path.read_text().splitlines():
        if line and not line.startswith((" ", "\t", "-", "#")) and ":" in line:
            out.append(line.partition(":")[0].strip())
    return out


class EvalSuites(unittest.TestCase):
    def cases(self):
        return sorted(p for p in EVALS.iterdir() if p.is_dir() and p.name != "results")

    def test_cases_exist(self):
        self.assertEqual({p.name for p in self.cases()}, {"start", "plan-graph", "go-to-production"})

    def test_prompts_use_only_documented_keys(self):
        for c in self.cases():
            keys, body = frontmatter(c / "prompt.md")
            self.assertFalse(set(keys) - PROMPT_KEYS, "%s: %s" % (c.name, set(keys) - PROMPT_KEYS))
            self.assertTrue(body.strip(), c.name)

    def test_graders_use_only_documented_keys(self):
        for c in self.cases():
            graders = sorted((c / "graders").glob("*.md"))
            self.assertTrue(graders, c.name)
            for g in graders:
                keys, body = frontmatter(g)
                self.assertIn(keys.get("type"), GRADER_TYPES, g)
                extra = set(keys) - GRADER_KEYS[keys["type"]]
                self.assertFalse(extra, "%s: %s" % (g, extra))
                if keys["type"] == "regex":
                    self.assertIn("pattern", keys, g)
                    self.assertNotIn("(?i)", keys["pattern"], g)  # inline flags are unsupported; use `flags: i`

    def test_case_yaml_keys(self):
        for c in self.cases():
            y = c / "case.yaml"
            if y.exists():
                self.assertFalse(set(top_keys(y)) - CASE_KEYS, y)
                self.assertIn('schema_version: "1.1"', y.read_text())

    def test_scaffold_scripts_exist(self):
        for c in self.cases():
            y = c / "case.yaml"
            if not y.exists():
                continue
            for line in y.read_text().splitlines():
                if "scaffold_script" in line:
                    rel = line.partition(":")[2].strip().strip("\"'")
                    self.assertTrue((c / rel).is_file(), (c.name, rel))

    def test_validator_rejects_a_typo(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d, "prompt.md")
            p.write_text("---\nmax_turn: 5\n---\nhi\n")
            keys, _ = frontmatter(p)
            self.assertTrue(set(keys) - PROMPT_KEYS)

    def test_results_are_ignored_by_git(self):
        # The pattern must match the plugin's evals/results/, not only a root-level evals/results/ (it did, until
        # 2026-11-09: a slash inside a .gitignore pattern anchors it to the .gitignore's folder).
        import subprocess
        r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index",
                            "plugins/pavedline/evals/results/2026-01-01/report.html"])
        self.assertEqual(r.returncode, 0)


class EvalRunner(unittest.TestCase):
    """An eval run loads only the plugin under test, so the runner evaluates a copy without `dependencies`."""

    def test_strip_removes_dependencies_from_a_copy(self):
        import json, subprocess, sys, tempfile
        with tempfile.TemporaryDirectory() as d:
            m = pathlib.Path(d, "plugin.json")
            m.write_text(json.dumps({"name": "pavedline", "dependencies": ["a@b"]}))
            subprocess.run([sys.executable, str(ROOT / "scripts/strip_plugin_dependencies.py"), str(m)], check=True)
            self.assertEqual(json.loads(m.read_text()), {"name": "pavedline"})

    def test_strip_refuses_the_shipped_manifest(self):
        import subprocess, sys
        shipped = ROOT / "plugins/pavedline/.claude-plugin/plugin.json"
        before = shipped.read_text()
        r = subprocess.run([sys.executable, str(ROOT / "scripts/strip_plugin_dependencies.py"), str(shipped)],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(shipped.read_text(), before)

    def test_runner_evaluates_a_copy_with_a_cost_cap_and_one_arm(self):
        t = (ROOT / "scripts/run_evals.sh").read_text()
        for needle in ("cp -R", "strip_plugin_dependencies.py", "MAX_COST=5", "--max-cost-usd", "--ablation none",
                       "--runs 1", "--no-publish"):
            self.assertIn(needle, t)

    def test_start_case_grades_only_what_one_prompt_can_show(self):
        graders = {g.name for g in (EVALS / "start/graders").glob("*.md")}
        self.assertEqual(graders, {"runs-doctor.md", "no-copy-before-answers.md", "stops-and-says-why.md"})
        self.assertIn("Bash", (EVALS / "start/prompt.md").read_text())

    def test_never_graders_set_min_zero(self):
        # A `max: 0` grader without `min: 0` demands at least one call (observed 2026-11-09: "expected 1..0").
        for g in EVALS.glob("*/graders/*.md"):
            t = g.read_text()
            if "max: 0" in t:
                self.assertIn("min: 0", t, g)


class LintAcceptsDisallowedTools(unittest.TestCase):
    def test_lint_accepts_the_key(self):
        import sys, tempfile
        sys.path.insert(0, str(ROOT / "scripts"))
        import lint_skills
        with tempfile.TemporaryDirectory() as d:
            s = pathlib.Path(d, "demo")
            s.mkdir()
            (s / "SKILL.md").write_text("---\nname: demo\ndescription: x\ndisallowed-tools: Write, Edit, NotebookEdit\n---\n# demo\n")
            self.assertEqual(lint_skills.check_skills(d), [])


if __name__ == "__main__":
    unittest.main()
