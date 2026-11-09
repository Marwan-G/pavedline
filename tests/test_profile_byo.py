import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PROFILE = PLUGIN / "templates/infra/profiles/byo-kubernetes"
BOOT = PROFILE / "bootstrap.sh"
VERSIONS = PLUGIN / "scripts/local-cluster/versions.env"
CTX = "prod-eu-1"

FAKE = """#!/usr/bin/env bash
# Records every call; fakes the few outputs bootstrap.sh reads.
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$FAKE_LOG"
case "$(basename "$0")" in
  curl)
    out=""
    while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done
    [ -n "$out" ] && printf 'fake-download\\n' > "$out"
    ;;
  helm)
    if [ "$1" = pull ]; then
      while [ $# -gt 0 ]; do [ "$1" = "--untardir" ] && d="$2"; shift; done
      mkdir -p "$d/gateway-helm/charts/crds/crds/generated"
    fi
    ;;
  kubectl)
    case "$*" in *jsonpath*) printf 'sidecar-secret' ;; esac
    if [ -n "${FAKE_FAIL_FIRST:-}" ] && [[ "$*" == *"apply -f"* && "$*" != *server-side* ]]; then
      n=0; [ -f "$FAKE_LOG.n" ] && n=$(cat "$FAKE_LOG.n"); n=$((n + 1)); echo $n > "$FAKE_LOG.n"
      size=0
      for a in "$@"; do [ -f "$a" ] && size=$(wc -c < "$a"); done
      [ "$size" = 0 ] && size=$(wc -c)
      echo "attempt $n size $size" >> "$FAKE_LOG.sizes"
      [ "$n" = 1 ] && exit 1
    fi
    ;;
esac
exit 0
"""


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Harness:
    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.bin = t / "bin"
        self.bin.mkdir()
        for name in ("kubectl", "helm", "curl"):
            f = self.bin / name
            f.write_text(FAKE)
            f.chmod(f.stat().st_mode | stat.S_IXUSR)
        self.log = t / "calls.log"
        self.log.write_text("")
        fake = t / "fake-download"
        fake.write_text("fake-download\n")
        digest = sha(fake)
        pins = VERSIONS.read_text()
        pins = re.sub(r"^GATEWAY_CRDS_SHA256=.*$", f"GATEWAY_CRDS_SHA256={digest}", pins, flags=re.M)
        pins = re.sub(r"^BARMAN_PLUGIN_SHA256=.*$", f"BARMAN_PLUGIN_SHA256={digest}", pins, flags=re.M)
        self.pins = t / "versions.env"
        self.pins.write_text(pins)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", FAKE_LOG=str(self.log),
                        PAVEDLINE_PINS=str(self.pins), PAVEDLINE_TEST="1",
                        PAVEDLINE_RETRY_ATTEMPTS="1", PAVEDLINE_RETRY_DELAY="0")

    def run(self, *args):
        return subprocess.run(["bash", str(BOOT), *args], capture_output=True, text=True, env=self.env)

    def calls(self):
        return [ln for ln in self.log.read_text().splitlines() if ln]


GOOD = ["--repo-url", "git://example.invalid/p.git", "--revision", "abc1234", "--environment", "staging"]


