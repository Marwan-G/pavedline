import pathlib
import re
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


if __name__ == "__main__":
    unittest.main()
