import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOKS = ROOT / "plugins" / "pavedline" / "scripts" / "hooks"
sys.path.insert(0, str(ROOT / "tests" / "hooks"))
from test_warn_hooks import git, run  # noqa: E402

GOOD = ("Model: sonnet\nStatus: DONE\n"
        "Gates: TDD ✓ · review pending · security pending · adversarial pending · verification ✓\n"
        "Branch head: abc1234\n")


class DotDriftState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name, "repo")
        (self.root / "api").mkdir(parents=True)
        (self.root / "api" / "ARCHITECTURE.dot").write_text("digraph {}\n")
        (self.root / "api" / "main.py").write_text("x = 1\n")
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        (self.root / "api" / "main.py").write_text("x = 2\n")
        self.temp = pathlib.Path(self.tmp.name, "temp")
        self.data = pathlib.Path(self.tmp.name, "data")
        self.temp.mkdir()

    def go(self, plugin_data):
        ev = {"session_id": "s", "cwd": str(self.root),
              "tool_input": {"file_path": str(self.root / "api" / "main.py")}}
        return run("warn_dot_drift.py", ev, env={"TMPDIR": str(self.temp), "CLAUDE_PLUGIN_DATA": plugin_data})

    def test_markers_go_to_plugin_data_when_set(self):
        r = self.go(str(self.data))
        self.assertIn("ARCHITECTURE.dot", r.stderr + r.stdout)
        self.assertEqual(len(list((self.data / "dot-drift").iterdir())), 1)
        self.assertFalse(list(self.temp.rglob("pavedline-dot-drift")))
        self.assertEqual((self.go(str(self.data)).stderr), "")  # once per session

    def test_falls_back_to_temp_when_unset_or_empty(self):
        r = self.go("")
        self.assertIn("ARCHITECTURE.dot", r.stderr + r.stdout)
        self.assertEqual(len(list((self.temp / "pavedline-dot-drift").iterdir())), 1)
        self.assertFalse(self.data.exists())


def stop(event=None, raw=None):
    return run("check_builder_report.py", event, raw=raw)


def ev(msg, agent="pavedline:builder", active=False):
    return {"hook_event_name": "SubagentStop", "agent_type": agent, "stop_hook_active": active,
            "last_assistant_message": msg}


class BuilderReportHook(unittest.TestCase):
    def blocked(self, r):
        # Warn only, never block (plan Task 2): a builder may deliver its report through a hand-back the hook
        # cannot see, so blocking could stop a correct builder.
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertNotIn("decision", out)
        self.assertTrue(out["systemMessage"])
        return out["systemMessage"]

    def silent(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")

    def test_good_report_passes(self):
        self.silent(stop(ev(GOOD)))

    def test_blocked_report_needs_no_gates_line(self):
        self.silent(stop(ev("Model: sonnet\nStatus: BLOCKED — docker not usable; nothing built\n")))

    def test_missing_status_blocks_once(self):
        reason = self.blocked(stop(ev("Model: sonnet\nall done\n")))
        self.assertIn("Status", reason)

    def test_done_without_gates_line_blocks(self):
        reason = self.blocked(stop(ev("Model: sonnet\nStatus: DONE\n")))
        self.assertIn("Gates", reason)

    def test_empty_or_missing_message_is_silent(self):
        self.silent(stop(ev("")))
        self.silent(stop(ev(None)))

    def test_stop_hook_active_never_blocks_again(self):
        self.silent(stop(ev("nothing useful", active=True)))

    def test_other_agents_ignored(self):
        self.silent(stop(ev("nothing useful", agent="pavedline:reviewer")))
        self.silent(stop(ev("nothing useful", agent="Explore")))

    def test_bare_builder_name_is_not_ours(self):
        self.silent(stop(ev("nothing useful", agent="builder")))

    def test_malformed_input_fails_open(self):
        for raw in ("", "not json", "[1]", json.dumps({"agent_type": "builder"})):
            r = stop(raw=raw)
            self.assertEqual(r.returncode, 0, raw)
            if raw.strip().startswith("{"):
                continue
            self.assertEqual(r.stdout, "", raw)

    def test_non_string_message_fails_open_or_blocks_without_crash(self):
        r = stop(ev(None))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_registered_in_hooks_json(self):
        h = json.loads((ROOT / "plugins/pavedline/hooks/hooks.json").read_text())["hooks"]
        groups = [g for g in h["SubagentStop"]
                  if any("check_builder_report.py" in x["command"] for x in g["hooks"])]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["matcher"], "pavedline:builder")
        self.assertEqual(groups[0]["hooks"][0].get("timeout"), 10)


class BuilderAgent(unittest.TestCase):
    def test_max_turns_and_partial_rule(self):
        text = (ROOT / "plugins/pavedline/agents/builder.md").read_text()
        front = text.split("---")[1]
        self.assertRegex(front, r"(?m)^maxTurns: \d+$")
        self.assertIn("partial", text)
        self.assertIn("BLOCKED", text)
        self.assertRegex(text, r"(?m)^\d+\. \*\*Report status")


if __name__ == "__main__":
    unittest.main()
