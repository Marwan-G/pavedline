import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pr_checks.py"
GOOD = "Gates: TDD ✓ · review ✓ (3 found, 3 fixed) · security ✓ · adversarial n/a · verification ✓"


def run(body):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "body.txt"
        f.write_text(body, encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), "--body-file", str(f)],
                              capture_output=True, text=True)


class PrChecksTests(unittest.TestCase):
    def test_accepts_valid_gates_line(self):
        self.assertEqual(run("Summary\n\n" + GOOD + "\n\nPost-deploy check: none").returncode, 0)
        self.assertEqual(run(GOOD.replace("n/a", "✓")).returncode, 0)

    def test_rejects_cross_value(self):
        self.assertEqual(run(GOOD.replace("security ✓", "security ✗")).returncode, 1)

    def test_rejects_missing_line(self):
        self.assertEqual(run("no gates here").returncode, 1)

    def test_rejects_trailing_text_and_missing_file(self):
        self.assertEqual(run(GOOD + " extra").returncode, 1)
        r = subprocess.run([sys.executable, str(SCRIPT), "--body-file", "/nonexistent/x"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


class RenovateExemptionTests(unittest.TestCase):
    def go(self, ref, files, body="no gates"):
        with tempfile.TemporaryDirectory() as d:
            b, c = Path(d) / "b.txt", Path(d) / "c.txt"
            b.write_text(body, encoding="utf-8")
            c.write_text("\n".join(files), encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), "--body-file", str(b), "--head-ref", ref,
                                   "--changed-files-file", str(c)], capture_output=True, text=True).returncode

    def test_renovate_ref_with_only_dependency_files_passes(self):
        self.assertEqual(self.go("renovate/x", ["renovate.json", ".github/workflows/ci.yml",
                                                 "plugins/pavedline/scripts/local-cluster/versions.env"]), 0)

    def test_renovate_ref_with_code_file_requires_gates(self):
        self.assertEqual(self.go("renovate/x", ["renovate.json", "scripts/pr_checks.py"]), 1)
        self.assertEqual(self.go("renovate/x", ["scripts/pr_checks.py"], GOOD), 0)

    def test_non_renovate_ref_requires_gates(self):
        self.assertEqual(self.go("feature/x", ["renovate.json"]), 1)

    def test_empty_change_list_requires_gates(self):
        self.assertEqual(self.go("renovate/x", []), 1)


class ContributorPrTests(unittest.TestCase):
    """A PR from a fork is a contributor's: the maintainer's local review and approval are its gate, not this line."""

    def go(self, body, head_repo, base_repo="Marwan-G/pavedline"):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.txt"
            b.write_text(body, encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), "--body-file", str(b),
                                   "--head-repo", head_repo, "--base-repo", base_repo],
                                  capture_output=True, text=True)

    def test_fork_pr_needs_no_gates_line(self):
        r = self.go("Fixes a typo in the README.", "someone/pavedline")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("contributor pull request", r.stdout)

    def test_deleted_fork_counts_as_contributor(self):
        self.assertEqual(self.go("text", "").returncode, 0)

    def test_same_repo_pr_still_needs_gates_line(self):
        self.assertEqual(self.go("no gates", "Marwan-G/pavedline").returncode, 1)
        self.assertEqual(self.go("no gates", "marwan-g/Pavedline").returncode, 1, "repo names compare case-insensitively")
        self.assertEqual(self.go(GOOD, "Marwan-G/pavedline").returncode, 0)

    def test_without_repo_flags_behaves_as_before(self):
        self.assertEqual(run("no gates").returncode, 1)

    def test_ci_passes_the_repos_through_env(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}", ci)
        self.assertIn("BASE_REPO: ${{ github.repository }}", ci)
        self.assertIn('--head-repo "$HEAD_REPO" --base-repo "$BASE_REPO"', ci)


if __name__ == "__main__":
    unittest.main()
