import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ROOT / "plugins/pavedline/templates/infra/helm/base-chart"
APP = ROOT / "tests/fixtures/helm/example-app"
SKILL = ROOT / "plugins/pavedline/skills/helm-base-chart"
HELM = shutil.which("helm")
ENVS = ["local", "staging", "production"]


def split_docs(text):
    docs = []
    for chunk in re.split(r"^---\s*$", text, flags=re.M):
        if chunk.strip():
            docs.append(chunk)
    return docs


def kind_of(doc):
    m = re.search(r"^kind: (\S+)", doc, flags=re.M)
    return m.group(1) if m else None


class StaticFiles(unittest.TestCase):
    def test_files_exist(self):
        for p in [BASE / "Chart.yaml", BASE / "app-values.schema.json", BASE / "templates/_render.tpl",
                  APP / "Chart.yaml", APP / "values.schema.json", APP / "templates/all.yaml",
                  APP / "values-local.yaml", APP / "values-staging.yaml", APP / "values-production.yaml",
                  SKILL / "SKILL.md", SKILL / "references/sources.md"]:
            self.assertTrue(p.is_file(), str(p))

    def test_library_chart(self):
        self.assertRegex((BASE / "Chart.yaml").read_text(), r"(?m)^type: library$")

    def test_schema_copy_identical(self):
        self.assertEqual((BASE / "app-values.schema.json").read_text(), (APP / "values.schema.json").read_text())
        json.loads((APP / "values.schema.json").read_text())

    def test_staging_and_production_pin_digests(self):
        for env in ("staging", "production"):
            t = (APP / ("values-%s.yaml" % env)).read_text()
            self.assertEqual(len(re.findall(r"digest: \"sha256:[0-9a-f]{64}\"", t)), 2, env)
            self.assertNotRegex(t, r"(?m)^\s+tag:", env)

    def test_checkov_config_skips_have_reasons(self):
        t = (BASE.parent / ".checkov.yaml").read_text()
        ids = re.findall(r"(?m)^\s+- (CKV_\w+)", t)
        self.assertEqual(sorted(ids), ["CKV_K8S_15", "CKV_K8S_35"])
        for i in ids:
            self.assertRegex(t, r"(?m)^\s+#[^\n]+\n\s+- " + i)

    def test_no_secret_data_in_values(self):
        for env in ENVS:
            t = (APP / ("values-%s.yaml" % env)).read_text()
            self.assertNotRegex(t, r"(?i)postgres(ql)?://")

    def test_skill_and_sources(self):
        lines = (SKILL / "SKILL.md").read_text().splitlines()
        self.assertLessEqual(len(lines), 120)
        s = (SKILL / "references/sources.md").read_text()
        for needle in ("v1.6.3", "2026-10-06", "github.com/kubernetes-sigs/gateway-api/releases", "checkov", "Helm"):
            self.assertIn(needle, s)
        self.assertRegex(s, r"checkov==?\s*3\.\d+\.\d+|Checkov[^\n]*3\.\d+\.\d+")


