import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOKS = ROOT / "plugins" / "pavedline" / "scripts" / "hooks"


def run(script, event=None, raw=None):
    stdin = raw if raw is not None else json.dumps(event)
    return subprocess.run([sys.executable, str(HOOKS / script)], input=stdin,
                          capture_output=True, text=True)


def lines(n):
    return "\n".join("line %d" % i for i in range(n)) + "\n"


class StateGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def ev(self, tool, **ti):
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(self.dir), "tool_input": ti}

    def test_blocks_write_over_60(self):
        r = run("guard_state_size.py", self.ev("Write", file_path=str(self.dir / "STATE.md"), content=lines(61)))
        self.assertEqual(r.returncode, 2)
        self.assertIn("STATE.md would be 61 lines (cap 60)", r.stderr)

    def test_allows_write_at_60(self):
        r = run("guard_state_size.py", self.ev("Write", file_path=str(self.dir / "STATE.md"), content=lines(60)))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_edit_growth_blocked(self):
        (self.dir / "STATE.md").write_text(lines(59))
        r = run("guard_state_size.py", self.ev("Edit", file_path="STATE.md", old_string="line 0",
                                               new_string="a\nb\nc\nd"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("62 lines", r.stderr)

    def test_edit_replace_all(self):
        (self.dir / "STATE.md").write_text("x\n" * 31)
        r = run("guard_state_size.py", self.ev("Edit", file_path="STATE.md", old_string="x",
                                               new_string="x\ny", replace_all=True))
        self.assertEqual(r.returncode, 2)

    def test_edit_not_found_allows(self):
        (self.dir / "STATE.md").write_text(lines(59))
        r = run("guard_state_size.py", self.ev("Edit", file_path="STATE.md", old_string="zzz", new_string="a\n" * 9))
        self.assertEqual(r.returncode, 0)

    def test_multiedit(self):
        (self.dir / "STATE.md").write_text(lines(58))
        edits = [{"old_string": "line 0", "new_string": "a\nb\ne"}, {"old_string": "line 1", "new_string": "c\nd"}]
        r = run("guard_state_size.py", self.ev("MultiEdit", file_path="STATE.md", edits=edits))
        self.assertEqual(r.returncode, 2)

    def test_ignores_other_files(self):
        r = run("guard_state_size.py", self.ev("Write", file_path=str(self.dir / "NOTES.md"), content=lines(200)))
        self.assertEqual(r.returncode, 0)
        r = run("guard_state_size.py", self.ev("Write", file_path=str(self.dir / "OLDSTATE.md"), content=lines(200)))
        self.assertEqual(r.returncode, 0)

    def test_bad_input_fails_open(self):
        for raw in ("", "not json"):
            r = run("guard_state_size.py", raw=raw)
            self.assertEqual(r.returncode, 0)


class ClaudeMdWarnTests(unittest.TestCase):
    def test_claude_md_warning(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "CLAUDE.md"
            p.write_text(lines(151))
            ev = {"hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": d,
                  "tool_input": {"file_path": "CLAUDE.md"}}
            r = run("warn_claude_md.py", ev)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "PostToolUse")
            self.assertIn("151 lines", out["additionalContext"])
            p.write_text(lines(150))
            r = run("warn_claude_md.py", ev)
            self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_other_file_and_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "README.md").write_text(lines(500))
            ev = {"cwd": d, "tool_input": {"file_path": "README.md"}}
            self.assertEqual(run("warn_claude_md.py", ev).stdout, "")
        self.assertEqual(run("warn_claude_md.py", raw="").returncode, 0)


class SessionStartTests(unittest.TestCase):
    def test_session_start_prints_state(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "PRODUCT.md").write_text("# Product\n\nA ledger for bakers.\nSecond line.\n\nOther para.\n")
            (p / "STATE.md").write_text("Phase: build\nNext: ship\n")
            (p / "WAITING.md").write_text("# Waiting\n- F1 · sign up\n- done thing\n- F2 · pay\n")
            r = run("session_start.py", {"hook_event_name": "SessionStart", "cwd": d})
            self.assertEqual(r.returncode, 0)
            self.assertIn("Pavedline project state", r.stdout)
            self.assertIn("A ledger for bakers.", r.stdout)
            self.assertNotIn("Other para", r.stdout)
            self.assertIn("Phase: build", r.stdout)
            self.assertIn("WAITING", r.stdout)
            self.assertIn("- F1 · sign up", r.stdout)
            self.assertIn("- F2 · pay", r.stdout)
            self.assertNotIn("done thing", r.stdout)

    def test_session_start_without_project(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("session_start.py", {"cwd": d})
            self.assertEqual(r.returncode, 0)
            self.assertIn("/pavedline:start", r.stdout)

    def test_truncates_and_empty_markers(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "STATE.md").write_text("x" * 5000)
            r = run("session_start.py", {"cwd": d})
            self.assertIn("… (truncated)", r.stdout)
            self.assertIn("(PRODUCT.md is empty)", r.stdout)
            self.assertIn("(none)", r.stdout)


if __name__ == "__main__":
    unittest.main()
