import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PACK = PLUGIN / "stacks/nextjs-fastapi"
FILES = PACK / "files"
EXAMPLE = PACK / "example"
BASE = PLUGIN / "templates/infra/helm/base-chart"
CHECKOV = PLUGIN / "templates/infra/helm/.checkov.yaml"
BOUNDARY = FILES / "scripts/web_boundary_check.py"
HELM = shutil.which("helm")
ENVS = ["local", "staging", "production"]
APPS = {"web": ("web", "app.localtest.me"), "site": ("site", "www.localtest.me")}

PACKAGE_JSONS = [
    "package.json", "apps/web/package.json", "apps/site/package.json", "packages/api-client/package.json",
    "packages/tokens/package.json", "packages/glossary/package.json",
]
DEP_KEYS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


def package_json(rel):
    return json.loads((FILES / rel).read_text())


def split_docs(text):
    return [c for c in re.split(r"^---\s*$", text, flags=re.M) if c.strip()]


def kind_of(doc):
    m = re.search(r"^kind: (\S+)", doc, flags=re.M)
    return m.group(1) if m else None


def version_tuple(v):
    return tuple(int(x) for x in v.split(".")[:3])


class StaticFiles(unittest.TestCase):
    def test_files_exist(self):
        for rel in PACKAGE_JSONS + [
            "pnpm-workspace.yaml", "pnpm-lock.yaml", "biome.json", "tsconfig.base.json", ".node-version",
            "RUN.stack.md", "scripts/web_boundary_check.py",
            "apps/web/next.config.ts", "apps/web/tsconfig.json", "apps/web/Dockerfile", ".dockerignore",
            "apps/web/app/layout.tsx", "apps/web/app/page.tsx", "apps/web/app/healthz/route.ts",
            "apps/web/app/robots.ts", "apps/web/lib/api.ts", "apps/web/lib/status.ts", "apps/web/lib/status.test.ts",
            "apps/web/e2e/home.spec.ts", "apps/web/e2e/stub-api.mjs", "apps/web/playwright.config.ts",
            "apps/web/scripts/boot-check.mjs",
            "apps/site/next.config.ts", "apps/site/tsconfig.json", "apps/site/Dockerfile",
            "apps/site/mdx-components.tsx", "apps/site/proxy.ts", "apps/site/app/layout.tsx", "apps/site/app/page.tsx",
            "apps/site/app/healthz/route.ts", "apps/site/app/robots.ts", "apps/site/app/sitemap.ts",
            "apps/site/app/blog/page.tsx", "apps/site/app/blog/hello-world/page.mdx", "apps/site/lib/posts.ts",
            "apps/site/lib/robots.ts", "apps/site/lib/robots.test.ts", "apps/site/scripts/boot-check.mjs",
            "packages/api-client/src/index.ts", "packages/api-client/src/generated/schema.d.ts",
            "packages/api-client/scripts/generate.mjs", "packages/api-client/scripts/check.mjs",
            "packages/api-client/README.md", "packages/api-client/src/index.test.ts",
            "packages/tokens/src/index.ts", "packages/tokens/scripts/build.mjs", "packages/tokens/README.md",
            "packages/tokens/src/index.test.ts", "packages/glossary/src/index.ts", "packages/glossary/src/terms.ts",
            "packages/glossary/src/index.test.ts",
            "infra/k8s/apps/web/Chart.yaml", "infra/k8s/apps/web/values.schema.json",
            "infra/k8s/apps/web/templates/all.yaml", "infra/k8s/apps/web/values.yaml",
            "infra/k8s/apps/site/Chart.yaml", "infra/k8s/apps/site/values.schema.json",
            "infra/k8s/apps/site/templates/all.yaml", "infra/k8s/apps/site/values.yaml",
        ]:
            self.assertTrue((FILES / rel).is_file(), rel)
        for app in APPS:
            for env in ENVS:
                self.assertTrue((FILES / ("infra/k8s/apps/%s/values-%s.yaml" % (app, env))).is_file(), (app, env))
        self.assertTrue((PACK / "SOURCES.md").is_file())
        for rel in ("docs/api/openapi.yaml", "docs/design/tokens.json", "packages/api-client/src/generated/schema.d.ts",
                    "packages/glossary/src/terms.ts", "apps/web/app/items/page.tsx"):
            self.assertTrue((EXAMPLE / rel).is_file(), "example/" + rel)

    def test_exact_pins_everywhere(self):
        for rel in PACKAGE_JSONS:
            data = package_json(rel)
            for key in DEP_KEYS:
                for name, spec in data.get(key, {}).items():
                    if spec.startswith("workspace:"):
                        self.assertEqual(spec, "workspace:*", (rel, name))
                        continue
                    self.assertRegex(spec, r"^\d+\.\d+\.\d+$", "%s %s %s" % (rel, name, spec))
        root = package_json("package.json")
        self.assertRegex(root["packageManager"], r"^pnpm@\d+\.\d+\.\d+$")
        self.assertTrue(root.get("private"))
        self.assertRegex((FILES / ".node-version").read_text().strip(), r"^\d+\.\d+\.\d+$")

    def test_nextjs_at_least_16_3(self):
        for rel in ("apps/web/package.json", "apps/site/package.json"):
            v = package_json(rel)["dependencies"]["next"]
            self.assertGreaterEqual(version_tuple(v), (16, 3, 0), rel)
        site = package_json("apps/site/package.json")["dependencies"]
        self.assertEqual(site["@next/mdx"], site["next"])

    def test_biome_and_typescript_configured(self):
        data = json.loads((FILES / "biome.json").read_text())
        self.assertTrue(data["linter"]["enabled"])
        self.assertIn("@biomejs/biome", package_json("package.json")["devDependencies"])
        base = json.loads((FILES / "tsconfig.base.json").read_text())
        self.assertTrue(base["compilerOptions"]["strict"])

    def test_workspace_and_release_age(self):
        t = (FILES / "pnpm-workspace.yaml").read_text()
        self.assertIn("apps/*", t)
        self.assertIn("packages/*", t)
        self.assertRegex(t, r"(?m)^minimumReleaseAge: 20160\b")  # transitive packages obey the two-week rule

    def test_scripts_fan_out(self):
        scripts = package_json("package.json")["scripts"]
        for name in ("lint", "typecheck", "test", "build", "e2e"):
            self.assertIn(name, scripts)

    def test_gitignore_covers_generated_output(self):
        t = (FILES / ".gitignore").read_text()
        for pat in ("node_modules/", ".next/", "playwright-report/", "test-results/", "next-env.d.ts"):
            self.assertIn(pat, t)
        self.assertNotIn("pnpm-lock", t)

    def test_no_generated_or_dependency_files_in_pack(self):
        git = shutil.which("git")
        if git is None:
            self.skipTest("skipped: git not on PATH")
        r = subprocess.run([git, "ls-files", "--cached", "--others", "--exclude-standard", str(PACK)],
                           capture_output=True, text=True, cwd=ROOT)
        for line in r.stdout.splitlines():
            self.assertNotRegex(line, r"(^|/)(node_modules|\.next|playwright-report|test-results)/", line)

    def test_dockerfiles_pin_by_digest_and_boot_check(self):
        for app, port in (("web", "3000"), ("site", "3000")):
            t = (FILES / ("apps/%s/Dockerfile" % app)).read_text()
            froms = re.findall(r"(?m)^FROM (\S+)", t)
            self.assertTrue(froms)
            for f in froms:
                self.assertRegex(f, r"^node:\d+\.\d+\.\d+-alpine@sha256:[0-9a-f]{64}$", app)
            self.assertIn("USER 10001:10001", t)
            self.assertIn("scripts/boot-check.mjs", t)
            self.assertIn("EXPOSE " + port, t)
            self.assertNotRegex(t, r"(?m)^USER root")

    def test_dockerfile_node_matches_node_version_file(self):
        major = (FILES / ".node-version").read_text().strip().split(".")[0]
        for app in ("web", "site"):
            t = (FILES / ("apps/%s/Dockerfile" % app)).read_text()
            self.assertIn("node:%s." % major, t)

    def test_web_pages_send_noindex_and_security_headers(self):
        t = (FILES / "apps/web/next.config.ts").read_text()
        for needle in ("X-Robots-Tag", "noindex", "Content-Security-Policy", "default-src 'self'",
                       "frame-ancestors 'none'", "Referrer-Policy", "X-Content-Type-Options", "standalone"):
            self.assertIn(needle, t)
        self.assertIn("disallow: '/'", (FILES / "apps/web/app/robots.ts").read_text())

    def test_site_noindex_is_decided_at_runtime(self):
        t = (FILES / "apps/site/proxy.ts").read_text()
        self.assertIn("X-Robots-Tag", t)
        self.assertIn("SITE_INDEXABLE", (FILES / "apps/site/lib/robots.ts").read_text())
        self.assertIn("standalone", (FILES / "apps/site/next.config.ts").read_text())

    def test_web_home_calls_api_health_server_side(self):
        t = (FILES / "apps/web/lib/api.ts").read_text()
        self.assertIn("API_INTERNAL_URL", t)
        self.assertIn("server-only", t)
        self.assertNotIn("NEXT_PUBLIC_", t)

    def test_playwright_runs_axe_wcag22(self):
        t = (FILES / "apps/web/e2e/home.spec.ts").read_text()
        self.assertIn("@axe-core/playwright", t)
        self.assertIn("wcag22aa", t)
        self.assertRegex(t, r"violations.*toEqual\(\[\]\)|toEqual\(\[\]\)")

    def test_no_secrets_or_public_env_in_apps(self):
        for app in ("web", "site"):
            for p in (FILES / "apps" / app).rglob("*"):
                if p.is_file() and "node_modules" not in p.parts and p.suffix in {".ts", ".tsx", ".mjs", ".mdx"}:
                    self.assertNotRegex(p.read_text(), r"(?i)(secret|password|api[_-]?key)\s*[:=]\s*[\"'][^\"']+[\"']", str(p))

    def test_api_chart_allows_web_pods_in(self):
        t = (FILES / "infra/k8s/apps/api/values.yaml").read_text()
        self.assertIn("kubernetes.io/metadata.name: web", t)

    def test_sources_record_every_direct_pin(self):
        t = (PACK / "SOURCES.md").read_text()
        for rel in PACKAGE_JSONS:
            data = package_json(rel)
            for key in DEP_KEYS:
                for name, spec in data.get(key, {}).items():
                    if not spec.startswith("workspace:"):
                        self.assertIn(name, t, name)
                        self.assertIn(spec, t, name)
        self.assertRegex(t, r"node:\d+\.\d+\.\d+-alpine@sha256:[0-9a-f]{64}")
        for name in ("next-dev-loop", "react-best-practices", "deploy-to-vercel"):
            self.assertIn(name, t)
        self.assertRegex(t, r"https://www\.npmjs\.com/package/next/v/")


