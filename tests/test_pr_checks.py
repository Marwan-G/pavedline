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


if __name__ == "__main__":
    unittest.main()
