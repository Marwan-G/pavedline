import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
K8S = PLUGIN / "templates/infra/k8s"
SKILL = PLUGIN / "skills/gitops/SKILL.md"


def read(p):
    return p.read_text()


class ApplicationSets(unittest.TestCase):
    def setUp(self):
        self.addons = read(K8S / "applicationsets/addons.yaml")
        self.apps = read(K8S / "applicationsets/apps.yaml")

    def test_kind_and_generator(self):
        for text, path in ((self.addons, "infra/k8s/addons/*"), (self.apps, "infra/k8s/apps/*")):
            self.assertIn("kind: ApplicationSet", text)
            self.assertIn("apiVersion: argoproj.io/v1alpha1", text)
            self.assertIn("directories:", text)
            self.assertIn("path: " + path, text)
            self.assertIn("repoURL: '{{REPO_URL}}'", text)
            self.assertIn("revision: '{{REVISION}}'", text)
            self.assertIn("path: '{{path}}'", text)

    def test_addons_auto_sync_and_self_heal(self):
        self.assertRegex(self.addons, r"(?m)^\s+automated:")
        self.assertRegex(self.addons, r"(?m)^\s+selfHeal: true")
        self.assertRegex(self.addons, r"(?m)^\s+prune: true")
        self.assertIn("CreateNamespace=true", self.addons)

    def test_apps_manual_sync_and_preserved(self):
        self.assertNotIn("automated", self.apps)
        self.assertRegex(self.apps, r"(?m)^\s+preserveResourcesOnDeletion: true")
        self.assertIn("CreateNamespace=true", self.apps)

    def test_no_latest_or_floating_revision(self):
        for text in (self.addons, self.apps):
            self.assertNotRegex(text, r"(?i)targetRevision:\s*(HEAD|latest)")


class Addons(unittest.TestCase):
    def test_priority_classes(self):
        d = K8S / "addons/priority-classes"
        text = "\n".join(read(p) for p in d.glob("*.yaml"))
        for name in ("app-critical", "app-default"):
            self.assertIn("name: " + name, text)
        self.assertEqual(text.count("kind: PriorityClass"), 2)
        self.assertNotRegex(text, r"globalDefault:\s*true")

    def test_envoyproxy_syncs_before_the_gatewayclass_that_references_it(self):
        """A GatewayClass applied before its EnvoyProxy is marked Accepted=False and the add-on stays Degraded."""
        proxy = read(K8S / "addons/gateway/envoyproxy.yaml")
        self.assertRegex(proxy, r'argocd\.argoproj\.io/sync-wave: "-1"')
        for f in (K8S / "addons/gateway").glob("*.yaml"):
            if "kind: GatewayClass" in read(f):
                self.assertNotIn("sync-wave: \"-1\"", read(f))

    def test_gateway_addon(self):
        text = "\n".join(read(p) for p in (K8S / "addons/gateway").glob("*.yaml"))
        self.assertIn("kind: GatewayClass", text)
        self.assertIn("gateway.envoyproxy.io/gatewayclass-controller", text)
        self.assertIn("kind: Gateway\n", text)
        self.assertIn("name: shared", text)
        self.assertIn("name: http", text)
        self.assertIn("kind: EnvoyProxy", text)
        self.assertIn("nodePort: 30080", text)
        self.assertNotIn("443", text)
        self.assertIn("allowedRoutes", text)

    def test_observability_slot_documented(self):
        t = read(K8S / "addons/README.md")
        self.assertIn("observability", t.lower())
        self.assertIn("reserved", t.lower())
        self.assertIn("auto", t.lower())


class Skill(unittest.TestCase):
    def test_skill(self):
        t = read(SKILL)
        self.assertTrue(t.startswith("---\nname: gitops\n"))
        self.assertLessEqual(len(t.splitlines()), 120)
        for needle in ["CI builds images and commits the tag bump; it never syncs", "kind-git",
                       "git://kind-git:9418", "push.sh", "preserveResourcesOnDeletion", "Git is the only path",
                       "values-staging.yaml", "references/sources.md"]:
            self.assertIn(needle, t, needle)

    def test_sources(self):
        t = read(PLUGIN / "skills/gitops/references/sources.md")
        for needle in ["2026-11-09", "gateway-api/releases", "envoyproxy", "git://"]:
            self.assertIn(needle, t, needle)


if __name__ == "__main__":
    unittest.main()
