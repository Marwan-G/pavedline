import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK = ROOT / "plugins/pavedline/stacks/nextjs-fastapi"
API = PACK / "files/services/api"
SKILL = ROOT / "plugins/pavedline/skills/fastapi-service"
UV = shutil.which("uv")


class Files(unittest.TestCase):
    def test_files_exist(self):
        for p in [
            PACK / "pack.yaml",
            PACK / "files/.gitignore",
            PACK / "files/scripts/rls_check.py",
            PACK / "files/scripts/contract_check.py",
            API / "pyproject.toml",
            API / "uv.lock",
            API / ".python-version",
            API / "Dockerfile",
            API / ".dockerignore",
            API / "alembic.ini",
            API / "db/roles.sql",
            API / "db/global_tables.txt",
            API / "app/main.py",
            API / "app/boot_check.py",
            API / "app/auth.py",
            API / "app/settings.py",
            API / "app/db/tenant.py",
            API / "app/services/idempotency.py",
            API / "migrations/env.py",
            API / "tests/conftest.py",
            API / "tests/leak_registry.py",
            API / "tests/test_tenant_leak.py",
            PACK / "example/docs/api/openapi.yaml",
            PACK / "example/services/api/app/routes/v1/items.py",
            PACK / "example/services/api/tests/test_items.py",
            SKILL / "SKILL.md",
            SKILL / "references/sources.md",
        ]:
            self.assertTrue(p.is_file(), str(p))

    def test_no_generated_files_are_tracked(self):
        git = shutil.which("git")
        if git is None:
            self.skipTest("skipped: git not on PATH")
        r = subprocess.run([git, "ls-files", "--cached", "--others", "--exclude-standard", str(PACK)],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        bad = (".venv/", "__pycache__/", ".pytest_cache/", ".ruff_cache/", ".pyright/", ".pyc")
        for line in r.stdout.splitlines():
            for b in bad:
                self.assertNotIn(b, line, line)


class Pins(unittest.TestCase):
    def test_exact_pins(self):
        text = (API / "pyproject.toml").read_text()
        if tomllib is None:
            self.skipTest("tomllib needs Python 3.11+")
        data = tomllib.loads(text)
        deps = list(data["project"]["dependencies"])
        for group in data.get("dependency-groups", {}).values():
            deps += [d for d in group if isinstance(d, str)]
        self.assertTrue(deps)
        for d in deps:
            self.assertRegex(d, r"^[A-Za-z0-9_.\-]+(\[[A-Za-z0-9_,\-]+\])?==\d[\w.]*$", d)

    def test_image_digests(self):
        text = (API / "Dockerfile").read_text()
        froms = re.findall(r"(?m)^FROM (\S+)", text)
        self.assertGreaterEqual(len(froms), 3)
        for f in froms:
            if f in ("build", "uv"):
                continue
            self.assertRegex(f, r"@sha256:[0-9a-f]{64}$", f)
        self.assertIn("app.boot_check", text)
        self.assertIn("USER ", text)

    def test_ruff_pyright_strict(self):
        text = (API / "pyproject.toml").read_text()
        self.assertIn('typeCheckingMode = "strict"', text)
        self.assertIn("[tool.ruff", text)
        self.assertIn("[tool.importlinter]", text)


class Skill(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text()

    def test_frontmatter_and_length(self):
        self.assertRegex(self.text, r"(?m)^name: fastapi-service$")
        self.assertLessEqual(len(self.text.splitlines()), 150)

    def test_float_money_rule(self):
        self.assertRegex(self.text, r"(?i)never\s+`?float`?")
        self.assertIn("rg -n", self.text)
        self.assertIn("float", self.text)

    def test_names_the_checks(self):
        for word in ("rls_check.py", "contract_check.py", "SET LOCAL", "Idempotency-Key", "leak_registry"):
            self.assertIn(word, self.text)

    def test_sources_has_pins_with_urls(self):
        src = (SKILL / "references/sources.md").read_text()
        for pin in ("fastapi", "pydantic", "sqlalchemy", "alembic", "ruff", "pyright", "import-linter"):
            self.assertRegex(src, r"(?i)`" + pin + r"(\[[a-z]+\])?==\d")
        self.assertIn("https://pypi.org/project/fastapi/", src)
        self.assertRegex(src, r"2026-11-09")


class Scripts(unittest.TestCase):
    def run_help(self, name):
        if UV is None:
            self.skipTest("skipped: uv not on PATH")
        with tempfile.TemporaryDirectory() as venv:  # never create a .venv inside the source tree
            env = dict(os.environ, UV_PROJECT_ENVIRONMENT=venv)
            r = subprocess.run(
                [UV, "run", "--frozen", "--no-dev", "--project", str(API), "python",
                 str(PACK / "files/scripts" / name), "--help"],
                capture_output=True, text=True, timeout=300, env=env,
            )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("usage", r.stdout.lower())

    def test_rls_check_help(self):
        self.run_help("rls_check.py")

    def test_contract_check_help(self):
        self.run_help("contract_check.py")


class PackYaml(unittest.TestCase):
    def test_api_entry(self):
        text = (PACK / "pack.yaml").read_text()
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError:
            yaml = None
        if yaml is not None:
            data = yaml.safe_load(text)
            api = data["surfaces"]["api"]
            self.assertIn("services/api", api["paths"])
            self.assertIn("pavedline-surface: api", " ".join(api["ci_markers"]))
            self.assertIn("fastapi-service", data["skills"])
            self.assertIn("uv", data["tools"])
        else:
            self.assertRegex(text, r"(?m)^surfaces:")
            self.assertIn("services/api", text)
            self.assertIn("# pavedline-surface: api", text)
            self.assertIn("fastapi-service", text)


if __name__ == "__main__":
    unittest.main()