class Bootstrap(unittest.TestCase):
    def test_context_is_required(self):
        h = Harness(self)
        r = h.run(*GOOD)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--context", r.stderr)
        self.assertEqual(h.calls(), [])

    def test_refusals(self):
        h = Harness(self)
        base = ["--context", CTX]
        cases = {
            "environment": ["--repo-url", "u", "--environment", "dev"],
            "empty repo": ["--repo-url", "", "--environment", "staging"],
            "missing repo": ["--environment", "staging"],
            "bad revision": ["--repo-url", "u", "--revision", "a b;rm", "--environment", "staging"],
            "print and yes": GOOD + ["--yes", "--print"],
        }
        for name, extra in cases.items():
            r = h.run(*base, *extra)
            self.assertEqual(r.returncode, 2, name + r.stdout + r.stderr)
        self.assertEqual(h.calls(), [])

    def test_production_on_kind_needs_allow_kind(self):
        h = Harness(self)
        args = ["--context", "kind-pavedline-x", "--repo-url", "u", "--environment", "production", "--yes"]
        r = h.run(*args)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--allow-kind", r.stderr)
        self.assertEqual(h.calls(), [])
        r = h.run(*args, "--allow-kind")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_default_prints_and_runs_nothing(self):
        h = Harness(self)
        r = h.run("--context", CTX, *GOOD)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(h.calls(), [])
        for word in ("kubectl", "helm", "Gateway API", "cert-manager", "cloudnative-pg", "barman", "argo-cd", "--context " + CTX):
            self.assertIn(word.lower(), r.stdout.lower(), word)
        self.assertIn("applicationsets", r.stdout)

    def test_yes_pins_every_call_to_the_context(self):
        h = Harness(self)
        r = h.run("--context", CTX, *GOOD, "--yes", "--tunnel")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = h.calls()
        self.assertTrue(calls)
        for c in calls:
            tool, rest = c.split(" ", 1)
            if tool == "kubectl":
                self.assertIn(f"--context {CTX}", rest, c)
            elif tool == "helm" and rest.split(" ", 1)[0] in ("upgrade", "install"):
                self.assertIn(f"--kube-context {CTX}", rest, c)
            self.assertNotIn("--kubeconfig", c)
        joined = "\n".join(calls)
        for chart in ("argo-cd", "cloudnative-pg", "cert-manager", "gateway-helm"):
            self.assertIn(chart, joined)
        self.assertIn("crds.enabled=true", joined)
        self.assertEqual(sum(1 for c in calls if c.startswith("helm upgrade")), 4)

    def test_checksum_mismatch_stops_before_apply(self):
        h = Harness(self)
        pins = h.pins.read_text().replace("GATEWAY_CRDS_SHA256=", "GATEWAY_CRDS_SHA256=00", 1)
        h.pins.write_text(pins)
        r = h.run("--context", CTX, *GOOD, "--yes")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse([c for c in h.calls() if c.startswith("kubectl")])

    def test_applicationsets_are_rendered_from_flags(self):
        h = Harness(self)
        r = h.run("--context", CTX, *GOOD)
        self.assertIn("git://example.invalid/p.git", r.stdout + "")  # printed in the render step
        self.assertIn("abc1234", r.stdout)
        self.assertIn("staging", r.stdout)