class FixRound1(unittest.TestCase):
    def test_tokens_check_fails_without_source_when_output_exists(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("skipped: node not on PATH")
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(FILES / "packages/tokens", tmp / "packages/tokens")
        (tmp / "packages/tokens/src/generated.ts").write_text("export const tokens = {}\nexport const css = 'x'\n")
        r = subprocess.run([node, "scripts/build.mjs", "--check"], cwd=tmp / "packages/tokens", capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        # a pack without any tokens (step 7 not done) still passes with the shipped empty placeholder
        shutil.copy(FILES / "packages/tokens/src/generated.ts", tmp / "packages/tokens/src/generated.ts")
        r = subprocess.run([node, "scripts/build.mjs", "--check"], cwd=tmp / "packages/tokens", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_files_ship_placeholders_not_example_output(self):
        # files/ has no contract, tokens or terms: the generated outputs are placeholders, the example overlay has the real ones.
        self.assertIn("Placeholder", (FILES / "packages/api-client/src/generated/schema.d.ts").read_text())
        self.assertNotIn("/v1/items", (FILES / "packages/api-client/src/generated/schema.d.ts").read_text())
        self.assertTrue((FILES / "packages/tokens/src/generated.ts").read_text().startswith("// Placeholder."))
        self.assertNotIn("item", (FILES / "packages/glossary/src/terms.ts").read_text().replace("items", "").split("export const")[1])
        self.assertIn("/v1/items", (EXAMPLE / "packages/api-client/src/generated/schema.d.ts").read_text())
        self.assertIn("--color-background", (EXAMPLE / "packages/tokens/src/generated.ts").read_text())

    def test_site_sends_csp_and_security_headers(self):
        t = (FILES / "apps/site/next.config.ts").read_text()
        for needle in ("Content-Security-Policy", "default-src 'self'", "frame-ancestors 'none'", "Permissions-Policy",
                       "Referrer-Policy", "X-Content-Type-Options", "nosniff"):
            self.assertIn(needle, t)
        self.assertNotIn("unsafe-eval", t)

    def test_csp_trade_off_is_documented(self):
        for rel in ("RUN.stack.md",):
            t = (FILES / rel).read_text()
            self.assertIn("unsafe-inline", t)
            self.assertIn("nonce", t)
        self.assertIn("unsafe-inline", (PACK / "SOURCES.md").read_text())

    def test_npmrc_saves_exact(self):
        self.assertRegex((FILES / ".npmrc").read_text(), r"(?m)^save-exact=true$")
        self.assertRegex((FILES / "pnpm-workspace.yaml").read_text(), r"(?m)^minimumReleaseAge: 20160\b")


class PackYaml(unittest.TestCase):
    def setUp(self):
        self.text = (PACK / "pack.yaml").read_text()
        try:
            import yaml  # type: ignore
            self.data = yaml.safe_load(self.text)
        except ModuleNotFoundError:
            self.data = None

    def test_web_and_site_surfaces(self):
        if self.data is None:
            for n in ("web:", "site:", "# pavedline-surface: web", "# pavedline-surface: site", "apps/web", "apps/site"):
                self.assertIn(n, self.text)
            return
        s = self.data["surfaces"]
        for name in ("web", "site"):
            self.assertIn("apps/" + name, s[name]["paths"])
            self.assertIn("pavedline-surface: " + name, " ".join(s[name]["ci_markers"]))
            self.assertIn("infra/k8s/apps/" + name, s[name]["infra"])
            for cmd in ("install", "lint", "types", "test", "build", "image"):
                self.assertIn(cmd, s[name]["commands"], (name, cmd))
        self.assertIn("e2e", s["web"]["commands"])
        self.assertIn("biome ci", s["web"]["commands"]["lint"])
        self.assertIn("tsc --noEmit", s["web"]["commands"]["types"])
        for rel in ("package.json", "pnpm-workspace.yaml", "pnpm-lock.yaml", "biome.json", "tsconfig.base.json"):
            self.assertIn(rel, self.data["shared"]["paths"] if "shared" in self.data else [], rel)

    def test_shared_files_are_declared_for_web_or_site(self):
        self.assertRegex(self.text, r"(?s)shared:.*package\.json.*pnpm-lock\.yaml")
        self.assertIn("web or site", self.text)

    def test_nextjs_and_vercel_skills_listed_deploy_excluded(self):
        for n in ("next-dev-loop", "next-bundle-optimizer", "next-cache-components-adoption",
                  "next-cache-components-optimizer", "next-partial-prefetching-adoption",
                  "next-partial-prefetching-optimizer", "react-best-practices", "composition-patterns",
                  "web-design-guidelines", "react-view-transitions"):
            self.assertIn(n, self.text, n)
        self.assertIn("vercel/next.js", self.text)
        self.assertIn("vercel-labs/agent-skills", self.text)
        self.assertNotRegex(self.text, r"(?m)^\s*(- |name: ).*deploy-to-vercel")  # excluded, named only in a comment
        if self.data is not None:
            names = [s if isinstance(s, str) else s["name"] for s in self.data["skills"]]
            self.assertNotIn("deploy-to-vercel", names)
            self.assertIn("fastapi-service", names)


class BoundaryCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for app in ("web", "site"):
            shutil.copytree(FILES / "apps" / app, self.tmp / "apps" / app,
                            ignore=shutil.ignore_patterns("node_modules", ".next", "e2e"))

    def run_check(self):
        return subprocess.run([sys.executable, str(BOUNDARY), "--root", str(self.tmp)], capture_output=True, text=True)

    def plant(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def test_passes_on_the_shipped_apps(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bites_on_a_route_handler(self):
        self.plant("apps/web/app/api/items/route.ts", "export async function GET() { return new Response('x') }\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("apps/web/app/api/items/route.ts", r.stdout)

    def test_bites_on_a_route_handler_in_the_site(self):
        self.plant("apps/site/app/form/route.js", "export function POST() {}\n")
        self.assertEqual(self.run_check().returncode, 1)

    def test_allows_the_auth_cookie_proxy_path(self):
        self.plant("apps/web/app/auth/session/route.ts", "export function POST() {}\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_bites_on_a_server_action(self):
        self.plant("apps/web/app/actions.ts", '"use server";\nexport async function save() {}\n')
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("use server", r.stdout)

    def test_bites_on_an_inline_server_action_with_single_quotes(self):
        self.plant("apps/web/app/page2.tsx", "export default function P() {\n  async function f() {\n    'use server'\n  }\n  return null\n}\n")
        self.assertEqual(self.run_check().returncode, 1)

    def test_bites_on_database_imports(self):
        for i, line in enumerate(("import { PrismaClient } from '@prisma/client'", "import pg from 'pg'",
                                  "const x = require('drizzle-orm')", "import postgres from \"postgres\"",
                                  "import { sql } from '@vercel/postgres'")):
            self.plant("apps/web/lib/db%d.ts" % i, line + "\n")
            r = self.run_check()
            self.assertEqual(r.returncode, 1, line)
            (self.tmp / ("apps/web/lib/db%d.ts" % i)).unlink()

    def test_bites_on_a_database_dependency(self):
        p = self.tmp / "apps/web/package.json"
        data = json.loads(p.read_text())
        data["dependencies"]["pg"] = "8.0.0"
        p.write_text(json.dumps(data))
        self.assertEqual(self.run_check().returncode, 1)

    def test_ignores_node_modules_and_build_output(self):
        self.plant("apps/web/node_modules/x/route.ts", "export {}\n")
        self.plant("apps/web/.next/server/app/route.js", "export {}\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_bites_on_nested_and_src_app_route_handlers(self):
        for i, rel in enumerate(("apps/web/src/app/api/x/route.ts", "apps/web/app/(group)/api/y/route.tsx",
                                 "apps/site/app/deep/er/route.cjs", "apps/web/app/z/route.jsx",
                                 "apps/web/app/w/route.mjs", "apps/site/src/app/q/route.js")):
            self.plant(rel, "export {}\n")
            r = self.run_check()
            self.assertEqual(r.returncode, 1, rel)
            self.assertIn(rel, r.stdout)
            (self.tmp / rel).unlink()

    def test_bites_on_pages_api_handlers(self):
        for rel in ("apps/web/pages/api/hello.ts", "apps/web/src/pages/api/a/b.js", "apps/site/pages/api/x.tsx"):
            self.plant(rel, "export default function handler() {}\n")
            r = self.run_check()
            self.assertEqual(r.returncode, 1, rel)
            (self.tmp / rel).unlink()

    def test_skips_only_top_level_build_dirs(self):
        for rel in ("apps/web/app/dist/route.ts", "apps/web/app/test-results/route.ts", "apps/web/app/out/route.ts",
                    "apps/web/app/playwright-report/route.js"):
            self.plant(rel, "export {}\n")
            self.assertEqual(self.run_check().returncode, 1, rel)
            (self.tmp / rel).unlink()
        self.plant("apps/web/out/app/route.ts", "export {}\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_bites_on_use_server_anywhere(self):
        for i, body in enumerate(('export async function a() { "use server"; await 1 }\n',
                                  "export async function a() {'use server'\n}\n",
                                  "const f = async () => { 'use server' }\n",
                                  "'use server'\nexport const x = 1\n")):
            self.plant("apps/web/app/act%d.ts" % i, body)
            r = self.run_check()
            self.assertEqual(r.returncode, 1, body)
            (self.tmp / ("apps/web/app/act%d.ts" % i)).unlink()

    def test_bites_on_dynamic_and_commented_database_imports(self):
        for i, line in enumerate(('const m = await import(/* x */ "pg")', "const m = await import(`pg`)",
                                  'const m = require("pg")', 'import("postgres")', "import 'pg'",
                                  "export * from 'kysely'", 'import("pg/lib/client")', 'import(\n  "knex"\n)',
                                  "import x from 'slonik'", "import x from 'pg-promise'", "require( 'ioredis' )",
                                  "import m from 'mysql2/promise'", "import { neon } from '@neondatabase/serverless'")):
            self.plant("apps/site/lib/d%d.ts" % i, line + "\n")
            r = self.run_check()
            self.assertEqual(r.returncode, 1, line)
            (self.tmp / ("apps/site/lib/d%d.ts" % i)).unlink()

    def test_no_false_positive_on_similar_names(self):
        self.plant("apps/web/lib/ok.ts", "import x from 'pgp-utils'\nimport y from 'postgres-style'\nconst s = 'use client'\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_bites_on_database_import_in_middleware_and_proxy(self):
        for rel in ("apps/web/middleware.ts", "apps/web/src/middleware.ts", "apps/site/proxy.ts", "apps/web/src/proxy.ts"):
            self.plant(rel, "import pg from 'pg'\nexport function middleware() {}\n")
            self.assertEqual(self.run_check().returncode, 1, rel)
            (self.tmp / rel).unlink()

    def test_allow_list_entries_have_reasons(self):
        t = BOUNDARY.read_text()
        self.assertRegex(t, r"ALLOWED_ROUTE_DIRS\s*=\s*\{")
        for name in ("healthz", "auth"):
            self.assertRegex(t, r"[\"']%s[\"']\s*:\s*\"[^\"\n]{10,}" % name)

    def test_usage_error_exit_2(self):
        r = subprocess.run([sys.executable, str(BOUNDARY), "--root", str(self.tmp / "missing")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


@unittest.skipUnless(HELM, "skipped: helm not on PATH")
class Charts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(BASE, cls.tmp / "infra/helm/base-chart")
        shutil.copytree(FILES / "infra/k8s", cls.tmp / "infra/k8s")
        for app in ("api", "web", "site"):
            r = subprocess.run([HELM, "dependency", "update", str(cls.tmp / "infra/k8s/apps" / app)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stdout + r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def chart(self, app):
        return self.tmp / "infra/k8s/apps" / app

    def render(self, app, env):
        c = self.chart(app)
        r = subprocess.run([HELM, "template", "app-" + app, str(c), "-f", str(c / ("values-%s.yaml" % env)),
                            "--namespace", app], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def docs(self, app, env, kind):
        return [d for d in split_docs(self.render(app, env)) if kind_of(d) == kind]

    def test_lint_each_env(self):
        for app in APPS:
            for env in ENVS:
                c = self.chart(app)
                r = subprocess.run([HELM, "lint", str(c), "-f", str(c / ("values-%s.yaml" % env))], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, (app, env, r.stdout + r.stderr))

    def test_schema_copy_identical(self):
        for app in APPS:
            self.assertEqual((BASE / "app-values.schema.json").read_text(), (FILES / "infra/k8s/apps" / app / "values.schema.json").read_text())

    def test_chart_depends_on_base_chart(self):
        for app in APPS:
            t = (FILES / "infra/k8s/apps" / app / "Chart.yaml").read_text()
            self.assertIn("file://../../../helm/base-chart", t)
            self.assertEqual((FILES / "infra/k8s/apps" / app / "templates/all.yaml").read_text().strip(), '{{ include "base.render" . }}')

    def test_probes_port_priority_and_empty_dirs(self):
        for app in APPS:
            for env in ENVS:
                dep = self.docs(app, env, "Deployment")[0]
                self.assertRegex(dep, r"livenessProbe:\n\s+httpGet:\n\s+path: /healthz", (app, env))
                self.assertRegex(dep, r"readinessProbe:\n\s+httpGet:\n\s+path: /healthz", (app, env))
                self.assertIn("containerPort: 3000", dep)
                self.assertIn("priorityClassName: app-default", dep)
                self.assertIn("readOnlyRootFilesystem: true", dep)
                self.assertIn("/.next/cache", dep)  # writable cache for the standalone server

    def test_local_hostnames_and_route(self):
        for app, (_, host) in APPS.items():
            route = self.docs(app, "local", "HTTPRoute")[0]
            self.assertIn(host, route)
            self.assertRegex(route, r"name: shared\n\s+namespace: gateway\n\s+sectionName: http")

    def test_staging_and_production_hostnames_are_placeholders(self):
        for app in APPS:
            for env, pat in (("staging", r"\.staging\.example\.com"), ("production", r"example\.com")):
                self.assertRegex(self.docs(app, env, "HTTPRoute")[0], pat, (app, env))

    def test_digest_pins_in_staging_and_production(self):
        for app in APPS:
            for env in ("staging", "production"):
                t = (FILES / "infra/k8s/apps" / app / ("values-%s.yaml" % env)).read_text()
                self.assertRegex(t, r'digest: "sha256:[0-9a-f]{64}"', (app, env))
                self.assertNotRegex(t, r"(?m)^\s+tag:", (app, env))
                self.assertRegex(self.render(app, env), r"image: \"[^\"]+@sha256:[0-9a-f]{64}\"")

    def test_web_reaches_api_and_site_does_not(self):
        for env in ENVS:
            dep = self.docs("web", env, "Deployment")[0]
            self.assertRegex(dep, r"name: API_INTERNAL_URL\n\s+value: \"?http://app-api-api\.api\.svc\.cluster\.local\"?", env)
            np = [d for d in self.docs("web", env, "NetworkPolicy") if "name: app-web-web\n" in d][0]
            self.assertIn("kubernetes.io/metadata.name: api", np)
            self.assertIn("app.kubernetes.io/name: api", np)
            self.assertIn("port: 8000", np)
            self.assertIn("envoy-gateway-system", np)
            self.assertIn("port: 3000", np)
            site = [d for d in self.docs("site", env, "NetworkPolicy") if "name: app-site-site\n" in d][0]
            self.assertNotIn("port: 8000", site)

    def test_api_admits_web(self):
        np = [d for d in self.docs("api", "staging", "NetworkPolicy") if "name: app-api-api\n" in d][0]
        self.assertIn("kubernetes.io/metadata.name: web", np)
        self.assertIn("app.kubernetes.io/name: web", np)

    def test_site_indexing_per_env(self):
        expect = {"local": "false", "staging": "false", "production": "true"}
        for env, val in expect.items():
            dep = self.docs("site", env, "Deployment")[0]
            self.assertRegex(dep, r"name: SITE_INDEXABLE\n\s+value: \"%s\"" % val, env)
            self.assertIn("SITE_ORIGIN", dep)

    def test_no_secret_objects_or_literals_in_render(self):
        for app in APPS:
            for env in ENVS:
                out = self.render(app, env)
                self.assertNotIn("kind: Secret", out)
                self.assertNotRegex(out, r"(?im)password|postgres(ql)?://")

    @unittest.skipUnless(shutil.which("uvx"), "skipped: uvx not on PATH (Checkov run)")
    def test_checkov_clean_staging_and_production(self):
        for app in APPS:
            for env in ("staging", "production"):
                f = self.tmp / ("rendered-%s-%s.yaml" % (app, env))
                f.write_text(self.render(app, env))
                r = subprocess.run(["uvx", "checkov==3.3.30", "-f", str(f), "--config-file", str(CHECKOV), "--compact", "--quiet"],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, (app, env, r.stdout[-3000:] + r.stderr[-1000:]))


if __name__ == "__main__":
    unittest.main()
