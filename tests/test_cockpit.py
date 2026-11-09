import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "pavedline-cockpit"
FIX = ROOT / "tests" / "fixtures" / "cockpit"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def node_summary(files):
    """Run hooks/parse.mjs `summarize` under node on a dict of file texts."""
    script = (
        "import {summarize} from %r;"
        "import {readFileSync} from 'node:fs';const f=JSON.parse(readFileSync(0,'utf8'));"
        "console.log(JSON.stringify(summarize(f)));" % (PLUGIN / "hooks" / "parse.mjs").as_uri()
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(files),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class Manifest(unittest.TestCase):
    def test_plugin_json(self):
        p = load("plugins/pavedline-cockpit/.claude-plugin/plugin.json")
        base = load("plugins/pavedline/.claude-plugin/plugin.json")
        self.assertEqual(p["name"], "pavedline-cockpit")
        self.assertEqual(p["version"], "0.1.0")
        for k in ("author", "homepage", "repository", "license"):
            self.assertEqual(p[k], base[k], k)
        self.assertNotIn("dependencies", p)

    def test_hooks_json(self):
        h = load("plugins/pavedline-cockpit/hooks/hooks.json")
        self.assertEqual(h, {"modules": ["./register.js"]})
        self.assertTrue((PLUGIN / "hooks" / "register.js").is_file())

    def test_marketplace_entry(self):
        m = load(".claude-plugin/marketplace.json")
        e = [p for p in m["plugins"] if p["name"] == "pavedline-cockpit"]
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["source"], "./plugins/pavedline-cockpit")
        self.assertEqual(e[0]["version"], "0.1.0")

    def test_status_skill_and_sources(self):
        self.assertTrue((PLUGIN / "skills" / "status" / "SKILL.md").is_file())
        src = (PLUGIN / "SOURCES.md").read_text()
        self.assertIn("https://code.claude.com/docs/en/plugins/mods/reference.md", src)
        self.assertIn("2026-11-09", src)
        self.assertTrue((PLUGIN / "README.md").is_file())


class Independence(unittest.TestCase):
    def test_pavedline_never_mentions_the_cockpit(self):
        for f in (ROOT / "plugins" / "pavedline").rglob("*"):
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertNotIn("pavedline-cockpit", text, str(f))


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"])//.*$", r"\1", text)


