import hashlib
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import dot_check  # noqa: E402
import dot_drift  # noqa: E402
GOOD = "digraph g { a -> b }\n"


class ValidateTests(unittest.TestCase):
    def test_validate_rejects_syntax_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.dot"
            p.write_text("digraph{a->}")
            ok, _ = dot_check.validate(p)
            self.assertFalse(ok)

    def test_validate_accepts_flow(self):
        ok, _ = dot_check.validate(ROOT / "docs" / "flow.dot")
        self.assertTrue(ok)


class RenderCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dot = Path(self.tmp.name) / "a.dot"
        self.dot.write_text(GOOD)

    def tearDown(self):
        self.tmp.cleanup()

    def test_render_writes_hash(self):
        svg = dot_check.render(self.dot)
        self.assertEqual(svg, self.dot.with_suffix(".svg"))
        text = svg.read_text()
        digest = hashlib.sha256(self.dot.read_bytes()).hexdigest()
        self.assertIn(f"<!-- dot-source-sha256: {digest} -->", text)

    def test_check_passes_after_render(self):
        dot_check.render(self.dot)
        self.assertEqual(dot_check.check([self.dot]), [])

    def test_check_fails_on_missing_svg(self):
        self.assertEqual(len(dot_check.check([self.dot])), 1)

    def test_check_fails_on_stale_hash(self):
        dot_check.render(self.dot)
        self.dot.write_text("digraph g { a -> c }\n")
        self.assertEqual(len(dot_check.check([self.dot])), 1)

    def test_check_fails_on_invalid_dot(self):
        self.dot.write_text("digraph{a->}")
        self.assertEqual(len(dot_check.check([self.dot])), 1)


IGNORE = dot_drift.parse_globs("# c\n\n**/*.md\ndocs/**\ntests/**\n**/*.svg\n")


class DriftIgnoreTests(unittest.TestCase):
    def test_docs_only_change_has_no_owner(self):
        self.assertEqual(dot_drift.drift(["docs/a/b.md", "README.md", "x/y.svg"], ["."], "", IGNORE), [])

    def test_tests_only_change_has_no_owner(self):
        self.assertEqual(dot_drift.drift(["tests/test_x.py"], ["."], "", IGNORE), [])

    def test_script_change_still_flags_root(self):
        self.assertEqual(dot_drift.drift(["scripts/x.py", "docs/a.md"], ["."], "", IGNORE), ["."])

    def test_comments_and_blanks_skipped(self):
        self.assertEqual(IGNORE, ["**/*.md", "docs/**", "tests/**", "**/*.svg"])


class DriftTests(unittest.TestCase):
    def test_drift_flags_owner_without_dot_change(self):
        self.assertEqual(dot_drift.drift(["plugins/pavedline/x.py"], ["."], ""), ["."])

    def test_drift_passes_when_dot_changed(self):
        changed = ["plugins/pavedline/x.py", "ARCHITECTURE.dot"]
        self.assertEqual(dot_drift.drift(changed, ["."], ""), [])

    def test_drift_passes_with_reason(self):
        self.assertEqual(
            dot_drift.drift(["plugins/pavedline/x.py"], ["."], "diagram unchanged: typo only"), [])

    def test_nearest_owner_wins(self):
        owners = [".", "plugins/pavedline"]
        self.assertEqual(dot_drift.drift(["plugins/pavedline/x.py"], owners, ""), ["plugins/pavedline"])


if __name__ == "__main__":
    unittest.main()
