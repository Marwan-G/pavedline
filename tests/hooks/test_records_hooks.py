import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PLUGIN = ROOT / "plugins" / "pavedline"
HOOKS = PLUGIN / "scripts" / "hooks"


def run(script, event=None, raw=None, env=None):
    stdin = raw if raw is not None else json.dumps(event)
    e = dict(os.environ)
    e.pop("CLAUDE_PROJECT_DIR", None)
    e.update(env or {})
    return subprocess.run([sys.executable, str(HOOKS / script)], input=stdin, capture_output=True,
                          text=True, env=e)


def git(d, *args):
    subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   check=True, capture_output=True)


STATE = ("STEP: 9 — Build\nWAVE: 2\nLAST: did a thing\nNEXT: slice s3\n"
         "LEFT BEHIND: red test x\nSTALE: none\nOWNER: me\n")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def project(self, state=STATE, commit=True):
        git(self.dir, "init", "-q")
        (self.dir / "STATE.md").write_text(state)
        (self.dir / "WAITING.md").write_text("# Waiting\n- F1 · login · site · unblocks a\n- F2 · fund · x · y\n")
        (self.dir / "src.py").write_text("x = 1\n")
        git(self.dir, "add", "-A")
        if commit:
            git(self.dir, "commit", "-q", "-m", "init")

    def ev(self, name, **kw):
        d = {"hook_event_name": name, "cwd": str(self.dir)}
        d.update(kw)
        return d