class ReadOnly(unittest.TestCase):
    ALLOWED_IMPORTS = {"claude-code", "./parse.mjs"}
    ALLOWED_CALLS = {"fs.read", "fs.stat", "command.register", "ui.open", "ui.resolve", "session.root"}
    FORBIDDEN = (r"child_process", r"\bnet\b", r"\bhttps?\b", r"\bfetch\b", r"XMLHttpRequest",
                 r"WebSocket", r"\bwrite\w*", r"\bappend\w*", r"\beval\b", r"\bFunction\b",
                 r"\bspawn\b", r"\bexec\w*", r"\bprocess\b", r"\bstore\b", r"\bmcp\b")

    def sources(self):
        return [f for f in (PLUGIN / "hooks").iterdir()
                if f.suffix in (".js", ".mjs") and not f.name.endswith(".test.tsx")]

    def test_no_forbidden_identifiers(self):
        for f in self.sources():
            text = strip_comments(f.read_text())
            for bad in self.FORBIDDEN:
                self.assertIsNone(re.search(bad, text), f"{f.name}: {bad}")

    def test_imports_are_allow_listed_in_every_form(self):
        for f in self.sources():
            text = strip_comments(f.read_text())
            specs = re.findall(r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"]+)['"]""", text)
            for sp in specs:
                self.assertIn(sp, self.ALLOWED_IMPORTS, f"{f.name}: import {sp}")
            self.assertNotRegex(text, r"\b(import|require)\s*\(\s*[^'\"\s]", f.name)

    def test_only_allow_listed_engine_calls(self):
        for f in self.sources():
            text = strip_comments(f.read_text())
            for ns, m in re.findall(r"\$\.(\w+)\.(\w+)", text):
                self.assertIn(f"{ns}.{m}", self.ALLOWED_CALLS, f.name)
            self.assertNotRegex(text, r"\$\[|\$\.\w+\[", f.name)


@unittest.skipUnless(shutil.which("node"), "node not installed: parser tests skipped")
class Parsing(unittest.TestCase):
    def files(self, state="STATE.md"):
        return {
            "STATE.md": (FIX / state).read_text(),
            "WAITING.md": (FIX / "WAITING.md").read_text(),
            "handoff": {"a-items-api": (FIX / "handoff" / "a-items-api.md").read_text()},
        }

    def test_full_summary(self):
        lines = node_summary(self.files())
        text = "\n".join(lines)
        self.assertIn("STEP 7 — Build", text)
        self.assertIn("WAVE 2 (items and billing)", text)
        self.assertIn("NEXT review the open slice, then merge it", text)
        self.assertIn("SLICE a-items-api", text)
        self.assertIn("Gates: TDD ✓ · review pending", text)
        self.assertIn("WAITING 4 open", text)
        self.assertIn("F1 Log in to the registry", text)
        self.assertIn("F3 Add the signing key", text)
        self.assertNotIn("F4", text)

    def test_slice_on_following_line_and_no_handoff(self):
        f = self.files("STATE-multi.md")
        f["handoff"] = {}
        text = "\n".join(node_summary(f))
        self.assertIn("SLICE feature/items", text)
        self.assertNotIn("Gates:", text)

    def test_missing_files_one_line(self):
        self.assertEqual(node_summary({"STATE.md": None, "WAITING.md": None, "handoff": {}}),
                         ["no Pavedline project here"])

    def test_garbage_does_not_throw(self):
        lines = node_summary({"STATE.md": "\x00\x01 not a state file", "WAITING.md": "", "handoff": {}})
        self.assertIsInstance(lines, list)

    def run_js(self, expr):
        script = ("import * as m from %r;console.log(JSON.stringify(%s));"
                  % ((PLUGIN / "hooks" / "parse.mjs").as_uri(), expr))
        out = subprocess.run(["node", "--input-type=module", "-e", script],
                             capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_unsafe_branch_names_give_no_path(self):
        for b in ("../../etc/passwd", "/etc/passwd", "a/..", "a/./../b", "..", "a\\b", "x\u0000y", ""):
            self.assertEqual(self.run_js("m.handoffPaths(%s)" % json.dumps(b)), [], b)
        self.assertEqual(self.run_js("m.handoffPaths('feature/items')"),
                         ["handoff/feature/items.md", "handoff/feature-items.md"])

    def test_inside_guard_refuses_outside_and_prefix_tricks(self):
        self.assertTrue(self.run_js("m.isInside('/p/root','/p/root/handoff/a.md')"))
        for out in ("/etc/passwd", "/p/root2/x", "/p/root", "/p/root/../x", ""):
            self.assertFalse(self.run_js("m.isInside('/p/root',%s)" % json.dumps(out)), out)

    def test_project_only(self):
        self.assertTrue(self.run_js("m.isProject('STEP: 1\\nOWNER: x\\n')"))
        self.assertFalse(self.run_js("m.isProject('# my notes\\nSTEP: 1\\n')"))
        self.assertFalse(self.run_js("m.isProject(null)"))

    def test_lines_are_capped_and_clean(self):
        s = "STEP: " + "x" * 60_000 + "\nOWNER: o\nNEXT: a\x1b]8;;http://evil\x07link\x1b]8;;\x07 \x1b[2Jb\x9b31m\x00c\n"
        lines = node_summary({"STATE.md": s, "WAITING.md": None, "handoff": {}})
        for l in lines:
            self.assertLessEqual(len(l), 160)
            self.assertNotRegex(l, r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
        self.assertTrue(lines[0].endswith("\u2026"))
        nxt = [l for l in lines if l.startswith("NEXT")][0]
        self.assertEqual(nxt, "NEXT alink bc")

    def test_slice_none(self):
        s = "STEP: 1\nOWNER: o\nWAVE: none\nSLICES IN FLIGHT: none\nNEXT: x\n"
        text = "\n".join(node_summary({"STATE.md": s, "WAITING.md": None, "handoff": {}}))
        self.assertNotIn("SLICE ", text)
        self.assertNotIn("WAITING", text)


if __name__ == "__main__":
    unittest.main()
