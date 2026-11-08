import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from tests.test_local_cluster_static import LC


class UpHelmGate(unittest.TestCase):
    """up.sh refuses a helm with the known hook-wait bug before touching anything."""

    def run_up(self, helm_version):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        bin_dir = pathlib.Path(d)
        marker = bin_dir / "docker-called"
        stubs = {
            "helm": f'#!/bin/sh\nif [ "$1" = version ]; then echo "{helm_version}"; exit 0; fi\nexit 0\n',
            "docker": f"#!/bin/sh\ntouch {marker}\nexit 1\n",
            "kind": "#!/bin/sh\nexit 0\n",
            "kubectl": "#!/bin/sh\nexit 0\n",
        }
        for name, body in stubs.items():
            f = bin_dir / name
            f.write_text(body)
            f.chmod(0o755)
        env = dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin")
        r = subprocess.run(["bash", str(LC / "up.sh"), "gatetest"], capture_output=True, text=True, env=env)
        return r, marker.exists()

    def test_buggy_helm_is_refused_before_docker(self):
        r, docker_called = self.run_up("v4.2.1")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("helm v4.2.1 is too old", r.stderr)
        self.assertIn("4.2.2", r.stderr)
        self.assertIn("https://github.com/helm/helm/issues/32214", r.stderr)
        self.assertFalse(docker_called, "up.sh must stop before touching the container runtime")

    def test_unreadable_helm_version_is_refused(self):
        r, docker_called = self.run_up("not-a-version")
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not read the helm version", r.stderr)
        self.assertFalse(docker_called)

    def test_good_helm_passes_the_gate(self):
        for v in ("v4.2.2", "v4.3.1", "v4.10.0", "v5.0.0"):
            r, docker_called = self.run_up(v)
            self.assertNotIn("too old", r.stderr, v)
            self.assertTrue(docker_called, f"{v}: gate should pass and reach the runtime check")
            self.assertIn("no container runtime answers", r.stderr, v)


if __name__ == "__main__":
    unittest.main()
