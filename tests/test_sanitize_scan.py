import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import sanitize_scan  # noqa: E402

TOKEN = "ocid" + "1."  # built at runtime so this file does not trip the scan
OCID = [re.compile(re.escape(TOKEN))]


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_flags_ocid(self):
        f = self.dir / "a.txt"
        f.write_text(TOKEN + "tenancy.oc1..aaaa\n")
        found = sanitize_scan.scan([f], OCID)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 1)

    def test_local_extension_patterns_apply(self):
        (self.dir / ".sanitize-denylist").write_text("# generic\n" + re.escape(TOKEN) + "\n")
        (self.dir / ".sanitize-denylist.local").write_text("secretcorp\n")
        pats = sanitize_scan.load_patterns(self.dir)
        f = self.dir / "b.txt"
        f.write_text("hello\nworks at secretcorp\n")
        found = sanitize_scan.scan([f], pats)
        self.assertEqual([x.line for x in found], [2])

    def test_skips_binary(self):
        f = self.dir / "c.bin"
        f.write_bytes(b"\x00" + TOKEN.encode() + b"tenancy")
        self.assertEqual(sanitize_scan.scan([f], OCID), [])

    def test_scans_svg(self):
        f = self.dir / "d.svg"
        f.write_text("<svg><!-- " + TOKEN + "x --></svg>")
        self.assertEqual(len(sanitize_scan.scan([f], OCID)), 1)

    def test_clean_file_passes(self):
        f = self.dir / "e.txt"
        f.write_text("nothing here\n")
        self.assertEqual(sanitize_scan.scan([f], OCID), [])


A = "10"  # built at runtime so this file does not trip the scan
B = "192.168"


class DenyListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pats = sanitize_scan.load_patterns(ROOT)

    def hits(self, text):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d, True))
        f = d / "x.txt"
        f.write_text(text + "\n")
        return sanitize_scan.scan([f], self.pats)

    def test_network_blocks_pass(self):
        for s in (A + ".0.0.0/8", "172" + ".16.0.0/12", B + ".0.0/16"):
            self.assertEqual(self.hits(s), [], s)

    def test_hosts_fail_even_with_a_prefix(self):
        for s in (A + ".0.0.5/32", B + ".1.7", "172" + ".16.0.9/24", A + ".1.2.3"):
            self.assertEqual(len(self.hits(s)), 1, s)


if __name__ == "__main__":
    unittest.main()


class UntrackedFilesAreScanned(unittest.TestCase):
    """The scan covers tracked and untracked-not-ignored files, in Pavedline and in the product copy."""

    COPIES = (ROOT / "scripts/sanitize_scan.py", ROOT / "plugins/pavedline/templates/scripts/sanitize_scan.py")

    def run_in_repo(self, script, files, ignore=""):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "scripts").mkdir()
            shutil.copy(script, d / "scripts/sanitize_scan.py")
            (d / ".sanitize-denylist").write_text(re.escape(TOKEN) + "\n")
            (d / ".gitignore").write_text(ignore)
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "add", "-A"], cwd=d, check=True)  # tracked baseline: denylist, gitignore, script
            for name, text in files.items():
                (d / name).write_text(text)
            return subprocess.run([sys.executable, "scripts/sanitize_scan.py"], cwd=d, capture_output=True, text=True)

    def test_untracked_file_with_a_denied_pattern_fails(self):
        for script in self.COPIES:
            r = self.run_in_repo(script, {"new.txt": TOKEN + "x\n"})
            self.assertEqual(r.returncode, 1, (script, r.stdout, r.stderr))
            self.assertIn("new.txt", r.stdout)

    def test_ignored_file_is_not_scanned(self):
        for script in self.COPIES:
            r = self.run_in_repo(script, {"skip.txt": TOKEN + "x\n"}, ignore="skip.txt\n")
            self.assertEqual(r.returncode, 0, (script, r.stdout, r.stderr))