class StopTests(Base):
    def test_dirty_state_gives_feedback(self):
        self.project()
        (self.dir / "STATE.md").write_text(STATE + "x\n")
        r = run("stop_records.py", self.ev("Stop", stop_hook_active=False))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        h = out["hookSpecificOutput"]
        self.assertEqual(h["hookEventName"], "Stop")
        self.assertIn("Records not committed: STATE.md.", h["additionalContext"])
        self.assertNotIn("decision", out)

    def test_untracked_decision_listed(self):
        self.project()
        (self.dir / "decisions").mkdir()
        (self.dir / "decisions" / "0001-a.md").write_text("x")
        r = run("stop_records.py", self.ev("Stop"))
        self.assertIn("decisions/", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_non_record_change_silent(self):
        self.project()
        (self.dir / "src.py").write_text("x = 2\n")
        r = run("stop_records.py", self.ev("Stop"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_clean_silent(self):
        self.project()
        r = run("stop_records.py", self.ev("Stop"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_stop_hook_active_silent(self):
        self.project()
        (self.dir / "STATE.md").write_text(STATE + "x\n")
        r = run("stop_records.py", self.ev("Stop", stop_hook_active=True))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_not_a_project_silent(self):
        git(self.dir, "init", "-q")
        r = run("stop_records.py", self.ev("Stop"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_malformed_stdin(self):
        for raw in ("", "not json", "[1]"):
            r = run("stop_records.py", raw=raw)
            self.assertEqual((r.returncode, r.stdout), (0, ""), raw)


class PreCompactTests(Base):
    def test_output_has_state_lines_and_waiting(self):
        self.project()
        (self.dir / "STATE.md").write_text(STATE + "x\n")
        r = run("precompact_records.py", self.ev("PreCompact", trigger="auto"))
        self.assertEqual(r.returncode, 0, r.stderr)
        for s in ("STEP: 9 — Build", "WAVE: 2", "NEXT: slice s3", "LEFT BEHIND: red test x", "STALE: none",
                  "2 open", "F1", "F2", "STATE.md",
                  "After compaction, re-read STATE.md before acting."):
            self.assertIn(s, r.stdout)
        self.assertNotIn("LAST: did a thing", r.stdout)

    def test_clean_repo_has_no_uncommitted_files(self):
        self.project()
        r = run("precompact_records.py", self.ev("PreCompact"))
        self.assertIn("After compaction, re-read STATE.md before acting.", r.stdout)
        self.assertIn("none", r.stdout.lower())

    def test_huge_state_capped(self):
        self.project(state=STATE + ("NEXT: " + "y" * 500 + "\n") * 200 + ("LEFT BEHIND: " + "z" * 500 + "\n") * 200)
        r = run("precompact_records.py", self.ev("PreCompact"))
        self.assertEqual(r.returncode, 0)
        self.assertLess(len(r.stdout), 10000)
        self.assertIn("After compaction, re-read STATE.md before acting.", r.stdout)

    def test_not_a_project_silent(self):
        r = run("precompact_records.py", self.ev("PreCompact"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_project_dir_env(self):
        self.project()
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        r = run("precompact_records.py", {"cwd": other.name}, env={"CLAUDE_PROJECT_DIR": str(self.dir)})
        self.assertIn("STEP: 9", r.stdout)

    def test_malformed_stdin(self):
        for raw in ("", "not json", "[1]"):
            r = run("precompact_records.py", raw=raw)
            self.assertEqual(r.returncode, 0, raw)


class RegistrationTests(unittest.TestCase):
    def test_registered(self):
        h = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
        for ev, script in (("PreCompact", "precompact_records.py"), ("Stop", "stop_records.py")):
            cmds = [x for g in h[ev] for x in g["hooks"]]
            self.assertEqual(len(cmds), 1)
            self.assertIn(script, cmds[0]["command"])
            self.assertEqual(cmds[0]["timeout"], 10)


class PreapprovalTests(unittest.TestCase):
    EXPECT = {
        "system-architecture": "apply_stack.py",
        "plan-graph": "plan_graph.py",
        "doctor": "doctor.py",
        "start": "start_project.py",
        "lessons": "plan_graph.py",
    }

    def rules(self, skill):
        text = (PLUGIN / "skills" / skill / "SKILL.md").read_text()
        m = re.search(r"^allowed-tools:\s*(.*)$", text, re.MULTILINE)
        self.assertTrue(m, skill)
        return re.findall(r"Bash\([^)]*\)|[A-Za-z]+", m.group(1))

    def test_exact_script_rules(self):
        for skill, script in self.EXPECT.items():
            rules = self.rules(skill)
            want = "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/%s *)" % script
            self.assertIn(want, rules, skill)
            for r in rules:
                self.assertNotIn(r, ("Bash(*)", "Bash", "Bash(python3 *)", "Bash(python3*)"), skill)
                if r.startswith("Bash(python3"):
                    self.assertTrue(r.startswith("Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/"), (skill, r))

    def test_each_script_rule_matches_one_script_per_skill(self):
        import re
        want = {"start": {"start_project.py", "doctor.py"}}
        for skill, script in self.EXPECT.items():
            py = [r for r in self.rules(skill) if r.startswith("Bash(python3")]
            names = set()
            for r in py:
                m = re.fullmatch(r"Bash\(python3 \$\{CLAUDE_PLUGIN_ROOT\}/scripts/([a-z_]+\.py)( \*)?\)", r)
                self.assertIsNotNone(m, f"{skill}: unexpected rule {r}")
                names.add(m.group(1))
            expected = want.get(skill, {script} if isinstance(script, str) else set(script))
            self.assertEqual(names, expected, skill)
            self.assertEqual(len(py), 2 * len(expected), f"{skill}: bare and with-arguments form per script")

    def test_skill_bodies_run_the_scripts_unquoted(self):
        # A quoted path ("${CLAUDE_PLUGIN_ROOT}/...") would not match the pre-approval rule.
        for skill in self.EXPECT:
            body = (PLUGIN / "skills" / skill / "SKILL.md").read_text().split("---", 2)[2]
            self.assertNotIn('python3 "${CLAUDE_PLUGIN_ROOT}', body, skill)


class BuilderTests(unittest.TestCase):
    def test_preloads_quality_gates(self):
        text = (PLUGIN / "agents" / "builder.md").read_text()
        fm = text.split("---")[1]
        self.assertRegex(fm, r"(?m)^skills:\s*\n\s*-\s*quality-gates\s*$")
        self.assertLessEqual(len(text.split("---", 2)[2].strip().splitlines()), 40)
        qg = (PLUGIN / "skills" / "quality-gates" / "SKILL.md").read_text().split("---")[1]
        self.assertNotIn("disable-model-invocation", qg)


if __name__ == "__main__":
    unittest.main()