class Retry(unittest.TestCase):
    def test_every_retry_sends_the_full_manifest(self):
        h = Harness(self)
        h.env.update(FAKE_FAIL_FIRST="1", PAVEDLINE_RETRY_ATTEMPTS="3")
        r = h.run("--context", CTX, *GOOD, "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sizes = Path(str(h.log) + ".sizes").read_text().splitlines()
        self.assertGreaterEqual(len(sizes), 2, sizes)
        first = sizes[0].split()[-1]
        self.assertNotEqual(first, "0")
        for line in sizes[:2]:
            self.assertEqual(line.split()[-1], first, sizes)

    def test_retry_message_names_bootstrap(self):
        h = Harness(self)
        h.env.update(FAKE_FAIL_FIRST="1")
        r = h.run("--context", CTX, *GOOD, "--yes")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("re-run bootstrap.sh", r.stderr)
        self.assertNotIn("up.sh", r.stderr)

    def test_printed_plan_uses_the_run_paths(self):
        h = Harness(self)
        printed = h.run("--context", CTX, *GOOD).stdout
        ran = h.run("--context", CTX, *GOOD, "--yes").stdout
        norm = lambda t: re.sub(r"/[^ ]*?/pavedline-bootstrap\.[A-Za-z0-9]+", "WORK", t)
        self.assertEqual(norm(printed).count("WORK"), norm(ran).count("WORK"))
        self.assertIn("pavedline-bootstrap", printed)

    def test_pins_override_is_test_only(self):
        h = Harness(self)
        del h.env["PAVEDLINE_TEST"]
        r = h.run("--context", CTX, *GOOD)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("PAVEDLINE_TEST", r.stderr)
        h.env["PAVEDLINE_TEST"] = "1"
        r = h.run("--context", CTX, *GOOD)
        self.assertIn(str(h.pins), r.stdout + r.stderr)

    def test_tunnel_does_not_need_the_priority_class_from_argo(self):
        dep = (PROFILE / "cloudflared/deployment.yaml").read_text()
        self.assertNotIn("priorityClassName", dep)


class Profile(unittest.TestCase):
    def files(self):
        return [p for p in PROFILE.rglob("*") if p.is_file()]

    def test_files_exist(self):
        for rel in ("README.md", "bootstrap.sh", "cloudflared/deployment.yaml", "cloudflared/namespace.yaml"):
            self.assertTrue((PROFILE / rel).is_file(), rel)
        self.assertTrue(os.access(BOOT, os.X_OK))
        self.assertTrue((ROOT / "scripts/profile_check.sh").is_file())

    def test_no_duplicate_version_strings(self):
        pins = VERSIONS.read_text()
        values = re.findall(r"^[A-Z_]+_(?:VERSION|DIGEST|SHA256)=(\S+)$", pins, flags=re.M)
        values += re.findall(r"^[A-Z_]+_IMAGE=(\S+)$", pins, flags=re.M)
        self.assertGreater(len(values), 8)
        for p in self.files():
            text = p.read_text()
            for v in values:
                self.assertNotIn(v, text, f"{p.name} repeats the pin {v}")
        text = BOOT.read_text()
        self.assertNotRegex(text, r"sha256:[0-9a-f]{64}")
        self.assertNotRegex(text, r"\bv?\d+\.\d+\.\d+\b(?!\.)", "a version number in bootstrap.sh")
        self.assertIn("versions.env", text)

    def test_cloudflared_image_is_pinned_in_versions_env(self):
        self.assertRegex(VERSIONS.read_text(), r"(?m)^CLOUDFLARED_IMAGE=cloudflare/cloudflared:\S+@sha256:[0-9a-f]{64}$")
        self.assertIn("@CLOUDFLARED_IMAGE@", (PROFILE / "cloudflared/deployment.yaml").read_text())

    def test_no_secret_values_and_no_load_balancer(self):
        for p in self.files():
            text = p.read_text()
            self.assertNotRegex(text, r"type:\s*LoadBalancer", p.name)
            self.assertNotRegex(text, r"(?m)^kind:\s*Secret\b", p.name)
            self.assertNotRegex(text, r"eyJ[A-Za-z0-9_-]{20,}", p.name)
            self.assertNotRegex(text, r"(?i)(TUNNEL_TOKEN|password|secret)\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{16,}", p.name)
        dep = (PROFILE / "cloudflared/deployment.yaml").read_text()
        self.assertIn("name: cloudflared-token", dep)
        self.assertIn("secretKeyRef", dep)

    def test_readme_covers_the_founder_steps(self):
        text = (PROFILE / "README.md").read_text()
        for word in ("--context", "--yes", "db-backup-s3", "alerts-targets", "cloudflared-token", "RUN.md",
                     "Teleport", "never runs", "Gateway API", "Secret rotation", "Break-glass"):
            self.assertIn(word, text, word)

    def test_ci_runs_the_proof(self):
        wf = (ROOT / ".github/workflows/profile-byo.yml").read_text()
        for word in ("ubuntu-24.04-arm", "scripts/profile_check.sh", "workflow_dispatch", "schedule:",
                     "plugins/pavedline/templates/infra/**", "permissions:\n  contents: read"):
            self.assertIn(word, wf, word)
        for line in re.findall(r"uses:\s*(\S+)", wf):
            self.assertRegex(line, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
