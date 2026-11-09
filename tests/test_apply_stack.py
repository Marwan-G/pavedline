import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/pavedline/scripts/apply_stack.py"
START = ROOT / "plugins/pavedline/scripts/start_project.py"
STACKS = ROOT / "plugins/pavedline/stacks"
TEMPLATES = ROOT / "plugins/pavedline/templates"
PACK = STACKS / "nextjs-fastapi"
ALL = "api,web,site,mobile"
JUNK = shutil.ignore_patterns(
    ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".import_linter_cache", ".next", "example"
)


def load_module():
    spec = importlib.util.spec_from_file_location("apply_stack", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def start_tree(path):
    r = subprocess.run(
        [sys.executable, str(START), "--target", str(path), "--name", "example", "--mode", "solo"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr


def tree(path):
    return sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file())


def texts(path):
    for rel in tree(path):
        data = (path / rel).read_bytes()
        if b"\0" in data:
            continue
        try:
            yield rel, data.decode("utf-8")
        except UnicodeDecodeError:
            continue


# Tokens that identify the three optional surfaces; a dropped surface must leave none of them behind.
DROPPED = {
    "site": ["apps/site", "@app/site", "ci-site.yml", "infra/k8s/apps/site", "lighthouserc", "www.localtest.me"],
    "mobile": ["apps/mobile", "@app/mobile", "ci-mobile.yml", "ci-mobile"],
    "web": ["apps/web", "@app/web", "ci-web.yml", "infra/k8s/apps/web", "playwright.cluster", "app.localtest.me"],
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name) / "product"
        self.dir.mkdir()
        start_tree(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self, surfaces=ALL, *extra, tenancy="multi", pack="nextjs-fastapi"):
        return run("--target", str(self.dir), "--pack", pack, "--surfaces", surfaces, "--tenancy", tenancy, *extra)

    def ok(self, *a, **k):
        r = self.apply(*a, **k)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def read(self, rel):
        return (self.dir / rel).read_text(encoding="utf-8")

    def assertAbsentTokens(self, dropped):
        for rel, text in texts(self.dir):
            # web_boundary_check.py is surface-neutral by design (it checks whichever of web and site exists)
            if rel in ("RUN.md", "ARCHITECTURE.dot", "ARCHITECTURE.svg", "scripts/web_boundary_check.py"):
                continue
            if rel.startswith(("docs/", "scripts/local-cluster/")):
                continue
            for surface in dropped:
                for tok in DROPPED[surface]:
                    self.assertNotIn(tok, text, f"{rel} mentions {tok} (surface {surface} was not chosen)")


class FullCopy(Base):
    def test_four_surfaces_multi(self):
        r = self.ok()
        for rel in [
            "services/api/app/main.py",
            "services/api/uv.lock",
            "apps/web/package.json",
            "apps/site/package.json",
            "apps/mobile/app.config.ts",
            "packages/api-client/package.json",
            "packages/tokens/package.json",
            "packages/glossary/package.json",
            "infra/k8s/apps/api/Chart.yaml",
            "infra/k8s/apps/postgres/Chart.yaml",
            "infra/k8s/apps/web/Chart.yaml",
            "infra/k8s/apps/site/Chart.yaml",
            ".github/workflows/ci-api.yml",
            ".github/workflows/ci-web.yml",
            ".github/workflows/ci-site.yml",
            ".github/workflows/ci-mobile.yml",
            ".github/workflows/image.yml",
            ".github/workflows/security.yml",
            ".github/workflows/e2e-local.yml",
            ".github/workflows/openapi-diff.yml",
            "scripts/rls_check.py",
            "scripts/contract_check.py",
            "scripts/local_secrets.sh",
            "scripts/web_boundary_check.py",
            "scripts/local-cluster/up.sh",
            "scripts/local-cluster/git-server/Dockerfile",
            "package.json",
            "pnpm-lock.yaml",
            "pnpm-workspace.yaml",
            ".npmrc",
            ".dockerignore",
            ".gitignore",
            "docs/architecture/STACK-SOURCES.md",
            "services/api/tests/test_tenant_leak.py",
        ]:
            self.assertTrue((self.dir / rel).is_file(), rel)
        self.assertIn("created: services/api/app/main.py", r.stdout)
        self.assertRegex(r.stdout, r"copied \d+, kept \d+")
        self.assertEqual(self.read("docs/architecture/STACK-SOURCES.md"), (PACK / "SOURCES.md").read_text())

    def test_no_junk_and_no_example(self):
        self.ok()
        for rel in tree(self.dir):
            parts = rel.split("/")
            for bad in (".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".import_linter_cache"):
                self.assertNotIn(bad, parts, rel)
            self.assertFalse(rel.endswith(".pyc"), rel)
        self.assertFalse((self.dir / "example").exists())
        # the pack's example/ (a starter-check overlay) never lands in a product
        example = PACK / "example"
        if example.is_dir():
            for p in example.rglob("*"):
                if p.is_file() and ".venv" not in p.parts and "node_modules" not in p.parts and "__pycache__" not in p.parts:
                    rel = p.relative_to(example)
                    if not (PACK / "files" / rel).exists():
                        self.assertFalse((self.dir / rel).exists(), rel)

    def test_run_md_gets_stack_section_once(self):
        self.ok()
        run_md = self.read("RUN.md")
        self.assertEqual(run_md.count("## Stack: nextjs-fastapi"), 1)
        self.assertIn("app.localtest.me", run_md)
        self.assertIn("www.localtest.me", run_md)
        self.assertIn("api.localtest.me", run_md)
        self.assertNotIn("pavedline-begin", run_md)
        self.assertNotIn("pavedline-end", run_md)
        # the product's own text above is untouched
        self.assertTrue(run_md.startswith("# Run"))
        self.assertLess(run_md.index("| Task | Command |"), run_md.index("## Stack: nextjs-fastapi"))

    def test_no_marker_lines_left_anywhere(self):
        self.ok()
        for rel, text in texts(self.dir):
            if rel.startswith("scripts/") and rel.endswith("apply_stack.py"):
                continue
            self.assertNotRegex(text, r"pavedline-(begin|end)", rel)

    def test_executable_bits(self):
        self.ok()
        for rel in [
            "scripts/local-cluster/up.sh",
            "scripts/local-cluster/down.sh",
            "scripts/local-cluster/push.sh",
            "scripts/local-cluster/verify.sh",
            "scripts/local_secrets.sh",
        ]:
            self.assertTrue(os.access(self.dir / rel, os.X_OK), rel)
        self.assertFalse(os.access(self.dir / "package.json", os.X_OK))
        self.assertFalse(os.access(self.dir / "infra/k8s/apps/api/values.yaml", os.X_OK))

    def test_application_set_placeholders_are_kept_for_the_deploy_script(self):
        self.ok()
        text = self.read("infra/k8s/applicationsets/apps.yaml")
        self.assertIn("{{ENVIRONMENT}}", text)
        self.assertIn("{{REPO_URL}}", text)


class DroppedSurfaces(Base):
    def test_web_and_api_only(self):
        self.ok("web,api")
        for rel in [
            "apps/web/package.json",
            "packages/api-client/package.json",
            "infra/k8s/apps/web/Chart.yaml",
            "infra/k8s/apps/api/Chart.yaml",
            "infra/k8s/apps/postgres/Chart.yaml",
            ".github/workflows/ci-web.yml",
            ".github/workflows/ci-api.yml",
            "scripts/web_boundary_check.py",
        ]:
            self.assertTrue((self.dir / rel).is_file(), rel)
        for rel in tree(self.dir):
            self.assertFalse(rel.startswith(("apps/site", "apps/mobile", "infra/k8s/apps/site")), rel)
        for rel in (".github/workflows/ci-site.yml", ".github/workflows/ci-mobile.yml"):
            self.assertFalse((self.dir / rel).exists(), rel)
        self.assertAbsentTokens(["site", "mobile"])
        # the lockfile lists no importer for a dropped surface
        lock = self.read("pnpm-lock.yaml")
        self.assertNotIn("apps/site", lock)
        self.assertNotIn("apps/mobile", lock)
        self.assertIn("  apps/web:", lock)
        # the API chart admits the web app when web is chosen
        self.assertIn("kubernetes.io/metadata.name: web", self.read("infra/k8s/apps/api/values.yaml"))
        run_md = self.read("RUN.md")
        self.assertNotIn("www.localtest.me", run_md)
        self.assertNotIn("@app/site", run_md)
        self.assertNotIn("@app/mobile", run_md)
        # mobile-only install settings are not carried either
        self.assertNotIn("allowBuilds", self.read("pnpm-workspace.yaml"))
        self.assertNotIn("apps/mobile", self.read(".dockerignore"))

    def test_api_alone(self):
        self.ok("api")
        files = tree(self.dir)
        self.assertIn("services/api/app/main.py", files)
        self.assertIn("infra/k8s/apps/api/Chart.yaml", files)
        self.assertIn("infra/k8s/apps/postgres/Chart.yaml", files)
        self.assertIn(".github/workflows/ci-api.yml", files)
        self.assertIn(".github/workflows/image.yml", files)
        self.assertIn("scripts/rls_check.py", files)
        self.assertIn("scripts/contract_check.py", files)
        self.assertIn(".env.local.example", files)
        for rel in files:
            self.assertFalse(rel.startswith(("apps/", "packages/", "infra/k8s/apps/web", "infra/k8s/apps/site")), rel)
        for rel in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "biome.json", ".npmrc", ".node-version",
                    "scripts/web_boundary_check.py", ".github/workflows/ci-web.yml"):
            self.assertNotIn(rel, files)
        self.assertAbsentTokens(["site", "mobile", "web"])
        # without web the API chart no longer admits the web namespace
        self.assertNotIn("metadata.name: web", self.read("infra/k8s/apps/api/values.yaml"))
        run_md = self.read("RUN.md")
        self.assertIn("api.localtest.me", run_md)
        self.assertNotIn("pnpm", run_md)

    def test_package_json_scripts_follow_the_copied_packages(self):
        self.ok("api,site")
        scripts = json.loads(self.read("package.json"))["scripts"]
        self.assertNotIn("e2e", scripts)
        self.assertEqual(scripts["check:generated"], "pnpm --filter @app/tokens check")
        self.assertIn("check:boundary", scripts)
        self.assertIn("lint", scripts)

    def test_package_json_without_web_or_site(self):
        self.ok("api,mobile")
        scripts = json.loads(self.read("package.json"))["scripts"]
        self.assertNotIn("check:boundary", scripts)
        self.assertNotIn("check:generated", scripts)
        self.assertNotIn("e2e", scripts)
        self.assertIn("lint", scripts)

    def test_mobile_only_surface_keeps_the_mobile_lock_importer(self):
        self.ok("mobile")
        lock = self.read("pnpm-lock.yaml")
        self.assertIn("  apps/mobile:", lock)
        self.assertNotIn("  apps/web:", lock)
        self.assertIn("allowBuilds", self.read("pnpm-workspace.yaml"))
        self.assertIn("apps/mobile", self.read(".dockerignore"))


class Tenancy(Base):
    def test_single_drops_rls_and_leak_fixture(self):
        self.ok("api", tenancy="single")
        self.assertFalse((self.dir / "scripts/rls_check.py").exists())
        self.assertFalse((self.dir / "services/api/tests/test_tenant_leak.py").exists())
        self.assertFalse((self.dir / "services/api/tests/test_rls_check.py").exists())
        # the registry the shared `world` fixture seeds stays, or the other tests would not import
        self.assertTrue((self.dir / "services/api/tests/leak_registry.py").is_file())
        self.assertTrue((self.dir / "services/api/tests/test_tenant_scope.py").is_file())
        ci = self.read(".github/workflows/ci-api.yml")
        self.assertIn("PAVEDLINE_TENANCY: single", ci)
        self.assertNotIn("PAVEDLINE_TENANCY: multi", ci)
        run_md = self.read("RUN.md")
        self.assertEqual(run_md.count("not applicable (decision 0002)"), 2)
        self.assertNotIn("rls_check.py", run_md)
        self.assertIn("contract_check.py", run_md)

    def test_multi_keeps_them(self):
        self.ok("api")
        self.assertTrue((self.dir / "scripts/rls_check.py").is_file())
        self.assertTrue((self.dir / "services/api/tests/test_tenant_leak.py").is_file())
        self.assertIn("PAVEDLINE_TENANCY: multi", self.read(".github/workflows/ci-api.yml"))
        run_md = self.read("RUN.md")
        self.assertIn("rls_check.py", run_md)
        self.assertNotIn("not applicable", run_md)

    def test_tenancy_defaults_to_multi(self):
        r = run("--target", str(self.dir), "--pack", "nextjs-fastapi", "--surfaces", "api")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.dir / "scripts/rls_check.py").is_file())


