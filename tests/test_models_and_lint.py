import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gen_agent_models as gen  # noqa: E402
import lint_skills as lint  # noqa: E402


def write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class ModelsTests(unittest.TestCase):
    def test_parse_rejects_haiku(self):
        with self.assertRaises(ValueError):
            gen.parse_models("builder: haiku\n")

    def test_parse_ok_with_comments(self):
        self.assertEqual(gen.parse_models("# c\n\nbuilder: sonnet\ndesigner: opus\n"),
                         {"builder": "sonnet", "designer": "opus"})

    def test_generator_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            models = write(d / "models.yaml", "researcher: sonnet\n")
            agent = write(d / "agents" / "researcher.md",
                          "---\nname: researcher\nmodel: opus\n---\nbody\n")
            before = agent.read_text()
            args = ["--models", str(models), "--agents-dir", str(d / "agents")]
            self.assertEqual(gen.main(args + ["--check"]), 1)
            self.assertEqual(agent.read_text(), before)
            self.assertEqual(gen.main(args), 0)
            self.assertEqual(agent.read_text(),
                             "---\nname: researcher\nmodel: sonnet\n---\nbody\n")
            self.assertEqual(gen.main(args + ["--check"]), 0)

    def test_generator_inserts_missing_model_line(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            models = write(d / "m.yaml", "builder: sonnet\n")
            agent = write(d / "agents" / "builder.md", "---\nname: builder\n---\nmodel: opus in body\n")
            gen.main(["--models", str(models), "--agents-dir", str(d / "agents")])
            self.assertEqual(agent.read_text(),
                             "---\nname: builder\nmodel: sonnet\n---\nmodel: opus in body\n")

    def test_real_repo_in_sync(self):
        self.assertEqual(gen.main(["--check"]), 0)

    def test_crlf_wrong_model_only_model_line_changes(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            models = write(d / "m.yaml", "builder: sonnet\n")
            agent = d / "agents" / "builder.md"
            agent.parent.mkdir()
            agent.write_bytes(b"---\r\nname: builder\r\nmodel: opus\r\n---\r\nbody\r\n")
            self.assertEqual(gen.main(["--models", str(models), "--agents-dir", str(d / "agents")]), 0)
            self.assertEqual(agent.read_bytes(),
                             b"---\r\nname: builder\r\nmodel: sonnet\r\n---\r\nbody\r\n")

    def test_crlf_correct_model_check_passes_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            models = write(d / "m.yaml", "builder: sonnet\n")
            agent = d / "agents" / "builder.md"
            agent.parent.mkdir()
            data = b"---\r\nname: builder\r\nmodel: sonnet\r\n---\r\nbody\r\n"
            agent.write_bytes(data)
            self.assertEqual(gen.main(["--check", "--models", str(models),
                                       "--agents-dir", str(d / "agents")]), 0)
            self.assertEqual(agent.read_bytes(), data)

    def test_parse_rejects_duplicate_role(self):
        with self.assertRaisesRegex(ValueError, "duplicate role: builder"):
            gen.parse_models("builder: sonnet\nbuilder: opus\n")

    def test_agent_without_policy_fails(self):
        for extra in ([], ["--check"]):
            with tempfile.TemporaryDirectory() as d:
                d = pathlib.Path(d)
                models = write(d / "m.yaml", "builder: sonnet\nghost: opus\n")
                write(d / "agents" / "builder.md", "---\nname: builder\nmodel: sonnet\n---\n")
                write(d / "agents" / "stray.md", "---\nname: stray\n---\n")
                self.assertEqual(gen.main(extra + ["--models", str(models),
                                                   "--agents-dir", str(d / "agents")]), 1)


class LintTests(unittest.TestCase):
    def skill(self, root, name, fm_name=None, desc="Does a thing.", extra="", body="# x\n"):
        fm_name = fm_name or name
        write(pathlib.Path(root) / name / "SKILL.md",
              f"---\nname: {fm_name}\ndescription: {desc}\n---\n{body}{extra}")

    def test_lint_passes_valid_skill(self):
        with tempfile.TemporaryDirectory() as d:
            self.skill(d, "good", extra="See [r](references/a.md)\n")
            write(pathlib.Path(d) / "good" / "references" / "a.md", "x")
            self.assertEqual(lint.check_skills(d), [])
            self.assertEqual(lint.main([d]), 0)

    def test_lint_name_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            self.skill(d, "good", fm_name="other")
            problems = lint.check_skills(d)
            self.assertTrue(any("name" in p for p in problems))
            self.assertEqual(lint.main([d]), 1)

    def test_lint_missing_reference(self):
        with tempfile.TemporaryDirectory() as d:
            self.skill(d, "good", extra="See [r](references/nope.md)\n")
            self.assertTrue(any("references/nope.md" in p for p in lint.check_skills(d)))

    def test_lint_long_description_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.skill(d, "long", desc="x" * 1025)
            self.skill(d, "empty", desc="")
            p = lint.check_skills(d)
            self.assertEqual(len([x for x in p if "description" in x]), 2)

    def test_lint_too_many_lines(self):
        with tempfile.TemporaryDirectory() as d:
            self.skill(d, "big", body="line\n" * 501)
            self.assertTrue(any("500" in p for p in lint.check_skills(d)))

    def test_lint_folded_description_and_missing_skill_md(self):
        with tempfile.TemporaryDirectory() as d:
            write(pathlib.Path(d) / "fold" / "SKILL.md",
                  "---\nname: fold\ndescription: >\n  first part\n  second part\n---\nbody\n")
            (pathlib.Path(d) / "nofile").mkdir()
            p = lint.check_skills(d)
            self.assertEqual(len(p), 1)
            self.assertIn("nofile", p[0])
            self.assertIn("SKILL.md", p[0])

    def test_lint_missing_dir_and_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(lint.main([d]), 0)
            self.assertEqual(lint.main([os.path.join(d, "absent")]), 1)


if __name__ == "__main__":
    unittest.main()
