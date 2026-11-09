import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LC = ROOT / "plugins/pavedline/scripts/local-cluster"
SCRIPTS = [LC / "up.sh", LC / "verify.sh", LC / "down.sh"]
SKILL = ROOT / "plugins/pavedline/skills/local-cluster/SKILL.md"

KUBECTL_RE = re.compile(r"(^|[\s;&|(`$])kubectl\s")
HELM_CLUSTER_RE = re.compile(r"(^|[\s;&|(`$])helm\s+(install|upgrade|uninstall|status|list|get|test)\b")


def command_lines(path):
    """Logical command lines: joins backslash continuations, drops comments/blank/heredoc-free text."""
    out, buf = [], ""
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        out.append(buf + line)
        buf = ""
    return out


def env_values():
    vals = {}
    for line in (LC / "versions.env").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return vals


class LocalClusterStatic(unittest.TestCase):
    def test_files_exist(self):
        for p in SCRIPTS + [LC / "versions.env", LC / "kind-config.yaml.tpl",
                            LC / "manifests/cnpg-smoke-cluster.yaml", SKILL]:
            self.assertTrue(p.is_file(), str(p))

    def test_versions_pinned(self):
        v = env_values()
        self.assertRegex(v["KIND_NODE_IMAGE"], r"^kindest/node:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}$")
        self.assertEqual(v["ARGOCD_CHART_VERSION"], "10.15.0")
        self.assertEqual(v["CNPG_CHART_VERSION"], "0.29.1")
        # Charts come from OCI registries on ghcr.io, not GitHub release downloads, pinned by version and digest.
        self.assertEqual(v["ARGOCD_CHART"], "oci://ghcr.io/argoproj/argo-helm/argo-cd")
        self.assertEqual(v["CNPG_CHART"], "oci://ghcr.io/cloudnative-pg/charts/cloudnative-pg")
        self.assertRegex(v["ARGOCD_CHART_DIGEST"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(v["CNPG_CHART_DIGEST"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(v["REGISTRY_PORT"], "5001")
        text = (LC / "versions.env").read_text()
        self.assertIn("verified 2026-11-07", text)
        for path in SCRIPTS + [LC / "versions.env", LC / "kind-config.yaml.tpl", LC / "manifests/cnpg-smoke-cluster.yaml"]:
            self.assertNotRegex(path.read_text(), r"(?i)[:=@]latest\b", str(path))

    def test_strict_mode(self):
        for p in SCRIPTS:
            lines = [l for l in p.read_text().splitlines()]
            self.assertTrue(lines[0].startswith("#!"), str(p))
            body = [l for l in lines[1:] if l.strip() and not l.strip().startswith("#")]
            self.assertEqual(body[0].strip(), "set -euo pipefail", str(p))

    def test_syntax(self):
        for p in SCRIPTS:
            r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, p.name + r.stderr)

    def test_cluster_commands_pin_context(self):
        seen = 0
        for p in SCRIPTS:
            for line in command_lines(p):
                if line.startswith(("for ", "command -v")):
                    continue  # tool-presence loop, not a cluster command
                if KUBECTL_RE.search(line):
                    seen += 1
                    self.assertIn("--context", line, f"{p.name}: {line}")
                if HELM_CLUSTER_RE.search(line):
                    seen += 1
                    self.assertIn("--kube-context", line, f"{p.name}: {line}")
        self.assertGreater(seen, 5)

    def test_no_current_context_reliance(self):
        for p in SCRIPTS:
            text = p.read_text()
            self.assertNotIn("use-context", text)
            self.assertNotIn("current-context", text)

    def test_context_name_matches_guard(self):
        for p in SCRIPTS:
            text = p.read_text()
            self.assertIn("kind-pavedline-", text, p.name)
            self.assertIn("pavedline-", text, p.name)

    def test_project_slug_validated(self):
        for p in SCRIPTS:
            text = p.read_text()
            self.assertIn("^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$", text, p.name)
            self.assertIn("exit 2", text, p.name)

    def test_down_only_named_cluster(self):
        text = (LC / "down.sh").read_text()
        self.assertNotIn("delete clusters", text)
        self.assertIn("--all", text)
        self.assertIn("kind-registry", text)
        self.assertRegex(text, r"kind delete cluster --name")

    def test_up_follows_registry_recipe(self):
        text = (LC / "up.sh").read_text()
        for needle in ["kind-registry", "127.0.0.1:${REGISTRY_PORT}", "docker network connect", "hosts.toml",
                       "local-registry-hosting", "/etc/containerd/certs.d", "--wait",
                       '"${ARGOCD_CHART}:${ARGOCD_CHART_VERSION}@${ARGOCD_CHART_DIGEST}"',
                       '"${CNPG_CHART}:${CNPG_CHART_VERSION}@${CNPG_CHART_DIGEST}"', "argocd", "cnpg-system"]:
            self.assertIn(needle, text, needle)
        self.assertIn("docker info", text)
        self.assertNotIn("helm repo", text, "charts are pulled by OCI reference; no classic repo")
        self.assertNotIn("github.io", text)

    def test_renovate_tracks_every_pin(self):
        import json
        env_text = (LC / "versions.env").read_text()
        conf = json.loads((ROOT / "renovate.json").read_text())
        found = {}
        for m in conf["customManagers"]:
            for pattern in m["matchStrings"]:
                py = re.sub(r"\(\?<(\w+)>", r"(?P<\1>", pattern)  # JS named groups -> Python
                hit = re.search(py, env_text)
                self.assertIsNotNone(hit, f"Renovate rule matches nothing: {m['description']}")
                found[m["description"]] = (m["datasourceTemplate"], hit.groupdict())
        v = env_values()
        docker_deps = {g.get("depName"): g for ds, g in found.values() if ds == "docker"}
        for chart in ("ARGOCD", "CNPG"):
            dep = v[f"{chart}_CHART"].removeprefix("oci://")
            self.assertIn(dep, docker_deps, dep)
            self.assertEqual(docker_deps[dep]["currentValue"], v[f"{chart}_CHART_VERSION"])
            self.assertEqual(docker_deps[dep]["currentDigest"], v[f"{chart}_CHART_DIGEST"])

    def test_kind_config(self):
        text = (LC / "kind-config.yaml.tpl").read_text()
        self.assertIn("apiVersion: kind.x-k8s.io/v1alpha4", text)
        # host 8080 reaches the Envoy Gateway data plane through the fixed NodePort 30080; no TLS port until step 12
        self.assertRegex(text, r"containerPort: 30080\b")
        self.assertRegex(text, r"hostPort: 8080\b")
        self.assertNotIn("8443", text)
        self.assertNotIn("30443", text)
        self.assertIn("config_path", text)

    def test_smoke_manifest(self):
        text = (LC / "manifests/cnpg-smoke-cluster.yaml").read_text()
        self.assertIn("apiVersion: postgresql.cnpg.io/v1", text)
        self.assertIn("kind: Cluster", text)
        self.assertIn("name: smoke", text)
        self.assertRegex(text, r"instances: 1\b")
        self.assertIn("size: 1Gi", text)

    def test_verify_waits_on_ready_condition(self):
        text = (LC / "verify.sh").read_text()
        self.assertIn("--for=condition=Ready cluster/smoke", text)
        self.assertIn("argocd-server", text)
        self.assertIn("condition=Available", text)
        self.assertIn("delete", text)

    def test_skill_content(self):
        text = SKILL.read_text()
        for needle in ["colima start --cpu 4 --memory 10", "16 GB", "32 GB", "up.sh", "verify.sh", "down.sh",
                       "kind-pavedline-", "/pavedline:doctor", "real DNS and TLS", "multi-node failure"]:
            self.assertIn(needle, text, needle)
        self.assertTrue(text.startswith("---\nname: local-cluster\n"))

    def test_gateway_and_git_server_pins(self):
        v = env_values()
        text = (LC / "versions.env").read_text()
        self.assertEqual(v["GATEWAY_API_VERSION"], "v1.6.3")
        self.assertRegex(v["GATEWAY_API_STANDARD_SHA256"], r"^[0-9a-f]{64}$")
        self.assertEqual(v["ENVOY_GATEWAY_CHART"], "oci://docker.io/envoyproxy/gateway-helm")
        self.assertRegex(v["ENVOY_GATEWAY_CHART_VERSION"], r"^v\d+\.\d+\.\d+$")
        self.assertRegex(v["ENVOY_GATEWAY_CHART_DIGEST"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(v["GIT_SERVER_BASE_IMAGE"], r"^alpine:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}$")
        self.assertRegex(v["ECHO_IMAGE"], r"^alpine:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}$")
        self.assertIn("verified 2026-11-09", text)
        self.assertIn("compatib", text.lower())
        df = (LC / "git-server/Dockerfile").read_text()
        self.assertRegex(df, r"(?m)^ARG BASE$")
        self.assertIn("FROM ${BASE}", df)
        self.assertIn("git-daemon", df)
        self.assertIn("--base-path=/srv/git", df)
        self.assertIn("--export-all", df)
        self.assertNotIn("latest", df)

    def test_up_installs_gateway_and_git_server(self):
        text = (LC / "up.sh").read_text()
        for needle in ["GATEWAY_API_VERSION", "GATEWAY_API_STANDARD_SHA256", "ENVOY_GATEWAY_CHART",
                       "envoy-gateway-system", "kind-git", "git-server", "docker build", "org.opencontainers.image.base.digest"]:
            self.assertIn(needle, text, needle)

    def test_git_server_is_read_only_and_not_published(self):
        for path in (LC / "up.sh", LC / "git-server/Dockerfile", LC / "verify.sh", LC / "push.sh"):
            self.assertNotIn("receive-pack", path.read_text().replace("git receive-pack", ""), str(path))
        up = (LC / "up.sh").read_text()
        for line in up.splitlines():
            if "docker run" in line and "GIT_NAME" in line:
                self.assertNotRegex(line, r"\s-p\s|--publish", "kind-git must not publish a host port")
        self.assertNotIn("GIT_SERVER_PORT", up)
        self.assertNotIn("GIT_SERVER_PORT", (LC / "versions.env").read_text())
        for t in ("SKILL.md",):
            for skill in (SKILL, ROOT / "plugins/pavedline/skills/gitops/SKILL.md"):
                self.assertNotIn("nothing of value", skill.read_text())
                self.assertNotIn("git://127.0.0.1", skill.read_text())

    def test_push_helper(self):
        push = LC / "push.sh"
        self.assertTrue(push.is_file())
        text = push.read_text()
        self.assertIn("protocol.ext.allow=always", text)
        self.assertIn("ext::docker exec -i kind-git %S /srv/git/", text)
        self.assertIn("^[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?$", text)
        self.assertIn("exit 2", text)
        self.assertIn("set -euo pipefail", text)
        r = subprocess.run(["bash", "-n", str(push)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for bad in ("Bad_Name", "a;b", "../x", ""):
            r = subprocess.run(["bash", str(push), bad], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, bad)
        self.assertIn("push.sh", (LC / "verify.sh").read_text())

    def test_up_rejects_stale_cluster_and_rebuilds_git_image(self):
        text = (LC / "up.sh").read_text()
        self.assertIn("this cluster was created by an older Pavedline; run down.sh <project> then up.sh <project>", text)
        self.assertIn("docker port", text)
        self.assertIn("30080/tcp", text)
        self.assertIn("org.opencontainers.image.base.digest", text)
        df = (LC / "git-server/Dockerfile").read_text()
        self.assertIn("org.opencontainers.image.base.digest", df)

    def test_every_pin_is_tracked_by_renovate(self):
        import json
        conf = json.loads((ROOT / "renovate.json").read_text())
        matchers = [p for m in conf["customManagers"] for p in m["matchStrings"]]
        for name in env_values():
            if name in ("REGISTRY_PORT", "HELM_MIN_VERSION", "GATEWAY_API_STANDARD_SHA256",
                        "ENVOY_GATEWAY_CHART_DIGEST", "ARGOCD_CHART_DIGEST", "CNPG_CHART_DIGEST"):
                continue  # not a pin of its own: a port, a floor, a derived tag, or the digest of a pin matched with its version
            self.assertTrue(any(name in p for p in matchers), f"{name} is not matched by any Renovate customManager")
        for chart in ("ENVOY_GATEWAY",):
            self.assertTrue(any(f"{chart}_CHART_DIGEST" in p for p in matchers), chart)
        self.assertTrue(any("GATEWAY_API_VERSION" in p for m in conf["customManagers"] if m["datasourceTemplate"] == "github-releases" for p in m["matchStrings"]))
        self.assertIn("a Renovate bump fails up.sh's checksum until GATEWAY_API_STANDARD_SHA256 is updated by hand", (LC / "versions.env").read_text())
        # the regexes match the real file
        env_text = (LC / "versions.env").read_text()
        for m in conf["customManagers"]:
            for pattern in m["matchStrings"]:
                self.assertIsNotNone(re.search(re.sub(r"\(\?<(\w+)>", r"(?P<\1>", pattern), env_text), m["description"])

    def test_no_pipe_into_grep_q(self):
        text = (LC / "down.sh").read_text()
        self.assertIn("kind-git", text)

    def test_verify_checks_gateway_route_and_argocd_sync(self):
        text = (LC / "verify.sh").read_text()
        self.assertIn("Programmed", text)
        self.assertIn("HTTPRoute", text)
        self.assertIn("curl", text)
        self.assertIn("127.0.0.1:8080", text)
        self.assertIn("git://kind-git:9418", text)
        self.assertRegex(text, r"Synced")
        for f in ["manifests/gateway-smoke.yaml", "manifests/argocd-git-smoke.yaml"]:
            self.assertTrue((LC / f).is_file(), f)

    def test_skill_mentions_new_pieces(self):
        text = SKILL.read_text()
        for needle in ["kind-git", "Envoy Gateway", "git://kind-git:9418", "push.sh"]:
            self.assertIn(needle, text, needle)

    def test_no_pipe_into_grep_q(self):
        for path in SCRIPTS:
            for line in command_lines(path):
                self.assertNotRegex(line, r"\|\s*grep\s+-\w*q", f"{path.name}: {line}")

    def test_shellcheck_if_available(self):
        import shutil
        if not shutil.which("shellcheck"):
            self.skipTest("skipped: shellcheck not on PATH")
        r = subprocess.run(["shellcheck", "-x", *[p.name for p in SCRIPTS]], capture_output=True, text=True, cwd=LC)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
