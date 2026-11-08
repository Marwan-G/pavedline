import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github/workflows/ci.yml"


class CiDownloads(unittest.TestCase):
    """GitHub release downloads returned 504 for hours on 2026-11-08; CI must not fail on a brief outage."""

    def setUp(self):
        self.ci = CI.read_text()

    def test_gitleaks_runs_from_its_official_image_pinned_by_digest(self):
        self.assertRegex(self.ci, r"uses: docker://ghcr\.io/gitleaks/gitleaks:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}\n")
        self.assertNotIn("gitleaks/gitleaks/releases/download", self.ci)
        self.assertIn("args: dir /github/workspace --no-banner --redact", self.ci)

    def test_every_download_retries_and_fails_loudly(self):
        curls = [l for l in self.ci.splitlines() if re.search(r"\bcurl\b", l) and not l.strip().startswith("#")]
        self.assertGreaterEqual(len(curls), 2, curls)
        for line in curls:
            for flag in ("--fail", "--retry 6", "--retry-delay 20", "--retry-all-errors"):
                self.assertIn(flag, line, line.strip())

    def test_every_download_is_still_checksum_verified(self):
        downloads = len(re.findall(r"\bcurl\b[^\n]*-O\b", self.ci))
        checks = self.ci.count("sha256sum --check --strict")
        self.assertEqual(downloads, checks)


if __name__ == "__main__":
    unittest.main()
