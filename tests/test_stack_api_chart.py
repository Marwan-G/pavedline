import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PACK = PLUGIN / "stacks/nextjs-fastapi"
FILES = PACK / "files"
BASE = PLUGIN / "templates/infra/helm/base-chart"
CHECKOV = PLUGIN / "templates/infra/helm/.checkov.yaml"
API_CHART = FILES / "infra/k8s/apps/api"
PG_CHART = FILES / "infra/k8s/apps/postgres"
SECRETS = FILES / "scripts/local_secrets.sh"
ROLES_SQL = FILES / "services/api/db/roles.sql"
APPS_SET = PLUGIN / "templates/infra/k8s/applicationsets/apps.yaml"
HELM = shutil.which("helm")
BASH = shutil.which("bash")
ENVS = ["local", "staging", "production"]


def split_docs(text):
    return [c for c in re.split(r"^---\s*$", text, flags=re.M) if c.strip()]


def kind_of(doc):
    m = re.search(r"^kind: (\S+)", doc, flags=re.M)
    return m.group(1) if m else None


def name_of(doc):
    m = re.search(r"^  name: (\S+)", doc, flags=re.M)
    return m.group(1) if m else None


def all_text(path):
    return "\n".join(p.read_text() for p in sorted(path.rglob("*")) if p.is_file() and "charts" not in p.parts)


class StaticFiles(unittest.TestCase):
    def test_files_exist(self):
        for p in [API_CHART / "Chart.yaml", API_CHART / "values.schema.json", API_CHART / "templates/all.yaml",
                  API_CHART / "values.yaml", PG_CHART / "Chart.yaml", PG_CHART / "values.yaml",
                  PG_CHART / "files/roles.sql", PG_CHART / "templates/cluster.yaml",
                  PG_CHART / "templates/pooler.yaml", PG_CHART / "templates/roles-configmap.yaml",
                  SECRETS, FILES / ".env.local.example"]:
            self.assertTrue(p.is_file(), str(p))
        for env in ENVS:
            self.assertTrue((API_CHART / ("values-%s.yaml" % env)).is_file(), env)
            self.assertTrue((PG_CHART / ("values-%s.yaml" % env)).is_file(), env)

    def test_schema_copy_identical(self):
        self.assertEqual((BASE / "app-values.schema.json").read_text(), (API_CHART / "values.schema.json").read_text())
        json.loads((API_CHART / "values.schema.json").read_text())

    def test_roles_sql_single_source(self):
        # The service's db/roles.sql is the source; the database chart carries an identical copy (a chart can only
        # read files inside itself). The test keeps the two from drifting.
        self.assertEqual(ROLES_SQL.read_text(), (PG_CHART / "files/roles.sql").read_text())

    def test_api_chart_depends_on_base_chart(self):
        t = (API_CHART / "Chart.yaml").read_text()
        self.assertIn("file://../../../helm/base-chart", t)
        self.assertRegex(t, r"(?m)^type: application$")
        self.assertEqual((API_CHART / "templates/all.yaml").read_text().strip(), '{{ include "base.render" . }}')

    def test_staging_and_production_pin_digests(self):
        for env in ("staging", "production"):
            t = (API_CHART / ("values-%s.yaml" % env)).read_text()
            self.assertRegex(t, r'digest: "sha256:[0-9a-f]{64}"', env)
            self.assertNotRegex(t, r"(?m)^\s+tag:", env)

    def test_postgres_image_pinned_by_digest(self):
        t = (PG_CHART / "values.yaml").read_text()
        self.assertRegex(t, r"image: ghcr\.io/cloudnative-pg/postgresql:16\.\d+-\d+-standard-trixie@sha256:[0-9a-f]{64}")

    def test_no_literal_credentials_anywhere(self):
        for chart in (API_CHART, PG_CHART):
            t = all_text(chart)
            self.assertNotRegex(t, r"(?i)postgres(ql)?(\+\w+)?://", str(chart))
            self.assertNotRegex(t, r"(?im)^\s*(password|passwd|secret|token)[ \t]*:[ \t]*[\"']?\S", str(chart))
            self.assertNotIn("kind: Secret", t, str(chart))

    def test_apps_applicationset_selects_environment_values(self):
        t = APPS_SET.read_text()
        self.assertIn("valueFiles:", t)
        self.assertIn("values-{{ENVIRONMENT}}.yaml", t)
        self.assertIn("ignoreMissingValueFiles: true", t)
        self.assertNotIn("automated", t)

    def test_pack_lists_infra(self):
        t = (PACK / "pack.yaml").read_text()
        self.assertRegex(t, r"(?m)^    infra:\n(?:      - .*\n)*      - infra/k8s/apps/api\n")
        self.assertIn("- infra/k8s/apps/postgres", t)
        self.assertIn("- scripts/local_secrets.sh", t)

    def test_env_example_lists_keys_without_values(self):
        t = (FILES / ".env.local.example").read_text()
        for k in ("AUTH_ISSUER", "AUTH_AUDIENCE", "AUTH_JWKS_URL", "AUTH_TENANT_CLAIM"):
            self.assertRegex(t, r"(?m)^%s=$" % k)

    def test_env_local_is_ignored_and_example_is_not(self):
        git = shutil.which("git")
        if git is None:
            self.skipTest("skipped: git not on PATH")
        def ignored(name):
            return subprocess.run([git, "check-ignore", "-q", "--no-index", str(FILES / name)], cwd=ROOT).returncode == 0
        self.assertTrue(ignored(".env.local"))
        self.assertFalse(ignored(".env.local.example"))

    def test_script_is_executable_bash(self):
        self.assertTrue(SECRETS.stat().st_mode & stat.S_IXUSR)
        self.assertTrue(SECRETS.read_text().startswith("#!/usr/bin/env bash"))

    def test_skill_has_deploying_section(self):
        t = (PLUGIN / "skills/fastapi-service/SKILL.md").read_text()
        self.assertIn("## Deploying", t)
        for n in ("infra/k8s/apps/api", "local_secrets.sh", "gitops", ".env.local"):
            self.assertIn(n, t)
        self.assertLessEqual(len(t.splitlines()), 120)
        s = (PLUGIN / "skills/fastapi-service/references/sources.md").read_text()
        self.assertRegex(s, r"16\.\d+-\d+-standard-trixie")
        self.assertIn("ghcr.io/cloudnative-pg/postgresql", s)


