import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "plugins" / "pavedline" / "scripts" / "hooks" / "guard_git.py"


def run_raw(stdin):
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True)


def run(command):
    return run_raw(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))


class GitGuardTests(unittest.TestCase):
    def blocked(self, c):
        r = run(c)
        self.assertEqual(r.returncode, 2, (c, r.stderr))
        self.assertIn("Blocked", r.stderr)

    def allowed(self, c):
        r = run(c)
        self.assertEqual(r.returncode, 0, (c, r.stderr))

    def test_blocks_no_verify(self):
        self.blocked("git commit --no-verify -m x")

    def test_blocks_force_push_main(self):
        self.blocked("git push --force origin main")

    def test_allows_force_push_branch(self):
        self.allowed("git push --force-with-lease origin feat/x")

    def test_allows_normal_push(self):
        self.allowed("git push origin main")
        self.allowed("git push")
        self.allowed("git push -u origin feat/x")

    def test_no_verify_forms(self):
        for c in ["git commit -n -m x", "git commit -nm x", "git commit -anm x", "git commit -m x -n",
                  "git push --no-verify", "git merge --no-verify x", "git am --no-verify p",
                  "git commit --no-verif -m x", "git commit --no-ver -m x",
                  "git -c core.hooksPath=/dev/null commit -m x",
                  "git -C repo commit --no-verify -m x", "git rebase --no-verify main"]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_no_verify_lookalikes_allowed(self):
        for c in ["git push -n", "git push --dry-run origin main", "git log -n 5", "git commit -m n",
                  "git commit -m 'explain --no-verify'", "git commit -am msg", "git commit -mn",
                  "git diff --no-ext-diff", "git status", "git commit -m x"]:
            with self.subTest(c=c):
                self.allowed(c)

    def test_force_push_main_forms(self):
        for c in ["git push -f origin main", "git push origin main -f", "git push --force origin master",
                  "git push --force-with-lease origin main", "git push --force-with-lease=main origin main",
                  "git push --force-if-includes origin main", "git push --forc origin main",
                  "git push origin +main", "git push origin +refs/heads/main",
                  "git push origin HEAD:main --force", "git push origin +HEAD:main",
                  "git push origin +feat:main", "git push -fu origin main",
                  "git push -f origin refs/heads/main:refs/heads/main",
                  "git push -f", "git push -f origin", "git push --force-with-lease",
                  "git push -f origin HEAD", "git push --force --all", "git push --force --mirror",
                  "git push -f origin 'refs/heads/*:refs/heads/*'", "git push origin :main",
                  "git -C r push -f origin main"]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_safe_pushes(self):
        for c in ["git push --force-with-lease origin feat/x", "git push -f origin feat/x",
                  "git push origin +feat/x", "git push origin HEAD:feat/x", "git push origin main",
                  "git push origin HEAD:main", "git push origin main:feat/x"]:
            with self.subTest(c=c):
                self.allowed(c)

    def test_nested_and_chained(self):
        for c in ['bash -c "git push -f origin main"', "sh -c 'git commit --no-verify -m x'",
                  'eval "git push --force origin main"', "echo $(git push -f origin main)",
                  "git add . && git commit --no-verify -m x", "true; git push -f origin master",
                  "echo y | git push --force origin main", "sudo git push -f origin main",
                  "/usr/bin/git push -f origin main", "env X=1 git commit --no-verify -m x",
                  "git status\ngit push -f origin main"]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_malformed_input_fails_open(self):
        for stdin in ["", "nope", "[]", json.dumps({"tool_name": "Bash"}),
                      json.dumps({"tool_name": "Bash", "tool_input": {"command": 1}}),
                      json.dumps({"tool_name": "Write", "tool_input": {"file_path": "x"}})]:
            with self.subTest(stdin=stdin):
                self.assertEqual(run_raw(stdin).returncode, 0)

    def test_non_git_commands_allowed(self):
        self.allowed("ls -la")
        self.allowed("echo --no-verify")


if __name__ == "__main__":
    unittest.main()
