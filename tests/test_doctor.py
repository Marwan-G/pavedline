import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/pavedline/scripts"))
import doctor  # noqa: E402

ALL_IDS = [
    "superpowers@claude-plugins-official",
    "mattpocock-skills@claude-plugins-official",
    "product-management@knowledge-work-plugins",
    "pavedline@pavedline",
]


def listing(ids, enabled=True):
    return json.dumps([{"id": i, "version": "1", "scope": "user", "enabled": enabled, "installPath": "x"} for i in ids])


GOOD_HELM = lambda: "v4.3.1"  # noqa: E731


def fake_which(missing=()):
    return lambda name: None if name in missing else "/usr/bin/" + name


def by_name(checks):
    return {c.name: c for c in checks}


class DoctorTests(unittest.TestCase):
    def test_missing_kind_is_required_failure(self):
        c = by_name(doctor.check_tools(which=fake_which({"kind"}), platform="Darwin", docker_ok=lambda: True, helm_version=GOOD_HELM))["kind"]
        self.assertFalse(c.ok)
        self.assertTrue(c.required)
        self.assertIn("kind", c.fix)
        self.assertEqual(c.fix, "brew install kind")

    def test_non_mac_gives_docs_url(self):
        c = by_name(doctor.check_tools(which=fake_which({"kind"}), platform="Linux", docker_ok=lambda: True, helm_version=GOOD_HELM))["kind"]
        self.assertTrue(c.fix.startswith("https://"))

    def test_optional_tools_not_required(self):
        checks = by_name(doctor.check_tools(which=fake_which({"uv", "colima", "terraform"}), platform="Darwin", docker_ok=lambda: True, helm_version=GOOD_HELM))
        for n in ("uv", "colima", "terraform"):
            self.assertFalse(checks[n].ok)
            self.assertFalse(checks[n].required)

    def test_container_runtime(self):
        checks = by_name(doctor.check_tools(which=fake_which(), platform="Darwin", docker_ok=lambda: False, helm_version=GOOD_HELM))
        c = checks["container runtime"]
        self.assertFalse(c.ok)
        self.assertTrue(c.required)
        self.assertEqual(c.fix, "brew install colima docker && colima start --cpu 4 --memory 10")

    def test_plugins_detected(self):
        checks = doctor.check_plugins(listing(ALL_IDS))
        self.assertEqual(len(checks), 4)
        self.assertTrue(all(c.ok for c in checks))

    def test_disabled_plugin_not_present(self):
        checks = doctor.check_plugins(listing(ALL_IDS, enabled=False))
        self.assertTrue(all(not c.ok for c in checks))

    def test_missing_dependency_has_install_fix(self):
        checks = by_name(doctor.check_plugins(listing(ALL_IDS[:2] + ALL_IDS[3:])))
        c = checks["product-management@knowledge-work-plugins"]
        self.assertFalse(c.ok)
        self.assertIn("/plugin install product-management@knowledge-work-plugins", c.fix)
        self.assertIn("/plugin marketplace add anthropics/knowledge-work-plugins", c.fix)

    def test_inline_pavedline_enabled_is_ok(self):
        ids = ALL_IDS[:3] + ["pavedline@inline"]
        c = by_name(doctor.check_plugins(listing(ids)))["pavedline@pavedline"]
        self.assertTrue(c.ok)
        self.assertEqual(c.status, "ok")

    def test_inline_pavedline_disabled_is_not_ok(self):
        data = json.loads(listing(ALL_IDS[:3]))
        data.append({"id": "pavedline@inline", "enabled": False})
        c = by_name(doctor.check_plugins(json.dumps(data)))["pavedline@pavedline"]
        self.assertFalse(c.ok)
        self.assertEqual(c.status, "disabled")

    def test_disabled_dependency_has_enable_fix(self):
        data = json.loads(listing(ALL_IDS))
        for p in data:
            if p["id"] == "superpowers@claude-plugins-official":
                p["enabled"] = False
        c = by_name(doctor.check_plugins(json.dumps(data)))["superpowers@claude-plugins-official"]
        self.assertFalse(c.ok)
        self.assertEqual(c.status, "disabled")
        self.assertEqual(c.fix, "/plugin enable superpowers@claude-plugins-official")

    def test_absent_dependency_is_missing(self):
        c = by_name(doctor.check_plugins(listing(ALL_IDS[1:])))["superpowers@claude-plugins-official"]
        self.assertEqual(c.status, "missing")
        self.assertIn("/plugin install", c.fix)

    def test_invalid_json_is_claude_failure(self):
        checks = doctor.check_plugins("not json")
        self.assertEqual([c.name for c in checks], ["claude"])
        self.assertFalse(checks[0].ok)
        self.assertTrue(checks[0].required)
        self.assertIn("https://code.claude.com/docs/en/setup", checks[0].fix)

    def test_run_exit_codes(self):
        out = []
        ok = doctor.run(which=fake_which(), platform="Darwin", docker_ok=lambda: True, helm_version=GOOD_HELM, listing_json=listing(ALL_IDS), out=out.append)
        self.assertEqual(ok, 0)
        self.assertIn("doctor: all required checks passed", out[-1])
        out = []
        bad = doctor.run(which=fake_which({"kind", "helm"}), platform="Darwin", docker_ok=lambda: True, helm_version=GOOD_HELM, listing_json=listing(ALL_IDS), out=out.append)
        self.assertEqual(bad, 1)
        self.assertEqual(out[-1], "doctor: 2 required check(s) failed")

    def test_no_claude_on_path(self):
        out = []
        rc = doctor.run(which=fake_which({"claude"}), platform="Darwin", docker_ok=lambda: True, helm_version=GOOD_HELM, listing_json=None, out=out.append)
        self.assertEqual(rc, 1)
        self.assertTrue(any("claude" in l and "missing" in l for l in out))

    def test_helm_with_known_wait_bug_is_flagged(self):
        # helm v4.2.1 waits the full --timeout on every hook deletion (helm#32214): 40 minutes for Argo CD.
        c = by_name(doctor.check_tools(which=fake_which(), platform="Darwin", docker_ok=lambda: True,
                                       helm_version=lambda: "v4.2.1"))["helm"]
        self.assertFalse(c.ok)
        self.assertTrue(c.required)
        self.assertEqual(c.status, "too old (v4.2.1, need 4.2.2+)")
        self.assertEqual(c.fix, "brew upgrade helm")

    def test_helm_too_old_on_linux_gives_docs_url(self):
        c = by_name(doctor.check_tools(which=fake_which(), platform="Linux", docker_ok=lambda: True,
                                       helm_version=lambda: "v4.1.0"))["helm"]
        self.assertFalse(c.ok)
        self.assertTrue(c.fix.startswith("https://"))

    def test_helm_current_and_unparseable(self):
        for v, ok in (("v4.3.1", True), ("v4.2.2", True), ("v5.0.0", True), ("v3.18.0", False), (None, False), ("garbage", False)):
            c = by_name(doctor.check_tools(which=fake_which(), platform="Darwin", docker_ok=lambda: True,
                                           helm_version=lambda v=v: v))["helm"]
            self.assertEqual(c.ok, ok, v)

    def test_min_helm_comes_from_versions_env(self):
        env = (ROOT / "plugins/pavedline/scripts/local-cluster/versions.env").read_text()
        self.assertIn("HELM_MIN_VERSION=4.2.2", env)
        self.assertIn("helm/helm/issues/32214", env)
        self.assertEqual(doctor.helm_min_version(), (4, 2, 2))


if __name__ == "__main__":
    unittest.main()