@unittest.skipUnless(HELM, "skipped: helm not on PATH")
class FollowUps(unittest.TestCase):
    def test_every_app_folder_has_all_environment_values(self):
        apps = sorted(d for d in (FILES / "infra/k8s/apps").iterdir() if d.is_dir())
        names = {d.name for d in apps}
        self.assertTrue({"api", "postgres", "web", "site"} <= names, names)
        for d in apps:
            for env in ENVS:
                self.assertTrue((d / f"values-{env}.yaml").is_file(), f"{d.name} lacks values-{env}.yaml")

    def test_migration_job_tolerates_a_database_that_is_not_ready_yet(self):
        m = re.search(r"^\s+backoffLimit: (\d+)", (API_CHART / "values.yaml").read_text(), flags=re.M)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 6)

    def test_skills_explain_a_failed_first_sync(self):
        for s in ("gitops", "fastapi-service"):
            t = (PLUGIN / "skills" / s / "SKILL.md").read_text()
            self.assertRegex(t, r"first sync", s)
            self.assertRegex(t, r"(?i)sync again", s)

    def test_jwks_egress_excludes_link_local_and_shared_address_space(self):
        v = (API_CHART / "values.yaml").read_text()
        self.assertIn("169.254.0.0/16", v)
        self.assertIn("100.64.0.0/10", v)
        self.assertRegex((PLUGIN / "skills/fastapi-service/SKILL.md").read_text(), r"(?i)tighten to the provider")


class Rendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        # The layout of a product repository: infra/helm/base-chart and infra/k8s/apps/<app>.
        shutil.copytree(BASE, cls.tmp / "infra/helm/base-chart")
        shutil.copytree(FILES / "infra/k8s", cls.tmp / "infra/k8s")
        cls.api = cls.tmp / "infra/k8s/apps/api"
        cls.pg = cls.tmp / "infra/k8s/apps/postgres"
        r = subprocess.run([HELM, "dependency", "update", str(cls.api)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_helm(self, chart, cmd, env, *extra, ns="api"):
        args = [HELM, cmd] + (["rel"] if cmd == "template" else []) + [str(chart), "-f", str(chart / ("values-%s.yaml" % env))]
        if cmd == "template":
            args += ["--namespace", ns]
        return subprocess.run(args + list(extra), capture_output=True, text=True)

    def render(self, chart, env, *extra, ns="api"):
        r = self.run_helm(chart, "template", env, *extra, ns=ns)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def docs(self, chart, env, kind, ns="api"):
        return [d for d in split_docs(self.render(chart, env, ns=ns)) if kind_of(d) == kind]

    # --- the API chart

    def test_api_lint_and_template_each_env(self):
        for env in ENVS:
            r = self.run_helm(self.api, "lint", env)
            self.assertEqual(r.returncode, 0, env + r.stdout + r.stderr)
            self.assertIn("kind: Deployment", self.render(self.api, env))

    def test_deployment_database_url_from_api_db_secret(self):
        for env in ENVS:
            dep = [d for d in self.docs(self.api, env, "Deployment")][0]
            self.assertRegex(dep, r"name: DATABASE_URL\n\s+valueFrom:\n\s+secretKeyRef:\n\s+name: api-db\n\s+key: DATABASE_URL",
                             env)
            self.assertNotIn("DATABASE_OWNER_URL", dep, env)  # the app never gets the owner URL
            self.assertRegex(dep, r"envFrom:\n\s+- secretRef:\n\s+name: api-auth", env)
            self.assertRegex(dep, r"name: APP_ENV\n\s+value: \"?(development|production)\"?", env)

    def test_local_api_mounts_the_webhook_secret_as_optional_and_never_the_provider_keys(self):
        dep = self.docs(self.api, "local", "Deployment")[0]
        self.assertRegex(dep, r"- secretRef:\n\s+name: api-webhooks\n\s+optional: true")
        self.assertNotRegex(dep, r"name: api-auth\n\s+optional")
        self.assertNotIn("api-provider-keys", dep)
        for env in ("staging", "production"):
            self.assertNotIn("api-webhooks", self.docs(self.api, env, "Deployment")[0], env)

    def test_app_env_per_environment(self):
        expect = {"local": "development", "staging": "production", "production": "production"}
        for env, val in expect.items():
            dep = self.docs(self.api, env, "Deployment")[0]
            self.assertRegex(dep, r"name: APP_ENV\n\s+value: \"?%s\"?" % val, env)

    def test_probes_and_port(self):
        dep = self.docs(self.api, "staging", "Deployment")[0]
        self.assertRegex(dep, r"livenessProbe:\n\s+httpGet:\n\s+path: /healthz")
        self.assertRegex(dep, r"readinessProbe:\n\s+httpGet:\n\s+path: /readyz")
        self.assertIn("containerPort: 8000", dep)

    def test_migration_job_uses_owner_url(self):
        for env in ENVS:
            job = self.docs(self.api, env, "Job")[0]
            self.assertRegex(job, r"name: DATABASE_OWNER_URL\n\s+valueFrom:\n\s+secretKeyRef:\n\s+name: api-db\n\s+key: DATABASE_OWNER_URL", env)
            self.assertNotRegex(job, r"name: DATABASE_URL\n", env)
            self.assertRegex(job, r"command:\n\s+- alembic\n\s+- upgrade\n\s+- head", env)
            self.assertIn("argocd.argoproj.io/hook: PreSync", job)

    def test_route_attaches_to_shared_gateway(self):
        for env in ENVS:
            route = self.docs(self.api, env, "HTTPRoute")[0]
            self.assertRegex(route, r"name: shared\n\s+namespace: gateway\n\s+sectionName: http", env)
            self.assertIn("type: PathPrefix", route)
            self.assertIn("value: /", route)
        self.assertIn("api.localtest.me", self.docs(self.api, "local", "HTTPRoute")[0])

    def test_priority_class(self):
        self.assertIn("priorityClassName: app-default", self.docs(self.api, "local", "Deployment")[0])

    def test_network_policy_gateway_in_database_and_jwks_out(self):
        for env in ENVS:
            nps = self.docs(self.api, env, "NetworkPolicy")
            api = [d for d in nps if "name: rel-api\n" in d][0]
            self.assertIn("kubernetes.io/metadata.name: envoy-gateway-system", api, env)
            self.assertIn("gateway.envoyproxy.io/owning-gateway-name: shared", api, env)
            self.assertIn("kubernetes.io/metadata.name: postgres", api, env)
            self.assertIn("port: 5432", api, env)
            self.assertIn("cnpg.io/poolerName: db-pooler-rw", api, env)
            mig = [d for d in nps if "name: rel-api-migrate\n" in d][0]
            self.assertIn("cnpg.io/cluster: db", mig, env)  # the migration reaches the direct rw service
        for env in ("staging", "production"):
            api = [d for d in self.docs(self.api, env, "NetworkPolicy") if "name: rel-api\n" in d][0]
            self.assertIn("port: 443", api, env)
            self.assertIn("0.0.0.0/0", api, env)
            self.assertIn("10.0.0.0/8", api, env)  # private ranges excepted

    def test_staging_production_digest_in_render(self):
        for env in ("staging", "production"):
            self.assertRegex(self.render(self.api, env), r"image: \"[^\"]+@sha256:[0-9a-f]{64}\"", env)

    def test_no_secret_objects_or_literals_in_render(self):
        for env in ENVS:
            out = self.render(self.api, env)
            self.assertNotIn("kind: Secret", out)
            self.assertNotRegex(out, r"(?i)postgres(ql)?(\+\w+)?://")
            self.assertNotRegex(out, r"(?im)password")

    def test_namespace_on_namespaced_objects(self):
        for d in split_docs(self.render(self.api, "staging")):
            self.assertRegex(d, r"(?m)^  namespace: api$", kind_of(d))

    @unittest.skipUnless(shutil.which("uvx"), "skipped: uvx not on PATH (Checkov run)")
    def test_checkov_clean_staging_and_production(self):
        # local runs a tag from the local registry by design (CKV_K8S_43 wants a digest), so only the two cloud
        # environments are scanned, as the base chart's own test scans production.
        for env in ("staging", "production"):
            f = self.tmp / ("rendered-%s.yaml" % env)
            f.write_text(self.render(self.api, env))
            r = subprocess.run(["uvx", "checkov==3.3.30", "-f", str(f), "--config-file", str(CHECKOV), "--compact",
                                "--quiet"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, env + r.stdout[-3000:] + r.stderr[-1000:])

    # --- the database chart

    def test_postgres_lint_and_template_each_env(self):
        for env in ENVS:
            r = self.run_helm(self.pg, "lint", env)
            self.assertEqual(r.returncode, 0, env + r.stdout + r.stderr)

    def test_cluster_instances_per_env(self):
        for env, n in (("local", 1), ("staging", 3), ("production", 3)):
            c = self.docs(self.pg, env, "Cluster", ns="postgres")[0]
            self.assertIn("apiVersion: postgresql.cnpg.io/v1", c)
            self.assertRegex(c, r"(?m)^  instances: %d$" % n, env)
            self.assertRegex(c, r"imageName: ghcr\.io/cloudnative-pg/postgresql:16\.\d+-\d+-standard-trixie@sha256:[0-9a-f]{64}")

    def test_managed_roles(self):
        c = self.docs(self.pg, "staging", "Cluster", ns="postgres")[0]
        roles = {}
        for m in re.finditer(r"(?m)^      - name: (\w+)\n((?:        .*\n)+)", c.split("managed:")[1]):
            roles[m.group(1)] = m.group(2)
        self.assertEqual(sorted(roles), ["app_admin", "app_owner", "app_runtime"])
        for name, body in roles.items():
            self.assertIn("login: true", body, name)
            self.assertIn("ensure: present", body, name)
            self.assertIn("superuser: false", body, name)
            self.assertRegex(body, r"passwordSecret:\n\s+name: db-%s" % name.split("_")[1], name)
        self.assertIn("bypassrls: true", roles["app_owner"])
        self.assertIn("bypassrls: false", roles["app_runtime"])
        self.assertIn("bypassrls: false", roles["app_admin"])
        self.assertEqual(c.count("bypassrls: true"), 1)
        self.assertIn("inherit: false", roles["app_runtime"])

    def test_initdb_database_owned_by_app_owner_and_hardened(self):
        c = self.docs(self.pg, "local", "Cluster", ns="postgres")[0]
        self.assertRegex(c, r"initdb:\n\s+database: app\n\s+owner: app_owner")
        self.assertRegex(c, r"secret:\n\s+name: db-owner")
        self.assertRegex(c, r"postInitApplicationSQLRefs:\n\s+configMapRefs:\n\s+- name: db-roles-sql\n\s+key: roles.sql")
        cm = self.docs(self.pg, "local", "ConfigMap", ns="postgres")[0]
        self.assertIn("name: db-roles-sql", cm)
        for line in ("REVOKE CREATE ON SCHEMA public FROM PUBLIC", "REVOKE app_owner FROM app_runtime"):
            self.assertIn(line, cm)
        sql = ROLES_SQL.read_text()
        for line in sql.splitlines():
            if line.strip() and not line.startswith("--"):
                self.assertIn(line.rstrip(), cm)

    def test_pooler_transaction_mode(self):
        for env in ENVS:
            p = self.docs(self.pg, env, "Pooler", ns="postgres")[0]
            self.assertIn("name: db-pooler-rw", p)
            self.assertRegex(p, r"cluster:\n\s+name: db")
            self.assertRegex(p, r"type: rw")
            self.assertRegex(p, r"poolMode: transaction")

    def test_postgres_priority_and_namespace(self):
        c = self.docs(self.pg, "staging", "Cluster", ns="postgres")[0]
        self.assertIn("priorityClassName: app-critical", c)
        for d in split_docs(self.render(self.pg, "staging", ns="postgres")):
            self.assertRegex(d, r"(?m)^  namespace: postgres$", kind_of(d))

    def test_postgres_network_policy_admits_api_and_operator(self):
        np = self.docs(self.pg, "staging", "NetworkPolicy", ns="postgres")[0]
        self.assertIn("kubernetes.io/metadata.name: api", np)
        self.assertIn("kubernetes.io/metadata.name: cnpg-system", np)
        self.assertIn("port: 5432", np)

    def test_production_readiness_is_marked(self):
        # Backups and the restore drill exist since v0.4; the endpoint and bucket stay placeholders until step 12.
        t = (PG_CHART / "values-production.yaml").read_text() + (PG_CHART / "templates/cluster.yaml").read_text()
        self.assertIn("PLACEHOLDERS", t)
        self.assertIn("step 12", t)
        self.assertIn("restore_drill.sh", t)


class LocalSecretsScript(unittest.TestCase):
    """The script is kind-only: it refuses any context that is not kind-pavedline-<project> before it changes anything."""

    def run_script(self, project, contexts, nodes, extra_env=None, cwd=None):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        log = tmp / "kubectl.log"
        stub = tmp / "bin"
        stub.mkdir()
        k = stub / "kubectl"
        k.write_text(
            "#!/usr/bin/env bash\n"
            "echo \"$*\" >> \"%s\"\n"
            "case \"$*\" in\n"
            "  *'config get-contexts'*) printf '%%s\\n' %s ;;\n"
            "  *'get nodes'*) printf '%%s\\n' %s ;;\n"
            "esac\n"
            "exit 0\n" % (log, " ".join("'%s'" % c for c in contexts), " ".join("'%s'" % n for n in nodes)))
        k.chmod(0o755)
        env = dict(os.environ, PATH=str(stub) + os.pathsep + os.environ["PATH"])
        env.update(extra_env or {})
        r = subprocess.run([BASH, str(SECRETS), *project], capture_output=True, text=True, env=env, cwd=cwd or tmp)
        return r, (log.read_text() if log.exists() else "")

    def mutating(self, log):
        return [l for l in log.splitlines() if re.search(r"\b(apply|create|patch|delete|replace|label)\b", l)]

    def test_refuses_a_context_that_is_not_kind(self):
        r, log = self.run_script(["ci"], ["prod-cluster", "arn:aws:eks:x"], [])
        self.assertNotEqual(r.returncode, 0)
        self.assertRegex(r.stderr, r"kind-pavedline-ci")
        self.assertEqual(self.mutating(log), [], log)

    def test_refuses_when_the_node_is_not_the_kind_control_plane(self):
        r, log = self.run_script(["ci"], ["kind-pavedline-ci"], ["ip-10-0-0-5.ec2.internal"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("pavedline-ci-control-plane", r.stderr)
        self.assertEqual(self.mutating(log), [], log)

    def test_refuses_bad_project_names_and_missing_argument(self):
        for args in ([], ["Bad_Name"], ["kind-pavedline-ci"], ["a", "b"]):
            r, log = self.run_script(args, ["kind-pavedline-ci"], ["pavedline-ci-control-plane"])
            self.assertNotEqual(r.returncode, 0, args)
            self.assertEqual(self.mutating(log), [], args)

    def test_passes_the_context_on_every_call_and_never_prints_values(self):
        r, log = self.run_script(["ci"], ["kind-pavedline-ci"], ["pavedline-ci-control-plane"])
        self.assertEqual(r.returncode, 0, r.stderr)
        for line in log.splitlines():
            if "config get-contexts" not in line:  # the one call that asks which contexts exist
                self.assertIn("--context kind-pavedline-ci", line)
        self.assertTrue(self.mutating(log))
        self.assertNotRegex(r.stdout + r.stderr, r"postgresql://")

    def run_with_secret_lookup(self, lookup_script):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        log = tmp / "kubectl.log"
        stub = tmp / "bin"
        stub.mkdir()
        k = stub / "kubectl"
        k.write_text(
            "#!/usr/bin/env bash\n"
            "echo \"$*\" >> \"%s\"\n"
            "case \"$*\" in\n"
            "  *'config get-contexts'*) echo kind-pavedline-ci ;;\n"
            "  *'get nodes'*) echo pavedline-ci-control-plane ;;\n"
            "  *'get secret'*) %s ;;\n"
            "esac\n"
            "exit 0\n" % (log, lookup_script))
        k.chmod(0o755)
        env = dict(os.environ, PATH=str(stub) + os.pathsep + os.environ["PATH"])
        r = subprocess.run([BASH, str(SECRETS), "ci"], capture_output=True, text=True, env=env, cwd=tmp)
        return r, log.read_text()

    def run_provider_keys(self, env_text):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        stub = tmp / "bin"
        stub.mkdir()
        k = stub / "kubectl"
        k.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  *'config get-contexts'*) echo kind-pavedline-ci ;;\n"
            "  *'get nodes'*) echo pavedline-ci-control-plane ;;\n"
            "  *'create secret generic api-webhooks'*) cat > \"%s/api-webhooks.env\" ;;\n"
            "  *'create secret generic api-provider-keys'*) cat > \"%s/api-provider-keys.env\" ;;\n"
            "esac\nexit 0\n" % (tmp, tmp))
        k.chmod(0o755)
        envf = tmp / "env"
        envf.write_text(env_text)
        env = dict(os.environ, PATH=str(stub) + os.pathsep + os.environ["PATH"], ENV_FILE=str(envf))
        r = subprocess.run([BASH, str(SECRETS), "ci"], capture_output=True, text=True, env=env, cwd=tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("sk_test_abc", r.stdout + r.stderr)
        return tmp

    def test_provider_test_keys_go_to_their_own_secret_only_when_non_empty(self):
        example = (FILES / ".env.local.example").read_text()
        for key in ("WEBHOOK_CLERK_SECRET", "WEBHOOK_STRIPE_SECRET"):
            self.assertRegex(example, r"(?m)^%s=$" % key)
        for key in ("CLERK_SECRET_KEY", "STRIPE_SECRET_KEY"):  # commented: the product's own slices enable them
            self.assertRegex(example, r"(?m)^# %s=$" % key)
        self.assertIn("api-provider-keys", example)
        tmp = self.run_provider_keys(
            "CLERK_SECRET_KEY=sk_test_abc\nSTRIPE_SECRET_KEY=\nWEBHOOK_CLERK_SECRET=whsec_x\n")
        self.assertEqual((tmp / "api-webhooks.env").read_text(), "WEBHOOK_CLERK_SECRET=whsec_x\n")
        self.assertEqual((tmp / "api-provider-keys.env").read_text(), "CLERK_SECRET_KEY=sk_test_abc\n")
        # no provider key given: the Secret is not created at all
        tmp = self.run_provider_keys("WEBHOOK_STRIPE_SECRET=whsec_y\n")
        self.assertEqual((tmp / "api-webhooks.env").read_text(), "WEBHOOK_STRIPE_SECRET=whsec_y\n")
        self.assertFalse((tmp / "api-provider-keys.env").exists())

    def test_env_local_is_ignored_in_both_gitignores(self):
        for g in (PLUGIN / "templates/.gitignore", FILES / ".gitignore"):
            self.assertIn(".env.local", [l.strip() for l in g.read_text().splitlines()], g)

    def test_a_transient_kubectl_error_never_regenerates_a_password(self):
        r, log = self.run_with_secret_lookup("echo 'Unable to connect to the server' >&2; exit 1")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotRegex(log, r"create secret")

    def test_a_missing_secret_is_created(self):
        r, log = self.run_with_secret_lookup(
            "echo 'Error from server (NotFound): secrets \"x\" not found' >&2; exit 1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(log, r"create secret")


if __name__ == "__main__":
    unittest.main()