@unittest.skipUnless(HELM, "skipped: helm not on PATH")
class Rendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(BASE, cls.tmp / "plugins/pavedline/templates/infra/helm/base-chart")
        cls.app = cls.tmp / "tests/fixtures/helm/example-app"
        shutil.copytree(APP, cls.app)
        r = subprocess.run([HELM, "dependency", "update", str(cls.app)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_helm(self, cmd, env, *extra):
        return subprocess.run([HELM, cmd, "rel", str(self.app), "-f", str(self.app / ("values-%s.yaml" % env)), *extra],
                              capture_output=True, text=True)

    def render(self, env, *extra):
        r = self.run_helm("template", env, "--namespace", "example", *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_lint_each_env(self):
        for env in ENVS:
            r = subprocess.run([HELM, "lint", str(self.app), "-f", str(self.app / ("values-%s.yaml" % env))],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, env + r.stdout + r.stderr)

    def test_template_each_env(self):
        for env in ENVS:
            self.assertIn("kind: Deployment", self.render(env))

    def test_hardening_and_workload_pieces(self):
        out = self.render("staging")
        for s in ("livenessProbe:", "readinessProbe:", "requests:", "limits:", "topologySpreadConstraints:",
                  "runAsNonRoot: true", "readOnlyRootFilesystem: true", "allowPrivilegeEscalation: false",
                  "type: RuntimeDefault", "automountServiceAccountToken: false", "priorityClassName: ",
                  "emptyDir:", "mountPath: /tmp"):
            self.assertIn(s, out, s)
        self.assertRegex(out, r"drop:\s*\n\s*- ALL")
        kinds = [kind_of(d) for d in split_docs(out)]
        for k in ("Deployment", "Service", "ServiceAccount", "PodDisruptionBudget", "NetworkPolicy", "HTTPRoute", "Job"):
            self.assertIn(k, kinds, k)

    def test_one_service_account_per_workload(self):
        out = self.render("staging")
        sas = [d for d in split_docs(out) if kind_of(d) == "ServiceAccount"]
        deps = [d for d in split_docs(out) if kind_of(d) == "Deployment"]
        self.assertEqual(len(deps), 2)  # api and worker
        names = {re.search(r"(?m)^  name: (\S+)", d).group(1) for d in sas}
        self.assertEqual(len(names), len(sas))
        self.assertEqual(len(sas), 3)  # api, worker, api-migrate
        for d in sas:
            self.assertIn("automountServiceAccountToken: false", d)

    def test_hpa_only_when_enabled(self):
        self.assertNotIn("HorizontalPodAutoscaler", self.render("local"))
        prod = self.render("production")
        self.assertIn("kind: HorizontalPodAutoscaler", prod)
        dep = [d for d in split_docs(prod) if kind_of(d) == "Deployment" and "name: rel-api" in d][0]
        self.assertNotRegex(dep, r"(?m)^  replicas:")

    def test_network_policy_default_deny_and_allows(self):
        out = self.render("staging")
        nps = [d for d in split_docs(out) if kind_of(d) == "NetworkPolicy"]
        api = [d for d in nps if "name: rel-api\n" in d][0]
        self.assertIn("- Ingress", api)
        self.assertIn("- Egress", api)
        self.assertIn("k8s-app: kube-dns", api)  # DNS always allowed
        self.assertIn("port: 53", api)
        self.assertIn("kubernetes.io/metadata.name: gateway-system", api)  # allow from values
        self.assertIn("app: db", api)  # egress allow from values

    def test_route(self):
        out = self.render("staging")
        route = [d for d in split_docs(out) if kind_of(d) == "HTTPRoute"][0]
        self.assertIn("apiVersion: gateway.networking.k8s.io/v1", route)
        self.assertIn("kind: Gateway", route)
        self.assertIn("name: example-gateway", route)
        self.assertIn("api.staging.example.test", route)

    def test_route_only_when_enabled(self):
        out = self.render("staging", "--set", "workloads.api.route.enabled=false")
        self.assertNotIn("HTTPRoute", out)

    def test_migration_job(self):
        out = self.render("staging")
        job = [d for d in split_docs(out) if kind_of(d) == "Job"][0]
        self.assertIn("argocd.argoproj.io/hook: PreSync", job)
        self.assertIn("argocd.argoproj.io/hook-delete-policy: BeforeHookCreation", job)
        self.assertIn("secretKeyRef:", job)
        self.assertIn("serviceAccountName: rel-api-migrate", job)
        self.assertIn("automountServiceAccountToken", out)
        deploy = [d for d in split_docs(out) if kind_of(d) == "Deployment" and "name: rel-api" in d][0]
        img = re.search(r"image: (\S+)", job).group(1)
        self.assertEqual(img, re.search(r"image: (\S+)", deploy).group(1))

    def test_no_migration_job_when_disabled(self):
        out = self.render("staging", "--set", "workloads.api.migrations.enabled=false")
        self.assertNotIn("kind: Job", out)

    def test_no_secret_objects(self):
        for env in ENVS:
            self.assertNotIn("kind: Secret", self.render(env))

    def test_missing_image_tag_fails(self):
        for env in ENVS:
            r = self.run_helm("template", env, "--set", "workloads.api.image.tag=null")
            self.assertNotEqual(r.returncode, 0, env)

    def test_missing_tag_without_env_values_fails(self):
        r = subprocess.run([HELM, "template", "rel", str(self.app)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("image", r.stderr)

    def test_digest_accepted_instead_of_tag(self):
        d = "sha256:" + "a" * 64
        sets = []
        for w in ("api", "worker"):
            sets += ["--set", "workloads.%s.image.digest=%s" % (w, d)]
        r = subprocess.run([HELM, "template", "rel", str(self.app), *sets], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("@" + d, r.stdout)

    def test_latest_tag_rejected(self):
        r = self.run_helm("template", "staging", "--set", "workloads.api.image.tag=latest")
        self.assertNotEqual(r.returncode, 0)

    def test_migration_pod_not_selected_by_service_or_pdb(self):
        out = self.render("staging")
        docs = split_docs(out)
        job = [d for d in docs if kind_of(d) == "Job"][0]
        pod_labels = job.split("template:")[1].split("labels:")[1].split("spec:")[0]
        svc = [d for d in docs if kind_of(d) == "Service" and "name: rel-api\n" in d][0]
        pdb = [d for d in docs if kind_of(d) == "PodDisruptionBudget" and "name: rel-api\n" in d][0]
        for d in (svc, pdb):
            sel = d.split("selector:")[1]
            name = re.search(r"app.kubernetes.io/name: (\S+)", sel).group(1)
            self.assertNotIn("app.kubernetes.io/name: %s\n" % name, pod_labels + "\n")
        self.assertIn("app.kubernetes.io/name: api-migrate", pod_labels)
        np = [d for d in docs if kind_of(d) == "NetworkPolicy" and "name: rel-api-migrate\n" in d][0]
        self.assertIn("app.kubernetes.io/name: api-migrate", np)

    def test_pdb_min_available_zero(self):
        out = self.render("staging", "--set", "workloads.api.pdb.minAvailable=0")
        pdb = [d for d in split_docs(out) if kind_of(d) == "PodDisruptionBudget" and "name: rel-api\n" in d][0]
        self.assertIn("minAvailable: 0", pdb)
        self.assertNotIn("maxUnavailable", pdb)

    def test_extra_empty_dir(self):
        out = self.render("staging")
        dep = [d for d in split_docs(out) if kind_of(d) == "Deployment" and "name: rel-api\n" in d][0]
        self.assertIn("mountPath: /app/.cache", dep)
        self.assertRegex(dep, r"- name: cache\n\s+emptyDir:")

    def test_hook_annotations_on_migration_objects(self):
        docs = split_docs(self.render("staging"))
        for kind, wave in (("ServiceAccount", "-2"), ("NetworkPolicy", "-2"), ("Job", "-1")):
            d = [x for x in docs if kind_of(x) == kind and "name: rel-api-migrate\n" in x][0]
            self.assertIn("argocd.argoproj.io/hook: PreSync", d, kind)
            self.assertIn('argocd.argoproj.io/sync-wave: "%s"' % wave, d, kind)

    def test_namespace_on_namespaced_objects(self):
        for d in split_docs(self.render("staging")):
            self.assertRegex(d, r"(?m)^  namespace: example$", kind_of(d))

    @unittest.skipUnless(shutil.which("uvx"), "skipped: uvx not on PATH (Checkov run)")
    def test_checkov_production_clean(self):
        out = self.render("production")
        f = self.tmp / "rendered.yaml"
        f.write_text(out)
        r = subprocess.run(["uvx", "checkov==3.3.30", "-f", str(f), "--config-file", str(BASE.parent / ".checkov.yaml"),
                            "--compact", "--quiet"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-1000:])

    def test_missing_priority_class_fails(self):
        r = self.run_helm("template", "staging", "--set", "priorityClassName=null")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
