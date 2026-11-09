import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOKS = ROOT / "plugins" / "pavedline" / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(ROOT / "scripts"))
import _common  # noqa: E402
import pr_checks  # noqa: E402

GOOD = "Gates: TDD ✓ · review ✓ (2 found, 2 fixed) · security ✓ · adversarial n/a · verification ✓"


def run(script, event=None, raw=None, env=None):
    stdin = raw if raw is not None else json.dumps(event)
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, str(HOOKS / script)], input=stdin, capture_output=True,
                          text=True, env=e)


def bash(command):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}


class PrGatesTests(unittest.TestCase):
    def warned(self, command):
        r = run("warn_pr_gates.py", bash(command))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Gates:", r.stderr + r.stdout, command)

    def silent(self, command):
        r = run("warn_pr_gates.py", bash(command))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((r.stderr, r.stdout), ("", ""), command)

    def test_regex_has_one_source(self):
        self.assertEqual(_common.GATES_LINE.pattern, pr_checks.GATES.pattern)
        self.assertEqual(_common.GATES_LINE.flags, pr_checks.GATES.flags)

    def test_missing_gates_line_warns(self):
        self.warned('gh pr create --title t --body "a plain body"')
        self.warned("gh pr create -t t -b 'a plain body'")
        self.warned("gh pr create --body='a plain body'")
        self.warned('gh pr edit 3 --body "no gates here"')
        self.warned('gh pr create --fill')

    def test_bad_gates_line_warns(self):
        self.warned('gh pr create --body "Gates: TDD ✗ · review ✓ (1 found, 1 fixed) · security ✓ · '
                    'adversarial ✓ · verification ✓"')

    def test_good_gates_line_is_silent(self):
        self.silent('gh pr create --title t --body "Short.\n%s"' % GOOD)
        self.silent("gh pr create -b '%s'" % GOOD)
        self.silent("gh pr create --body \"$(cat <<'EOF'\nSummary\n%s\nEOF\n)\"" % GOOD)

    def test_body_file(self):
        with tempfile.TemporaryDirectory() as d:
            good = pathlib.Path(d, "good.md")
            good.write_text("x\n%s\n" % GOOD)
            bad = pathlib.Path(d, "bad.md")
            bad.write_text("x\n")
            self.silent("gh pr create --body-file %s" % good)
            self.silent("gh pr create -F %s" % good)
            self.warned("gh pr create --body-file %s" % bad)
            self.silent("gh pr create --body-file %s/missing.md" % d)  # unreadable: cannot judge
        self.silent("gh pr create --body-file -")

    def test_other_commands_are_silent(self):
        self.silent("gh pr view 3")
        self.silent("gh pr edit 3 --title new")
        self.silent("gh issue create --body x")
        self.silent("git commit -m 'gh pr create --body x'")
        self.silent("ls")

    def test_wrapped_and_chained(self):
        self.warned("cd x && gh pr create --body 'nothing'")
        self.warned("env GH_TOKEN=x gh pr create --body 'nothing'")

    def test_fails_open(self):
        for raw in ("", "not json", "[]", '{"tool_input": 5}', '{"tool_input": {"command": 7}}'):
            r = run("warn_pr_gates.py", raw=raw)
            self.assertEqual(r.returncode, 0, raw)


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd,
                   check=True, capture_output=True)


class DotDriftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name, "repo")
        (self.root / "api" / "app").mkdir(parents=True)
        (self.root / "web").mkdir()
        (self.root / "api" / "ARCHITECTURE.dot").write_text("digraph {}\n")
        (self.root / "api" / "app" / "main.py").write_text("x = 1\n")
        (self.root / "web" / "page.ts").write_text("x\n")
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        self.state = pathlib.Path(self.tmp.name, "tmp")
        self.state.mkdir()

    def ev(self, path, session="s1"):
        return {"hook_event_name": "PostToolUse", "tool_name": "Edit", "session_id": session,
                "cwd": str(self.root), "tool_input": {"file_path": str(path)}}

    def go(self, path, session="s1"):
        return run("warn_dot_drift.py", self.ev(path, session), env={"TMPDIR": str(self.state)})

    def text(self, r):
        return r.stderr + r.stdout

    def test_edit_without_dot_change_warns(self):
        f = self.root / "api" / "app" / "main.py"
        f.write_text("x = 2\n")
        r = self.go(f)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("diagram unchanged:", self.text(r))
        self.assertIn("ARCHITECTURE.dot", self.text(r))

    def test_warns_once_per_folder_per_session(self):
        f = self.root / "api" / "app" / "main.py"
        f.write_text("x = 2\n")
        self.assertNotEqual(self.text(self.go(f)), "")
        self.assertEqual(self.text(self.go(f)), "")
        self.assertNotEqual(self.text(self.go(f, session="s2")), "")

    def test_dot_changed_is_silent(self):
        (self.root / "api" / "ARCHITECTURE.dot").write_text("digraph { a -> b }\n")
        f = self.root / "api" / "app" / "main.py"
        f.write_text("x = 2\n")
        self.assertEqual(self.text(self.go(f)), "")

    def test_folder_without_dot_is_silent(self):
        f = self.root / "web" / "page.ts"
        f.write_text("y\n")
        self.assertEqual(self.text(self.go(f)), "")

    def test_editing_the_diagram_itself_is_silent(self):
        f = self.root / "api" / "ARCHITECTURE.dot"
        f.write_text("digraph { a }\n")
        self.assertEqual(self.text(self.go(f)), "")

    def test_not_a_git_repo_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "ARCHITECTURE.dot").write_text("digraph {}\n")
            (p / "a.py").write_text("x\n")
            r = run("warn_dot_drift.py", {"session_id": "s", "cwd": d, "tool_input": {"file_path": str(p / "a.py")}},
                    env={"TMPDIR": str(self.state)})
            self.assertEqual((r.returncode, self.text(r)), (0, ""))

    def test_fails_open(self):
        for raw in ("", "not json", "[]", '{"tool_input": 5}', '{"tool_input": {"file_path": 3}}'):
            r = run("warn_dot_drift.py", raw=raw, env={"TMPDIR": str(self.state)})
            self.assertEqual(r.returncode, 0, raw)


class Registration(unittest.TestCase):
    def test_hooks_json(self):
        h = json.loads((ROOT / "plugins/pavedline/hooks/hooks.json").read_text())["hooks"]

        def cmds(event, matcher):
            return [x["command"] for g in h[event] if g["matcher"] == matcher for x in g["hooks"]]

        self.assertTrue(any("warn_pr_gates.py" in c for c in cmds("PreToolUse", "Bash")))
        post = [g["matcher"] for g in h["PostToolUse"]
                if any("warn_dot_drift.py" in x["command"] for x in g["hooks"])]
        self.assertEqual(post, ["Write|Edit|MultiEdit"])


class BodyLimit(unittest.TestCase):
    def test_body_file_read_is_capped(self):
        import importlib, sys as _s, tempfile, os
        hooks = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "pavedline", "scripts", "hooks")
        _s.path.insert(0, os.path.abspath(hooks))
        common = importlib.import_module("_common")
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write("x" * (3 << 20))
        try:
            self.assertEqual(len(common.read_text(fh.name, limit=1 << 20)), 1 << 20)
            self.assertEqual(len(common.read_text(fh.name)), 3 << 20)
        finally:
            os.unlink(fh.name)

    def test_new_warn_hooks_have_a_timeout(self):
        import json, os
        p = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "pavedline", "hooks", "hooks.json")
        d = json.load(open(p))
        cmds = [h for ev in d["hooks"].values() for m in ev for h in m["hooks"]]
        for name in ("warn_pr_gates", "warn_dot_drift"):
            h = [h for h in cmds if name in h["command"]][0]
            self.assertEqual(h.get("timeout"), 10, name)

    def test_oversized_body_file_hook_is_fast_and_warns(self):
        import time
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md") as fh:
            fh.write("x" * (1 << 20) + "\n" + GOOD + "\n")
        try:
            t = time.time()
            r = run("warn_pr_gates.py", bash("gh pr create --title t --body-file %s" % fh.name))
            self.assertLess(time.time() - t, 5)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Gates:", r.stderr + r.stdout)
        finally:
            os.unlink(fh.name)


if __name__ == "__main__":
    unittest.main()
