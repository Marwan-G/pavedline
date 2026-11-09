import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LC = ROOT / "plugins/pavedline/scripts/local-cluster"
STARTER = (ROOT / "scripts/starter_check.sh").read_text()


def resolve(layout_root: pathlib.Path, rel_scripts: str):
    """Copy the local-cluster scripts to layout_root/rel_scripts and ask them where the add-ons are."""
    dest = layout_root / rel_scripts
    dest.mkdir(parents=True)
    for name in ("addons-dir.sh", "verify.sh"):
        src = LC / name
        if src.exists():
            (dest / name).write_text(src.read_text())
    return subprocess.run(
        ["bash", "-c", f'. "{dest}/addons-dir.sh"; resolve_addons_dir "{dest}"'],
        capture_output=True, text=True,
    )


class AddonsLayout(unittest.TestCase):
    def test_plugin_layout(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "templates/infra/k8s/addons/priority-classes").mkdir(parents=True)
            r = resolve(root, "scripts/local-cluster")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(pathlib.Path(r.stdout.strip()).resolve(),
                             (root / "templates/infra/k8s/addons").resolve())

    def test_product_layout(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "infra/k8s/addons/priority-classes").mkdir(parents=True)
            r = resolve(root, "scripts/local-cluster")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(pathlib.Path(r.stdout.strip()).resolve(),
                             (root / "infra/k8s/addons").resolve())

    def test_neither_layout_fails_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            r = resolve(pathlib.Path(d), "scripts/local-cluster")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("add-ons", r.stderr)

    def test_verify_uses_the_resolver(self):
        text = (LC / "verify.sh").read_text()
        self.assertIn("addons-dir.sh", text)
        self.assertIn("resolve_addons_dir", text)
        self.assertNotIn('ADDONS="$HERE/../../templates', text)


class StarterRunsProductCopies(unittest.TestCase):
    def test_cluster_stage_uses_generated_copies(self):
        self.assertIn('"$T/scripts/local-cluster/verify.sh"', STARTER)
        self.assertIn('"$T/scripts/local-cluster/down.sh"', STARTER)
        self.assertNotIn('"$PLUGIN/scripts/local-cluster/', STARTER)
        self.assertIn("cluster-verify", STARTER)


class DeploySkillWording(unittest.TestCase):
    def test_foreground_dispatch_and_kubectl_context(self):
        text = (ROOT / "plugins/pavedline/skills/deploy/SKILL.md").read_text()
        self.assertIn("Step 10 dispatches `pavedline:deployer` in the foreground", text)
        self.assertIn("sets the kubectl current context to `kind-pavedline-<project>`", text)


if __name__ == "__main__":
    unittest.main()
