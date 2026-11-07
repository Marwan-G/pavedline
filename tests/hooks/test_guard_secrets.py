import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOKS = ROOT / "plugins" / "pavedline" / "scripts" / "hooks"
SCRIPT = HOOKS / "guard_secrets.py"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(HOOKS))


def run(stdin: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True
    )


def run_fixture(name: str):
    return run((FIXTURES / (name + ".json")).read_text())


def run_payload(tool, tool_input, cwd="/work/proj"):
    return run(
        json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s",
                "cwd": cwd,
                "tool_name": tool,
                "tool_input": tool_input,
            }
        )
    )


PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"
GHP = "ghp" + "_" + "a" * 36
ANT = "sk" + "-ant-" + "a" * 24
AWS = "AK" + "IA" + "A" * 16


class GuardTests(unittest.TestCase):
    def assertBlocked(self, r):
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertTrue(r.stderr.strip())

    def assertAllowed(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_blocks_read_env(self):
        self.assertBlocked(run_fixture("read_env"))

    def test_blocks_env_local(self):
        self.assertBlocked(run_fixture("read_env_local"))

    def test_blocks_nested_env(self):
        self.assertBlocked(run_fixture("read_nested_env"))

    def test_blocks_edit_env(self):
        self.assertBlocked(run_fixture("edit_env"))

    def test_blocks_env_even_without_other_fields(self):
        self.assertBlocked(run_fixture("write_env_missing_content"))

    def test_allows_env_example(self):
        self.assertAllowed(run_fixture("read_env_example"))

    def test_allows_sample_and_template(self):
        for n in (".env.sample", ".env.template"):
            self.assertAllowed(run_payload("Read", {"file_path": n}))

    def test_envrc_is_not_env_file(self):
        self.assertAllowed(run_payload("Read", {"file_path": ".envrc"}))

    def test_allows_normal_file(self):
        self.assertAllowed(run_fixture("read_readme"))
        self.assertAllowed(run_fixture("write_plain"))

    def test_relative_path_resolved_against_cwd_basename_still_env(self):
        self.assertBlocked(run_payload("Read", {"file_path": "sub/.env"}, cwd="/x"))

    def test_blocks_bash_cat_env(self):
        self.assertBlocked(run_fixture("bash_cat_env"))

    def test_blocks_bash_redirect_read(self):
        self.assertBlocked(run_fixture("bash_redirect_env"))

    def test_blocks_bash_grep_nested_env(self):
        self.assertBlocked(run_fixture("bash_grep_env"))

    def test_blocks_bash_variants(self):
        for cmd in ("source .env", ". .env", "head -n1 .env.local", "cp .env /tmp/x",
                    "base64 .env", "sed -n 1p .env", "less .env", "tail .env",
                    "cat a.txt && cat .env"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(run_payload("Bash", {"command": cmd}))

    def test_blocks_bash_any_verb_naming_env(self):
        for cmd in ("sort .env", "cut -d= -f1 .env", "wc .env", "diff .env x", "tac .env",
                    "nl .env", "xxd .env", "od .env", "strings .env", "dotenv -f .env",
                    "git show HEAD:.env", "echo .env", "cat .ENV", "ls .env | cat .env"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(run_payload("Bash", {"command": cmd}))

    def test_blocks_bash_nested(self):
        for cmd in ('bash -c "cat .env"', "sh -c 'cat .env'", 'eval "cat .env"',
                    "python3 -c \"open('.env').read()\"", "cat `echo .env`",
                    "cat $(echo .env)", "node -e \"require('fs').readFileSync('.env')\"",
                    "ls $(cat .env)"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(run_payload("Bash", {"command": cmd}))

    def test_case_insensitive_env(self):
        self.assertBlocked(run_payload("Read", {"file_path": ".ENV"}))
        self.assertBlocked(run_payload("Read", {"file_path": ".Env.Local"}))
        self.assertAllowed(run_payload("Read", {"file_path": ".ENV.EXAMPLE"}))

    def test_multiedit(self):
        self.assertBlocked(run_payload("MultiEdit", {"file_path": ".env", "edits": []}))
        self.assertBlocked(run_payload("MultiEdit", {"file_path": "a.txt", "edits": [
            {"old_string": "a", "new_string": "ok"}, {"old_string": "b", "new_string": GHP}]}))
        self.assertAllowed(run_payload("MultiEdit", {"file_path": "a.txt", "edits": [
            {"old_string": "a", "new_string": "ok"}]}))

    def test_notebookedit(self):
        self.assertBlocked(run_payload("NotebookEdit", {"notebook_path": ".env"}))
        self.assertBlocked(run_payload("NotebookEdit", {"notebook_path": "n.ipynb", "new_source": GHP}))
        self.assertAllowed(run_payload("NotebookEdit", {"notebook_path": "n.ipynb", "new_source": "x"}))

    def test_grep_tool(self):
        self.assertBlocked(run_payload("Grep", {"pattern": "KEY", "path": ".env"}))
        self.assertBlocked(run_payload("Grep", {"pattern": "KEY", "glob": ".env*"}))
        self.assertBlocked(run_payload("Grep", {"pattern": "KEY", "glob": "*.env"}))
        self.assertBlocked(run_payload("Grep", {"pattern": "KEY", "glob": "**/.env.local"}))
        self.assertAllowed(run_payload("Grep", {"pattern": "KEY", "path": "src", "glob": "*.py"}))
        self.assertAllowed(run_payload("Grep", {"pattern": "KEY", "glob": ".env.example"}))

    def test_hooks_json_matcher_covers_tools(self):
        cfg = json.loads((ROOT / "plugins/pavedline/hooks/hooks.json").read_text())
        m = cfg["hooks"]["PreToolUse"][0]["matcher"].split("|")
        for t in ("Read", "Write", "Edit", "Bash", "MultiEdit", "NotebookEdit", "Grep"):
            self.assertIn(t, m)

    def test_bash_unbalanced_quote_falls_back(self):
        self.assertBlocked(run_payload("Bash", {"command": "cat .env 'oops"}))

    def test_allows_bash_normal(self):
        self.assertAllowed(run_fixture("bash_ls"))
        self.assertAllowed(run_fixture("bash_cat_example"))
        for cmd in ("ls -la .env", "stat .env", "test -f .env", "[ -f .env ]", "rm .env",
                    "mv .env .env.bak", "touch .env", "git add .env", "git rm .env",
                    "git mv .env x", "git check-ignore .env", "echo hi > .env",
                    "ls; cat README.md"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(run_payload("Bash", {"command": cmd}))

    def test_blocks_write_with_private_key(self):
        self.assertBlocked(
            run_payload("Write", {"file_path": "k.txt", "content": "x\n" + PEM + "\n"})
        )

    def test_blocks_write_with_tokens(self):
        for secret in (GHP, ANT, AWS):
            with self.subTest(secret=secret[:6]):
                self.assertBlocked(
                    run_payload("Write", {"file_path": "a.txt", "content": "k=" + secret})
                )

    def test_blocks_edit_new_string_secret(self):
        self.assertBlocked(
            run_payload("Edit", {"file_path": "a.txt", "old_string": "a", "new_string": GHP})
        )

    def test_edit_old_string_secret_not_checked(self):
        self.assertAllowed(
            run_payload("Edit", {"file_path": "a.txt", "old_string": GHP, "new_string": "x"})
        )

    def test_malformed_stdin_fails_open(self):
        for s in ("", "not json", "[1,2]"):
            with self.subTest(s=s):
                r = run(s)
                self.assertEqual(r.returncode, 0)
                self.assertTrue(r.stderr.strip())

    def test_unknown_tool_allowed(self):
        self.assertAllowed(run_payload("Glob", {"pattern": "**/.env"}))


class CommonTests(unittest.TestCase):
    def test_is_env_file(self):
        import _common

        yes = [".ENV", ".env", ".env.local", "a/b/.env.production", "/abs/.env"]
        no = [".env.example", ".ENV.Example", ".env.sample", ".env.template", ".envrc", "env", "x.env", "README.md"]
        for p in yes:
            self.assertTrue(_common.is_env_file(p), p)
        for p in no:
            self.assertFalse(_common.is_env_file(p), p)

    def test_secret_patterns_in_sync_with_denylist(self):
        import _common

        lines = (ROOT / ".sanitize-denylist").read_text().splitlines()
        for pat in _common.SECRET_PATTERNS:
            self.assertIn(pat, lines)
        # compile sanity
        for pat in _common.SECRET_PATTERNS:
            re.compile(pat)


if __name__ == "__main__":
    unittest.main()
