import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/pavedline/scripts/launch_check.py"


class LaunchCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name)
        (self.repo / "docs/production").mkdir(parents=True)
        (self.repo / "decisions").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, text=None):
        if text is not None:
            (self.repo / "docs/production/LAUNCH.md").write_text(text)
        r = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo)], capture_output=True, text=True)
        return r.returncode, r.stdout

    def adr(self, name, status):
        (self.repo / "decisions" / (name + ".md")).write_text("# t\n\n- Date: 2026-11-09\n- Status: %s\n" % status)

    def test_all_ticked(self):
        self.assertEqual(self.run_check("# L\n- [x] one\n- [X] two\n")[0], 0)

    def test_one_open(self):
        code, out = self.run_check("- [x] one\n- [ ] store approvals\n")
        self.assertEqual(code, 1)
        self.assertIn("store approvals", out)
        self.assertNotIn("one\n", out.replace("store approvals", ""))

    def test_exception_with_adr(self):
        self.adr("0042-risk", "accepted")
        self.assertEqual(self.run_check("- [ ] observability exception: decisions/0042-risk.md\n- [x] b\n")[0], 0)

    def test_exception_missing_adr(self):
        code, out = self.run_check("- [ ] observability exception: decisions/0099-nope.md\n")
        self.assertEqual(code, 1)
        self.assertIn("does not exist", out)

    def test_exception_superseded_adr(self):
        self.adr("0042-risk", "superseded by 0050")
        code, out = self.run_check("- [ ] observability exception: decisions/0042-risk.md\n")
        self.assertEqual(code, 1)
        self.assertIn("superseded", out)

    def test_custom_item_open(self):
        code, out = self.run_check("- [x] a\n- [ ] custom item added later\n")
        self.assertEqual(code, 1)
        self.assertIn("custom item added later", out)

    def test_missing_file(self):
        self.assertEqual(self.run_check()[0], 2)

    def test_no_items(self):
        self.assertEqual(self.run_check("# nothing here\n")[0], 2)

    def adr_text(self, name, text):
        (self.repo / "decisions" / (name + ".md")).write_text(text)

    def test_malformed_checkbox_lines_fail_closed(self):
        for bad in ("-[ ] x", "- [ ]x", "- [ ]", "+ [ ] x", "1. [ ] x", "- [] x", "* [ ] x", "- [ ]  "):
            code, out = self.run_check("- [x] ok\n%s\n" % bad)
            self.assertEqual(code, 1, bad)
            self.assertIn("line 2", out, bad)

    def test_items_inside_fences_or_comments_are_errors(self):
        for text in ("- [x] a\n```\n- [ ] example\n```\n", "- [x] a\n<!-- - [ ] hidden -->\n",
                     "<!--\n- [x] a\n-->\n```\n- [x] b\n```\n", "- [x] a\n<!--\n- [ ] x\n-->\n",
                     "- [x] a\n~~~\n- [x] b\n~~~\n"):
            code, out = self.run_check(text)
            self.assertEqual(code, 1, text)
            self.assertIn("inside a code block or comment", out, text)

    def test_unclosed_fence_or_comment_is_an_error(self):
        for text in ("- [x] ok\n```\n- [ ] x\n", "- [x] ok\n<!-- start\n- [ ] x\n", "- [x] ok\n```\ntext\n"):
            code, out = self.run_check(text)
            self.assertEqual(code, 1, text)
            self.assertIn("unclosed", out, text)
            self.assertIn("line 2", out, text)

    def test_longer_fence_containing_shorter_one(self):
        code, out = self.run_check("- [x] ok\n````\n```\n````\n- [ ] x\n")
        self.assertEqual(code, 1)
        self.assertIn("line 5", out)
        self.assertNotIn("inside a code block", out)  # the fence holds no items; the open item is reported

    def test_four_space_indent_is_not_a_fence(self):
        code, out = self.run_check("- [x] ok\n    ```\n- [ ] x\n")
        self.assertEqual(code, 1)
        self.assertIn("line 3", out)

    def test_clean_fence_without_items_is_fine(self):
        self.assertEqual(self.run_check("- [x] a\n```\nsome code\n```\n<!-- note -->\n")[0], 0)
        self.assertEqual(self.run_check("- [x] a <!-- note -->\n")[0], 0)

    def test_exception_must_be_exact_trailing_form(self):
        self.adr("0001-risk", "accepted")
        for bad in ("x (no exception: decisions/0001-risk.md needed)", "x exception: decisions/0001-risk",
                    "x exception: decisions/0001-risk.md and more", "x exception: decisions/0001.md"):
            self.assertEqual(self.run_check("- [ ] %s\n" % bad)[0], 1, bad)
        self.assertEqual(self.run_check("- [ ] x exception: decisions/0001-risk.md\n")[0], 0)

    def test_adr_must_be_accepted(self):
        bad = {
            "0002-a": "",
            "0003-b": "# t\n\n- Status: proposed\n",
            "0004-c": "# t\n\n- Status: proposed | accepted | superseded by NNNN\n",
            "0005-d": "# t\n\n**Status:** Superseded by 0002\n",
            "0006-e": "# t\n\n## Status\nSuperseded\n",
            "0007-f": "# t\n\nno status here\n",
            "0008-g": "# t\n\n- Status: SUPERSEDED by 0001\n",
        }
        for name, text in bad.items():
            self.adr_text(name, text)
            self.assertEqual(self.run_check("- [ ] x exception: decisions/%s.md\n" % name)[0], 1, name)
        for name, text in {"0009-h": "# t\n\n- Status: accepted\n", "0010-i": "# t\n\n**Status:** Accepted\n",
                           "0011-j": "# t\n\n## Status\naccepted\n"}.items():
            self.adr_text(name, text)
            self.assertEqual(self.run_check("- [ ] x exception: decisions/%s.md\n" % name)[0], 0, name)

    def test_shipped_template_is_all_open(self):
        text = (ROOT / "plugins/pavedline/templates/docs/production/LAUNCH.md").read_text()
        code, out = self.run_check(text)
        self.assertEqual(code, 1)
        self.assertIn("10 problem(s) in 10", out)


if __name__ == "__main__":
    unittest.main()
