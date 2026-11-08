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
    "figma@claude-plugins-official",
    "ui-ux-pro-max@ui-ux-pro-max-skill",
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

    def test_redocly_optional_for_step_5(self):
        c = by_name(doctor.check_tools(which=fake_which({"redocly"}), platform="Darwin", docker_ok=lambda: True, helm_version=GOOD_HELM))["redocly"]
        self.assertFalse(c.ok)
        self.assertFalse(c.required)
        self.assertIn("npm install -g @redocly/cli@2.71.0", c.fix)

    def test_container_runtime(self):
        checks = by_name(doctor.check_tools(which=fake_which(), platform="Darwin", docker_ok=lambda: False, helm_version=GOOD_HELM))
        c = checks["container runtime"]
        self.assertFalse(c.ok)
        self.assertTrue(c.required)
        self.assertEqual(c.fix, "brew install colima docker && colima start --cpu 4 --memory 10")

    def test_plugins_detected(self):
        checks = doctor.check_plugins(listing(ALL_IDS))
        self.assertEqual(len(checks), 6)
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

    def test_step_7_plugins_have_install_fixes(self):
        checks = by_name(doctor.check_plugins(listing(ALL_IDS[:3] + ALL_IDS[5:])))
        f = checks["figma@claude-plugins-official"]
        self.assertFalse(f.ok)
        self.assertTrue(f.required)
        self.assertIn("/plugin install figma@claude-plugins-official", f.fix)
        u = checks["ui-ux-pro-max@ui-ux-pro-max-skill"]
        self.assertFalse(u.ok)
        self.assertIn("/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill", u.fix)
        self.assertIn("/plugin install ui-ux-pro-max@ui-ux-pro-max-skill", u.fix)

    def test_impeccable_is_optional_and_listed(self):
        names = [n for n, _ in doctor.OPTIONAL_PLUGINS]
        self.assertEqual(names, ["impeccable@impeccable"])
        c = doctor.check_optional_plugins(listing(ALL_IDS))[0]
        self.assertFalse(c.ok)
        self.assertFalse(c.required)
        self.assertIn("/plugin marketplace add pbakaus/impeccable", c.fix)
        self.assertIn("/plugin install impeccable@impeccable", c.fix)
        c = doctor.check_optional_plugins(listing(ALL_IDS + ["impeccable@impeccable"]))[0]
        self.assertTrue(c.ok)

    def test_inline_pavedline_enabled_is_ok(self):
        ids = ALL_IDS[:5] + ["pavedline@inline"]
        c = by_name(doctor.check_plugins(listing(ids)))["pavedline@pavedline"]
        self.assertTrue(c.ok)
        self.assertEqual(c.status, "ok")

    def test_inline_pavedline_disabled_is_not_ok(self):
        data = json.loads(listing(ALL_IDS[:5]))
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

    def test_plugin_dir_load_is_not_reported_missing(self):
        # Docs (code.claude.com/docs/en/plugins-reference#environment-variables, checked 2026-11-08): the plugin path
        # variables are not in the environment of commands run through the Bash tool, so the script's own location
        # is the signal: a plugin installed by Claude Code lives under ~/.claude/plugins/.
        home = pathlib.Path("/home/u")
        self.assertTrue(doctor.loaded_from_plugin_dir(pathlib.Path("/work/pavedline/plugins/pavedline/scripts/doctor.py"), home))
        self.assertFalse(doctor.loaded_from_plugin_dir(home / ".claude/plugins/cache/pavedline/pavedline/0.1.0/scripts/doctor.py", home))
        c = by_name(doctor.check_plugins(listing(ALL_IDS[:5]), plugin_dir_load=True))["pavedline@pavedline"]
        self.assertTrue(c.ok)
        self.assertIn("--plugin-dir", c.status)
        c = by_name(doctor.check_plugins(listing(ALL_IDS[:5]), plugin_dir_load=False))["pavedline@pavedline"]
        self.assertFalse(c.ok)
        self.assertEqual(c.status, "missing")

    def test_config_dir_env_moves_the_plugin_store(self):
        # CLAUDE_CONFIG_DIR: Claude Code then stores settings, history and plugins there (settings docs, 2026-11-09).
        home = pathlib.Path("/home/u")
        cfg = pathlib.Path("/cfg")
        self.assertFalse(doctor.loaded_from_plugin_dir(cfg / "plugins/cache/p/0.1.0/scripts/doctor.py", home, cfg))
        self.assertTrue(doctor.loaded_from_plugin_dir(home / ".claude/plugins/cache/p/scripts/doctor.py", home, cfg))

    def test_node_range_for_redocly(self):
        for v, ok in (("v22.12.0", True), ("v22.11.9", False), ("v24.1.0", True), ("v20.19.0", True),
                      ("v20.18.0", False), ("v21.7.0", False), ("v18.0.0", False), (None, False)):
            self.assertEqual(doctor.redocly_node_ok(v), ok, v)
        checks = by_name(doctor.check_tools(which=fake_which(), platform="Darwin", docker_ok=lambda: True,
                                            helm_version=GOOD_HELM, node_version=lambda: "v18.0.0"))
        c = checks["node (for redocly)"]
        self.assertFalse(c.ok)
        self.assertFalse(c.required)
        self.assertIn("22.12", c.fix)
        checks = by_name(doctor.check_tools(which=fake_which(), platform="Darwin", docker_ok=lambda: True,
                                            helm_version=GOOD_HELM, node_version=lambda: "v22.12.0"))
        self.assertTrue(checks["node (for redocly)"].ok)


if __name__ == "__main__":
    unittest.main()