class NeverOverwrites(Base):
    def test_clash_prints_conflict_and_writes_nothing(self):
        (self.dir / "services/api/app").mkdir(parents=True)
        (self.dir / "services/api/app/main.py").write_text("mine")
        before = tree(self.dir)
        r = self.apply()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: services/api/app/main.py", r.stdout)
        self.assertEqual(tree(self.dir), before)
        self.assertEqual(self.read("services/api/app/main.py"), "mine")
        self.assertNotIn("## Stack", self.read("RUN.md"))

    def test_lists_every_conflict(self):
        (self.dir / "package.json").write_text("{}")
        (self.dir / "biome.json").write_text("{}")
        r = self.apply()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: package.json", r.stdout)
        self.assertIn("conflict: biome.json", r.stdout)

    def test_a_file_where_a_folder_is_needed_is_a_conflict(self):
        (self.dir / "services").write_text("a file")
        r = self.apply("api")
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: services/api/", r.stdout)

    def test_rerun_on_an_applied_tree_conflicts(self):
        self.ok()
        before = {rel: (self.dir / rel).read_bytes() for rel in tree(self.dir)}
        r = self.apply()
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: services/api/app/main.py", r.stdout)
        self.assertEqual({rel: (self.dir / rel).read_bytes() for rel in tree(self.dir)}, before)

    def test_existing_gitignore_keeps_its_lines_and_gains_the_packs_missing_ones(self):
        (self.dir / ".gitignore").write_text("mine\n.worktrees/\n")
        r = self.ok("api")
        text = self.read(".gitignore")
        self.assertTrue(text.startswith("mine\n.worktrees/\n"))
        self.assertEqual(text.count(".worktrees/"), 1)
        self.assertIn(".venv/", text)
        self.assertIn("node_modules/", text)
        self.assertIn("appended: .gitignore", r.stdout)
        self.assertNotIn("kept: .gitignore", r.stdout)

    def test_gitignore_that_already_has_every_line_is_left_alone(self):
        (self.dir / ".gitignore").write_text((PACK / "files/.gitignore").read_text())
        before = self.read(".gitignore")
        r = self.ok("api")
        self.assertEqual(self.read(".gitignore"), before)
        self.assertNotIn(".gitignore", r.stdout.replace("STACK-SOURCES", ""))

    def test_gitignore_from_start_project_gets_the_stack_lines(self):
        r = self.ok("api")
        text = self.read(".gitignore")
        self.assertIn(".worktrees/", text)
        self.assertIn(".env.local", text)
        self.assertIn(".venv/", text)
        self.assertIn("appended: .gitignore", r.stdout)

    def test_dry_run_reports_the_gitignore_append_and_writes_nothing(self):
        (self.dir / ".gitignore").write_text("mine\n")
        r = self.apply("api", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would append: .gitignore", r.stdout)
        self.assertEqual(self.read(".gitignore"), "mine\n")

    def test_dry_run_writes_nothing(self):
        before = tree(self.dir)
        run_md = self.read("RUN.md")
        r = self.apply(ALL, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(tree(self.dir), before)
        self.assertEqual(self.read("RUN.md"), run_md)
        self.assertIn("would create: services/api/app/main.py", r.stdout)
        self.assertIn("would append: RUN.md", r.stdout)
        self.assertNotIn("created:", r.stdout)

    def test_dry_run_still_reports_conflicts(self):
        (self.dir / "package.json").write_text("{}")
        r = self.apply(ALL, "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflict: package.json", r.stdout)

    def test_missing_target(self):
        r = run("--target", str(self.dir / "nope"), "--pack", "nextjs-fastapi", "--surfaces", "api")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not exist", r.stderr)


class NeutralTemplates(Base):
    def test_v01_product_gets_the_neutral_templates(self):
        for rel in ("infra", ".github", "scripts"):
            shutil.rmtree(self.dir / rel)
        for rel in ("renovate.json", ".sanitize-denylist"):
            (self.dir / rel).unlink()
        r = self.ok("api")
        for rel in (
            "infra/helm/base-chart/Chart.yaml",
            "infra/k8s/applicationsets/apps.yaml",
            "infra/k8s/addons/gateway/gateway.yaml",
            ".github/workflows/records.yml",
            ".github/workflows/renovate.yml",
            ".github/CODEOWNERS",
            "scripts/dot_check.py",
            "scripts/sanitize_scan.py",
            "renovate.json",
            ".sanitize-denylist",
        ):
            self.assertTrue((self.dir / rel).is_file(), rel)
            self.assertEqual((self.dir / rel).read_bytes(), (TEMPLATES / rel).read_bytes(), rel)
            self.assertIn("created: " + rel, r.stdout)

    def test_fresh_start_tree_templates_are_skipped_silently(self):
        r = self.ok("api")
        self.assertNotIn("scripts/dot_check.py", r.stdout)
        self.assertNotIn("kept:", r.stdout)

    def test_an_edited_neutral_file_is_kept_not_a_conflict(self):
        (self.dir / "scripts/dot_check.py").write_text("# edited by the product\n")
        r = self.ok("api")
        self.assertIn("kept: scripts/dot_check.py", r.stdout)
        self.assertEqual(self.read("scripts/dot_check.py"), "# edited by the product\n")

    def test_summary_counts(self):
        (self.dir / "scripts/dot_check.py").write_text("x\n")
        r = self.ok("api")
        m = re.search(r"copied (\d+), kept (\d+)", r.stdout)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "1")
        self.assertEqual(int(m.group(1)), r.stdout.count("created: ") + r.stdout.count("appended: .gitignore"))


class Renames(Base):
    def test_name_renames_the_mobile_app(self):
        r = self.ok("api,mobile", "--name", "my-shop")
        cfg = self.read("apps/mobile/app.config.ts")
        self.assertIn("name: 'My Shop'", cfg)
        self.assertIn("slug: 'my-shop'", cfg)
        self.assertIn("bundleIdentifier: 'com.myshop.app'", cfg)
        self.assertIn("package: 'com.myshop.app'", cfg)
        self.assertNotIn("Example", cfg)
        self.assertNotIn("com.example.app", cfg)
        self.assertNotIn("to fill: apps/mobile/app.config.ts", r.stdout)

    def test_without_name_the_placeholder_is_listed(self):
        r = self.ok("api,mobile")
        self.assertIn("to fill: apps/mobile/app.config.ts:", r.stdout)
        self.assertIn("com.example.app", self.read("apps/mobile/app.config.ts"))

    def test_github_repo_fills_owner_and_images(self):
        r = self.ok("api,web", "--github-repo", "Acme/Widgets")
        self.assertIn("repository: ghcr.io/acme/widgets/web", self.read("infra/k8s/apps/web/values-staging.yaml"))
        self.assertIn("ghcr.io/acme/widgets/api", self.read("infra/k8s/apps/api/values-production.yaml"))
        owners = self.read(".github/CODEOWNERS")
        self.assertIn("* @Acme", owners)
        self.assertNotIn("@OWNER", owners)
        self.assertNotIn("ghcr.io/OWNER/REPO", "".join(t for rel, t in texts(self.dir) if rel.startswith("infra/k8s/apps/")))
        self.assertNotRegex(r.stdout, r"to fill: .*OWNER")

    def test_without_github_repo_owner_is_listed(self):
        r = self.ok("api,web")
        self.assertRegex(r.stdout, r"to fill: infra/k8s/apps/web/values-staging.yaml: .*OWNER/REPO")
        self.assertRegex(r.stdout, r"to fill: infra/k8s/apps/web/values-production.yaml: .*example\.com")
        self.assertRegex(r.stdout, r"to fill: \.github/CODEOWNERS: .*@OWNER")
        self.assertIn("ghcr.io/OWNER/REPO/web", self.read("infra/k8s/apps/web/values-staging.yaml"))

    def test_edited_codeowners_is_never_rewritten(self):
        (self.dir / ".github/CODEOWNERS").write_text("* @me\n")
        r = self.ok("api", "--github-repo", "acme/widgets")
        self.assertEqual(self.read(".github/CODEOWNERS"), "* @me\n")
        self.assertIn("kept: .github/CODEOWNERS", r.stdout)

    def test_bad_inputs_exit_2(self):
        for args in (
            ["--surfaces", "api,bogus"],
            ["--surfaces", ""],
            ["--surfaces", "api", "--name", "Bad_Name"],
            ["--surfaces", "api", "--name", "-bad"],
            ["--surfaces", "api", "--github-repo", "no-slash"],
            ["--surfaces", "api", "--pack", "nope"],
            ["--surfaces", "api", "--tenancy", "both"],
        ):
            base = ["--target", str(self.dir)]
            if "--pack" not in args:
                base += ["--pack", "nextjs-fastapi"]
            r = run(*base, *args)
            self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
        self.assertEqual([p for p in tree(self.dir) if p.startswith("services/")], [])


class FixtureFiles(unittest.TestCase):
    """Task 9 adds deploy_local.sh, release_check.py and local-deploy.json to the pack; test the handling on a copy."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        cls.stacks = root / "stacks"
        shutil.copytree(PACK, cls.stacks / "nextjs-fastapi", ignore=JUNK)
        files = cls.stacks / "nextjs-fastapi/files"
        (files / "scripts/deploy_local.sh").write_text("#!/usr/bin/env bash\necho deploy\n")
        (files / "scripts/deploy_local.sh").chmod(0o755)
        (files / "scripts/release_check.py").write_text("print('release')\n")
        (files / "infra").mkdir(exist_ok=True)
        (files / "infra/local-deploy.json").write_text(
            json.dumps(
                {
                    "apps": [
                        {"name": "postgres", "surface": "postgres", "namespace": "postgres"},
                        {"name": "api", "surface": "api", "host": "api.localtest.me"},
                        {"name": "web", "surface": "web", "host": "app.localtest.me"},
                        {"name": "site", "surface": "site", "host": "www.localtest.me"},
                    ],
                    "registry": "localhost:5001",
                },
                indent=2,
            )
            + "\n"
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.t.name)
        start_tree(self.dir)

    def tearDown(self):
        self.t.cleanup()

    def apply(self, surfaces):
        return run(
            "--target", str(self.dir), "--pack", "nextjs-fastapi", "--surfaces", surfaces, "--stacks-dir", str(self.stacks)
        )

    def test_deploy_files_are_copied_with_any_surface(self):
        r = self.apply("api")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.access(self.dir / "scripts/deploy_local.sh", os.X_OK))
        self.assertTrue((self.dir / "scripts/release_check.py").is_file())
        r2 = tempfile.TemporaryDirectory()
        try:
            d2 = pathlib.Path(r2.name)
            start_tree(d2)
            r = run("--target", str(d2), "--pack", "nextjs-fastapi", "--surfaces", "mobile", "--stacks-dir", str(self.stacks))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((d2 / "scripts/deploy_local.sh").is_file())
            self.assertTrue((d2 / "scripts/release_check.py").is_file())
        finally:
            r2.cleanup()

    def test_local_deploy_json_is_filtered_by_surface(self):
        r = self.apply("api,web")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.dir / "infra/local-deploy.json").read_text())
        self.assertEqual([a["name"] for a in data["apps"]], ["postgres", "api", "web"])
        self.assertEqual(data["registry"], "localhost:5001")
        text = (self.dir / "infra/local-deploy.json").read_text()
        self.assertNotIn("www.localtest.me", text)
        # every entry has a chart folder in the product
        for entry in data["apps"]:
            self.assertTrue((self.dir / "infra/k8s/apps" / entry["name"] / "Chart.yaml").is_file(), entry)

    def test_postgres_entry_needs_api(self):
        r = self.apply("web,site")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.dir / "infra/local-deploy.json").read_text())
        self.assertEqual([a["name"] for a in data["apps"]], ["web", "site"])

    def test_absent_files_are_skipped_without_error(self):
        r = run("--target", str(self.dir), "--pack", "nextjs-fastapi", "--surfaces", "api", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        # the real pack may or may not carry them yet; either way the run succeeded and wrote nothing
        self.assertFalse((self.dir / "scripts/deploy_local.sh").exists())


class Units(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_pack_yaml_parses(self):
        pack = self.mod.parse_pack((PACK / "pack.yaml").read_text())
        self.assertEqual(sorted(pack["surfaces"]), ["api", "mobile", "site", "web"])
        self.assertIn("services/api", pack["surfaces"]["api"]["paths"])
        self.assertEqual(pack["surfaces"]["mobile"].get("infra", []), [])
        self.assertEqual(pack["surfaces"]["web"]["ci_markers"], ["# pavedline-surface: web"])
        self.assertEqual(pack["shared"]["needed_by"], ["web", "site", "mobile"])
        self.assertIn(".gitignore", pack["common"]["paths"])
        self.assertEqual(pack["run_fragment"], "RUN.stack.md")

    def test_marker_blocks(self):
        text = "a\n# pavedline-begin: web, site\nb\n# pavedline-end\nc\n<!-- pavedline-begin: mobile -->\nd\n<!-- pavedline-end -->\n"
        self.assertEqual(self.mod.apply_markers(text, {"web"}), "a\nb\nc\n")
        self.assertEqual(self.mod.apply_markers(text, {"mobile"}), "a\nc\nd\n")
        self.assertEqual(self.mod.apply_markers(text, set()), "a\nc\n")

    def test_unterminated_marker_is_an_error(self):
        with self.assertRaises(ValueError):
            self.mod.apply_markers("# pavedline-begin: web\nx\n", {"web"})
        with self.assertRaises(ValueError):
            self.mod.apply_markers("# pavedline-end\n", {"web"})

    def test_local_deploy_filter_variants(self):
        f = self.mod.filter_local_deploy
        self.assertEqual(
            f({"apps": [{"surface": "web"}, {"surface": ["web", "site"]}, {"x": 1}]}, {"site"}),
            {"apps": [{"surface": ["web", "site"]}, {"x": 1}]},
        )
        self.assertEqual(
            f({"apps": {"a": {"surface": "api"}, "b": {"surface": "web"}}}, {"web"}),
            {"apps": {"b": {"surface": "web"}}},
        )

    def test_dns_label(self):
        self.assertTrue(self.mod.valid_slug("my-shop"))
        self.assertTrue(self.mod.valid_slug("a"))
        for bad in ("", "-a", "a-", "A", "a_b", "a" * 64):
            self.assertFalse(self.mod.valid_slug(bad), bad)


class NeutralScriptsAreNotLinted(unittest.TestCase):
    def test_api_lint_and_types_skip_the_neutral_scripts(self):
        """services/api lints ../../scripts; the record checkers copied there must not be part of it."""
        text = (PACK / "files/services/api/pyproject.toml").read_text()
        ruff = text.split("[tool.ruff]", 1)[1].split("[tool.ruff.lint]", 1)[0]
        pyright = text.split("[tool.pyright]", 1)[1].split("[tool.importlinter]", 1)[0]
        neutral = sorted(p.name for p in (TEMPLATES / "scripts").glob("*.py")) + ["release_check.py", "post_deploy_check.py"]
        for name in neutral:
            ref = "../../scripts/" + name
            self.assertIn(ref, ruff, name)
            self.assertIn(ref, pyright, name)



class FixRound1(Base):
    def test_trailing_newline_and_dot_names_are_rejected(self):
        for args in (
            ["--name", "ab\n"],
            ["--name", "ab\x01"],
            ["--github-repo", "o/r\n"],
            ["--github-repo", "a/.."],
            ["--github-repo", "a/."],
            ["--github-repo", "../r"],
        ):
            r = run("--target", str(self.dir), "--pack", "nextjs-fastapi", "--surfaces", "api", *args)
            self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
        self.assertFalse((self.dir / "services").exists())

    def test_symlinked_directories_are_conflicts_and_nothing_leaks(self):
        outside = pathlib.Path(tempfile.mkdtemp(dir=self.tmp.name))
        for name in ("infra", "scripts"):
            shutil.rmtree(self.dir / name)
            (self.dir / name).symlink_to(outside, target_is_directory=True)
        r = self.apply("api")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"conflict: (infra|scripts)/")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.dir / "services").exists())

    def test_symlinked_services_folder_is_a_conflict(self):
        outside = pathlib.Path(tempfile.mkdtemp(dir=self.tmp.name))
        (self.dir / "services").symlink_to(outside, target_is_directory=True)
        r = self.apply("api")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(list(outside.iterdir()), [])


class FixRound1Pack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.stacks = root / "stacks"
        shutil.copytree(PACK, self.stacks / "nextjs-fastapi", ignore=JUNK)
        self.files = self.stacks / "nextjs-fastapi/files"
        self.dir = root / "product"
        self.dir.mkdir()
        start_tree(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self, surfaces="api"):
        return run("--target", str(self.dir), "--pack", "nextjs-fastapi", "--surfaces", surfaces,
                   "--stacks-dir", str(self.stacks))

    def test_deploy_paths_come_from_pack_yaml_and_must_exist(self):
        (self.files / "scripts/release_check.py").unlink()
        r = self.apply()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("scripts/release_check.py", r.stderr)
        self.assertFalse((self.dir / "services").exists())

    def test_deploy_block_drives_the_list(self):
        yml = self.stacks / "nextjs-fastapi/pack.yaml"
        text = yml.read_text().replace("    - scripts/post_deploy_check.py\n", "")
        yml.write_text(text)
        r = self.apply()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.dir / "scripts/post_deploy_check.py").exists())
        self.assertTrue((self.dir / "scripts/release_check.py").is_file())

    def test_marker_naming_an_unknown_surface_is_an_error(self):
        f = self.files / "pnpm-workspace.yaml"
        f.write_text(f.read_text() + "# pavedline-begin: nonesuch\nx: 1\n# pavedline-end\n")
        r = self.apply("web")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("nonesuch", r.stderr)

    def test_lock_is_pruned_to_what_the_kept_importers_reach(self):
        r = self.apply("site")
        self.assertEqual(r.returncode, 0, r.stderr)
        lock = (self.dir / "pnpm-lock.yaml").read_text()
        self.assertNotIn("expo@", lock)
        self.assertNotIn("react-native@", lock)
        self.assertIn("next@", lock)
        full = (PACK / "files/pnpm-lock.yaml").read_text()
        self.assertLess(len(lock), len(full) // 2)


class FrozenInstall(unittest.TestCase):
    def test_pruned_lock_installs_frozen(self):
        npx = shutil.which("npx")
        if not npx:
            self.skipTest("skipped: npx not on PATH")
        for surfaces in ("site", "web,api", "mobile,api"):
            with self.subTest(surfaces=surfaces):
                with tempfile.TemporaryDirectory() as d:
                    d = pathlib.Path(d)
                    start_tree(d)
                    r = run("--target", str(d), "--pack", "nextjs-fastapi", "--surfaces", surfaces)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    i = subprocess.run(
                        [npx, "--yes", "pnpm@11.28.8", "install", "--frozen-lockfile", "--ignore-scripts"],
                        cwd=d, capture_output=True, text=True, timeout=600)
                    self.assertEqual(i.returncode, 0, i.stdout[-800:] + i.stderr[-800:])


class StaticChecksOnTheCopiedTree(Base):
    def test_boundary_check_passes_on_the_copied_tree(self):
        self.ok()
        r = subprocess.run(
            [sys.executable, "scripts/web_boundary_check.py"], cwd=self.dir, capture_output=True, text=True
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_chart_renders_in_the_copied_tree(self):
        helm = shutil.which("helm")
        if not helm:
            self.skipTest("skipped: helm not on PATH")
        for surfaces in (ALL, "api"):
            with self.subTest(surfaces=surfaces):
                d = pathlib.Path(tempfile.mkdtemp(dir=self.tmp.name))
                start_tree(d)
                r = run("--target", str(d), "--pack", "nextjs-fastapi", "--surfaces", surfaces)
                self.assertEqual(r.returncode, 0, r.stderr)
                charts = sorted(p.parent for p in (d / "infra/k8s/apps").glob("*/Chart.yaml"))
                self.assertTrue(charts)
                for chart in charts:
                    if "dependencies" in (chart / "Chart.yaml").read_text():
                        u = subprocess.run([helm, "dependency", "update", str(chart)], capture_output=True, text=True)
                        self.assertEqual(u.returncode, 0, u.stderr)
                    t = subprocess.run(
                        [helm, "template", chart.name, str(chart), "-f", str(chart / "values-local.yaml")],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(t.returncode, 0, chart.as_posix() + t.stderr)
                    if chart.name == "api" and surfaces == "api":
                        self.assertNotIn("metadata.name: web", t.stdout)


if __name__ == "__main__":
    unittest.main()


class PostgresMajor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.pack = load_module().parse_pack((PACK / "pack.yaml").read_text())["postgres"]

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self, *extra):
        return run("--target", str(self.dir), "--pack", "nextjs-fastapi", "--surfaces", "api", "--name", "example", *extra)

    def image_line(self):
        text = (self.dir / "infra/k8s/apps/postgres/values.yaml").read_text()
        return re.search(r"(?m)^image: (.+)$", text).group(1)

    def test_pack_lists_its_pinned_majors_by_digest(self):
        self.assertEqual(str(self.pack["default_major"]), "16")
        self.assertEqual(sorted(self.pack["majors"]), ["16", "18"])
        for major, pins in self.pack["majors"].items():
            self.assertRegex(pins["test"], r"^postgres:%s\.\d+@sha256:[0-9a-f]{64}$" % major)
            image = pins["cluster"]
            self.assertRegex(image, r"^ghcr\.io/cloudnative-pg/postgresql:%s\.\d+-\d{12}-standard-trixie@sha256:[0-9a-f]{64}$" % major)

    def test_default_writes_the_default_majors_image(self):
        r = self.apply()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.image_line(), self.pack["majors"]["16"]["cluster"])

    def test_major_18_rewrites_the_image_line(self):
        r = self.apply("--postgres-major", "18")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.image_line(), self.pack["majors"]["18"]["cluster"])
        self.assertEqual(
            (self.dir / "infra/k8s/apps/postgres/values.yaml").read_text().count("image: ghcr.io/cloudnative-pg/postgresql"), 1
        )

    def ci_image(self):
        text = (self.dir / ".github/workflows/ci-api.yml").read_text()
        return re.findall(r"(?m)^        image: (postgres:\S+)$", text)

    def test_ci_test_image_follows_the_major(self):
        self.assertEqual(self.apply("--postgres-major", "18").returncode, 0)
        self.assertEqual(self.ci_image(), [self.pack["majors"]["18"]["test"]])
        self.assertIn(":18.", self.image_line())

    def test_ci_test_image_is_the_packs_own_with_the_default(self):
        self.assertEqual(self.apply().returncode, 0)
        self.assertEqual(self.ci_image(), [self.pack["majors"]["16"]["test"]])
        packed = (PACK / "files/.github/workflows/ci-api.yml").read_text()
        self.assertIn(self.pack["majors"]["16"]["test"], packed)

    def test_a_file_without_the_image_line_is_an_error_not_a_no_op(self):
        mod = load_module()
        with self.assertRaises(mod.UsageError) as cm:
            mod.sub_once(r"(?m)^image: .*$", "image: x", "cluster:\n  instances: 1\n", "infra/k8s/apps/postgres/values.yaml")
        self.assertIn("no Postgres image line", str(cm.exception))
        self.assertEqual(mod.sub_once(r"(?m)^image: .*$", "image: x", "a: 1\nimage: y\n", "v"), "a: 1\nimage: x\n")

    def test_unlisted_major_exits_1_and_writes_nothing(self):
        r = self.apply("--postgres-major", "17")
        self.assertEqual(r.returncode, 1)
        self.assertIn("postgres major 17 not pinned in this pack", r.stderr + r.stdout)
        self.assertEqual(tree(self.dir), [])

    def test_the_step_6_skill_names_the_comparison(self):
        t = (ROOT / "plugins/pavedline/skills/system-architecture/SKILL.md").read_text()
        self.assertIn("--postgres-major", t)
        self.assertIn("0006", t)
        self.assertIn("SYSTEM-DESIGN.md", t)
        self.assertRegex(t, r"(?i)stop[^\n]*(mismatch|differs|not pinned)")

    def test_pooler_image_is_a_digest_pinned_value_on_the_pgbouncer_container(self):
        base = PACK / "files/infra/k8s/apps/postgres"
        values = (base / "values.yaml").read_text()
        self.assertRegex(values, r"(?m)^  image: ghcr\.io/cloudnative-pg/pgbouncer:\d+\.\d+\.\d+-\d{12}-trixie@sha256:[0-9a-f]{64}$")
        tpl = (base / "templates/pooler.yaml").read_text()
        self.assertIn("template:", tpl)
        self.assertIn("name: pgbouncer", tpl)
        self.assertIn("image: {{ $p.image }}", tpl)
        self.assertLess(tpl.index("name: pgbouncer"), tpl.index("image: {{ $p.image }}"))

    def test_quality_gates_runs_gitleaks_before_the_push(self):
        t = (ROOT / "plugins/pavedline/skills/quality-gates/SKILL.md").read_text()
        self.assertIn("gitleaks", t)
        self.assertRegex(t, r"(?i)before (every|each|the) push|pre-push")
        self.assertIn("git archive", t)
        self.assertIn("$HOME", t)
