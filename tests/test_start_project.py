import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/pavedline/scripts/start_project.py"
TEMPLATES = ROOT / "plugins/pavedline/templates"
FIELDS = ["STEP", "WAVE", "SLICES IN FLIGHT", "LAST", "NEXT", "LEFT BEHIND", "STALE", "GROW DUE", "OWNER", "MODE"]


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def template_files():
    return sorted(p.relative_to(TEMPLATES).as_posix() for p in TEMPLATES.rglob("*") if p.is_file())


class StartProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, *extra):
        return run("--target", str(self.dir), "--name", "Acme", "--mode", "solo", *extra)

    def test_copies_into_empty_dir(self):
        r = self.start()
        self.assertEqual(r.returncode, 0, r.stderr)
        files = template_files()
        self.assertIn("CLAUDE.md", files)
        self.assertIn("ARCHITECTURE.svg", files)
        for rel in files:
            self.assertTrue((self.dir / rel).is_file(), rel)
            self.assertIn("created: " + rel, r.stdout)
            if rel.endswith((".md", ".dot", ".svg")):
                self.assertNotIn("{{", (self.dir / rel).read_text(encoding="utf-8"), rel)
        self.assertIn("Acme", (self.dir / "CLAUDE.md").read_text())
        self.assertIn("MODE: solo", (self.dir / "STATE.md").read_text())

    def test_ships_a_gitignore_with_worktrees_and_local_env(self):
        r = self.start()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("created: .gitignore", r.stdout)
        lines = (self.dir / ".gitignore").read_text().splitlines()
        self.assertIn(".worktrees/", lines)
        self.assertIn(".env.local", lines)

    def test_an_existing_gitignore_is_a_conflict_and_stays_untouched(self):
        (self.dir / ".gitignore").write_text("mine\n")
        r = self.start()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: .gitignore", r.stdout)
        self.assertEqual((self.dir / ".gitignore").read_text(), "mine\n")

    def test_refuses_when_claude_md_exists(self):
        (self.dir / "CLAUDE.md").write_text("mine")
        r = self.start()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: CLAUDE.md", r.stdout)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["CLAUDE.md"])
        self.assertEqual((self.dir / "CLAUDE.md").read_text(), "mine")

    def test_lists_every_conflict(self):
        (self.dir / "CLAUDE.md").write_text("a")
        (self.dir / "STATE.md").write_text("b")
        r = self.start()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: CLAUDE.md", r.stdout)
        self.assertIn("conflict: STATE.md", r.stdout)

    def test_dry_run_writes_nothing(self):
        r = self.start("--dry-run")
        self.assertEqual(r.returncode, 0)
        self.assertIn("would create: CLAUDE.md", r.stdout)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_missing_target_refused(self):
        r = run("--target", str(self.dir / "nope"), "--name", "A", "--mode", "solo")
        self.assertEqual(r.returncode, 1)

    def test_bad_mode_rejected(self):
        r = run("--target", str(self.dir), "--name", "A", "--mode", "crowd")
        self.assertNotEqual(r.returncode, 0)

    def test_date_is_today_iso(self):
        import datetime
        self.start()
        self.assertIn(datetime.date.today().isoformat(), (self.dir / "CLAUDE.md").read_text())

    def test_copied_diagram_passes_dot_check(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import dot_check
        finally:
            sys.path.pop(0)
        self.start()
        problems = dot_check.check([self.dir / "ARCHITECTURE.dot"])
        self.assertEqual(problems, [])

    def test_file_in_place_of_directory_is_conflict(self):
        (self.dir / "docs").write_text("x")
        r = self.start()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: docs", r.stdout)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["docs"])

    def test_step_4_7_folders_copied(self):
        r = self.start()
        self.assertEqual(r.returncode, 0, r.stderr)
        for folder in ("architecture", "data", "api", "design", "production"):
            readme = self.dir / "docs" / folder / "README.md"
            self.assertTrue(readme.is_file(), folder)
            self.assertLessEqual(len(readme.read_text().splitlines()), 10, folder)
        index = (self.dir / "docs/rules-index.md").read_text()
        for home in ("docs/architecture/", "docs/data/", "docs/api/", "docs/design/", "docs/production/LEAD-TIME.md"):
            self.assertRegex(index, r"\|[^|\n]+\| `" + home + r"` \|", home)

    def test_template_sizes(self):
        self.assertLessEqual(len((TEMPLATES / "CLAUDE.md").read_text().splitlines()), 150)
        self.assertLessEqual(len((TEMPLATES / "STATE.md").read_text().splitlines()), 60)

    def test_state_has_required_fields(self):
        lines = (TEMPLATES / "STATE.md").read_text().splitlines()
        found = [l.split(":")[0] for l in lines if l and l[0].isupper() and ":" in l]
        self.assertEqual(found, FIELDS)

    def test_claude_md_contents(self):
        t = (TEMPLATES / "CLAUDE.md").read_text()
        for needle in ["docs/rules-index.md", "take precedence", "PRODUCT.md", "GLOSSARY.md", "SPEC.md",
                       "Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓",
                       "Pavedline collects nothing. Every answer stays in your own repository.",
                       "{{PROJECT_NAME}}", "{{MODE}}", "{{DATE}}"]:
            self.assertIn(needle, t)

    def test_waiting_format_and_no_items(self):
        t = (TEMPLATES / "WAITING.md").read_text()
        self.assertIn("Fn · what · where/how · what it unblocks", t)
        self.assertFalse([l for l in t.splitlines() if l.startswith("- F")])


if __name__ == "__main__":
    unittest.main()
