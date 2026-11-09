import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PLAN_GRAPH = PLUGIN / "scripts/plan_graph.py"
LC = PLUGIN / "scripts/local-cluster"
SINK = LC / "sms-sink/sink.py"

SPEC = """# Spec

## 5. Acceptance tests

- AT-001 (Web app): Given a user, when they sign in, then they see items.
"""
DECISION_5 = "# 0005. Surfaces\n\n- Status: accepted\n\n## Decision\n\nWeb app and API only.\n"
PLAN = """# Wave 1

### Slice 1.1: Sign in
Tests: AT-001
Surfaces: web, api
Branch: slice-1-1
Depends on: none
"""
INTEGRATION = """# Integration wave

Wave: integration

### Slice int.1: Provider test modes
Tests: none
Surfaces: api
Branch: slice-int-1
Depends on: none

### Slice int.2: Real webhooks through the tunnel
Tests: none
Surfaces: api
Branch: slice-int-2
Depends on: int.1
"""


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          cwd=repo, capture_output=True, text=True, check=True)


class IntegrationWaveStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = pathlib.Path(self.tmp)
        git(self.repo, "init", "-q", "-b", "main")
        self.write("docs/spec/SPEC.md", SPEC)
        self.write("decisions/0005-surfaces.md", DECISION_5)
        self.write("docs/plans/2026-11-09-wave-1.md", PLAN)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg)

    def status(self):
        r = subprocess.run([sys.executable, str(PLAN_GRAPH), "status", "--repo", str(self.repo)],
                           capture_output=True, text=True)
        return r, [ln for ln in r.stdout.splitlines() if ln.startswith("integration wave:")]

    def slice_commit(self, sid):
        self.write("f%s.txt" % sid, sid)
        self.commit("Slice %s: done" % sid)

    def test_not_due_before_feature_complete(self):
        self.commit("start")
        r, lines = self.status()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(lines, ["integration wave: not due"])
        self.assertNotIn("feature-complete", r.stdout)

    def test_due_when_feature_complete_without_a_plan(self):
        self.commit("start")
        self.slice_commit("1.1")
        r, lines = self.status()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.splitlines()[0], "feature-complete")
        self.assertEqual(lines, ["integration wave: due"])

    def test_planned_then_done_needs_merged_slices_and_local_evidence(self):
        self.commit("start")
        self.slice_commit("1.1")
        self.write("docs/plans/2026-11-10-integration.md", INTEGRATION)
        self.commit("plan")
        self.assertEqual(self.status()[1], ["integration wave: planned"])
        self.slice_commit("int.1")
        self.slice_commit("int.2")
        self.assertEqual(self.status()[1], ["integration wave: planned"])  # merged, but no evidence line
        self.write("docs/plans/2026-11-10-integration.md",
                   INTEGRATION.replace("Wave: integration\n",
                                       "Wave: integration\nVerified: local — 2026-11-10, webhook accepted through the tunnel\n"))
        self.commit("evidence")
        r, lines = self.status()
        self.assertEqual(lines, ["integration wave: done"])
        self.assertIn("integration wave: done\n", r.stdout)  # the exact string step 12 looks for

    def test_evidence_without_merged_slices_is_not_done(self):
        self.commit("start")
        self.slice_commit("1.1")
        self.write("docs/plans/2026-11-10-integration.md",
                   INTEGRATION.replace("Wave: integration\n", "Wave: integration\nVerified: local - 2026-11-10, ok\n"))
        self.commit("plan")
        self.slice_commit("int.1")
        self.assertEqual(self.status()[1], ["integration wave: planned"])

    def test_a_verified_line_in_a_slice_body_does_not_count(self):
        self.commit("start")
        self.slice_commit("1.1")
        self.write("docs/plans/2026-11-10-integration.md", INTEGRATION + "\nVerified: local - 2026-11-10, ok\n")
        self.commit("plan")
        self.slice_commit("int.1")
        self.slice_commit("int.2")
        self.assertEqual(self.status()[1], ["integration wave: planned"])

    def test_a_wave_line_in_a_slice_body_does_not_count(self):
        self.commit("start")
        self.slice_commit("1.1")
        self.write("docs/plans/2026-11-10-wave-2.md", PLAN.replace("1.1", "2.1").replace("AT-001", "none")
                   + "\nWave: integration\n")
        self.commit("plan")
        self.assertEqual(self.status()[1], ["integration wave: due"])

    def test_plan_template_and_skill_define_the_lines(self):
        readme = (PLUGIN / "templates/docs/plans/README.md").read_text()
        skill = (PLUGIN / "skills/plan-graph/SKILL.md").read_text()
        for text in (readme, skill):
            self.assertIn("Wave: integration", text)
            self.assertIn("Verified: local", text)
            self.assertIn("integration wave: done", text)


class TunnelScript(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "docker.log"
        fake = self.bin / "docker"
        fake.write_text(
            "#!/bin/sh\n"
            'echo "$@" >> "%s"\n'
            'case "$1" in\n'
            '  inspect) echo true ;;\n'
            '  logs) echo "INF |  https://example-words-1234.trycloudflare.com  |" ;;\n'
            "esac\n"
            "exit 0\n" % self.log)
        fake.chmod(0o755)
        self.klog = self.tmp / "kubectl.log"
        kube = self.bin / "kubectl"
        kube.write_text('#!/bin/sh\necho "$@" >> "%s"\ncase "$*" in *jsonpath*) echo api ;; *apply*) cat >/dev/null ;; esac\nexit 0\n' % self.klog)
        kube.chmod(0o755)
        self.env = {**os.environ, "PATH": "%s:%s" % (self.bin, os.environ["PATH"])}
        self.repo = self.tmp / "product"
        self.repo.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_(self, *args):
        return subprocess.run(["bash", str(LC / "tunnel.sh"), *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True)

    def test_refuses_without_the_services_row_and_never_calls_docker(self):
        (self.repo / "SERVICES.md").write_text("| service | what |\n|---|---|\n| Resend | email |\n")
        r = self.run_("acme")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Cloudflare quick tunnel", r.stderr)
        self.assertFalse(self.log.exists())

    def test_refuses_without_a_services_file(self):
        self.assertEqual(self.run_("acme").returncode, 1)
        self.assertFalse(self.log.exists())

    def test_a_commented_template_row_is_not_approval(self):
        shutil.copy(PLUGIN / "templates/SERVICES.md", self.repo / "SERVICES.md")
        self.assertEqual(self.run_("acme").returncode, 1)

    def test_starts_the_pinned_image_on_the_kind_network_and_prints_the_url(self):
        (self.repo / "SERVICES.md").write_text(
            "| service | what |\n|---|---|\n| Cloudflare quick tunnel | testing only, no account, URL changes each start |\n")
        r = self.run_("acme")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("https://example-words-1234.trycloudflare.com", r.stdout)
        self.assertIn("Founder step", r.stdout)
        calls = self.log.read_text()
        self.assertRegex(calls, r"run -d --name pavedline-tunnel --network kind .*cloudflare/cloudflared:[0-9.]+@sha256:[0-9a-f]{64}")
        self.assertIn("http://pavedline-acme-control-plane:30080", calls)
        self.assertIn("--http-host-header tunnel.localtest.me", calls)
        kcalls = self.klog.read_text()
        self.assertIn("--context kind-pavedline-acme", kcalls)
        self.assertIn("apply -f -", kcalls)

    def test_the_tunnel_route_exposes_only_webhooks_and_healthz(self):
        route = (LC / "manifests/tunnel-route.yaml").read_text()
        self.assertIn('hostnames: ["tunnel.localtest.me"]', route)
        self.assertEqual(re.findall(r"value: (\S+?)}", route), ["/webhooks/", "/healthz"])
        self.assertNotIn("value: /v1", route)

    def test_approval_is_case_insensitive_on_the_service_column(self):
        (self.repo / "SERVICES.md").write_text("| cloudflare QUICK tunnel | x |\n")
        self.assertEqual(self.run_("acme").returncode, 0)

    def test_stop_removes_the_container(self):
        r = self.run_("stop")
        self.assertEqual(r.returncode, 0)
        self.assertIn("rm -f pavedline-tunnel", self.log.read_text())
        self.assertEqual(self.run_("stop", "acme").returncode, 0)
        self.assertIn("delete httproute pavedline-tunnel", self.klog.read_text())

    def test_bad_project_and_host_are_refused(self):
        (self.repo / "SERVICES.md").write_text("| Cloudflare quick tunnel | x |\n")
        self.assertEqual(self.run_("Bad_Name").returncode, 2)
        self.assertEqual(self.run_("acme", "--host", "a b;c").returncode, 2)

    def test_services_template_defines_the_row(self):
        text = (PLUGIN / "templates/SERVICES.md").read_text()
        self.assertIn("| Cloudflare quick tunnel |", text)
        for word in ("testing only", "no account", "URL changes at every start"):
            self.assertIn(word, text)


def load_sink():
    spec = importlib.util.spec_from_file_location("sms_sink", SINK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SmsSink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_sink()
        cls.store = cls.mod.Store()
        cls.server = cls.mod.serve("127.0.0.1", 0, cls.store)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.store.clear()

    def call(self, method, path, data=None, ctype=None):
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_twilio_style_form_is_stored_and_listed(self):
        status, body = self.call("POST", "/2010-04-01/Accounts/ACtest/Messages.json",
                                 b"To=%2B15550001&From=%2B15550002&Body=code+123456",
                                 "application/x-www-form-urlencoded")
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "queued")
        status, listed = self.call("GET", "/messages")
        self.assertEqual(status, 200)
        self.assertEqual([(m["to"], m["from"], m["body"]) for m in listed["messages"]],
                         [("+15550001", "+15550002", "code 123456")])

    def test_json_post_keeps_order_and_delete_clears(self):
        for i in (1, 2):
            s, _ = self.call("POST", "/messages", json.dumps({"to": "+1", "body": "m%d" % i}).encode(),
                             "application/json")
            self.assertEqual(s, 201)
        self.assertEqual([m["body"] for m in self.call("GET", "/messages")[1]["messages"]], ["m1", "m2"])
        self.assertEqual(self.call("DELETE", "/messages")[0], 200)
        self.assertEqual(self.call("GET", "/messages")[1]["messages"], [])

    def test_bad_input_is_refused(self):
        self.assertEqual(self.call("POST", "/messages", b'{"to": "+1"}', "application/json")[0], 400)
        self.assertEqual(self.call("POST", "/messages", b"not json", "application/json")[0], 400)
        self.assertEqual(self.call("POST", "/messages", b"[]", "application/json")[0], 400)
        self.assertEqual(self.call("POST", "/nope", b"x")[0], 404)
        self.assertEqual(self.call("POST", "/messages", b"x" * (self.mod.MAX_BODY + 1), "text/plain")[0], 413)
        self.assertEqual(self.call("GET", "/healthz")[1], {"status": "ok"})

    def test_non_ascii_digit_content_length_is_400_and_the_server_lives(self):
        import socket
        host, port = self.server.server_address[:2]
        with socket.create_connection((host, port), timeout=5) as s:
            s.sendall("POST /messages HTTP/1.1\r\nHost: x\r\nContent-Length: \u0662\r\n\r\n".encode())
            self.assertIn(b"400", s.recv(200))
        self.assertEqual(self.call("GET", "/healthz")[0], 200)

    def test_handler_has_a_socket_timeout(self):
        self.assertGreater(self.mod.SOCKET_TIMEOUT, 0)
        self.assertEqual(self.mod.make_handler(self.mod.Store()).timeout, self.mod.SOCKET_TIMEOUT)

    def test_memory_is_bounded(self):
        for i in range(self.mod.MAX_MESSAGES + 5):
            self.store.add("+1", "+2", "m%d" % i)
        msgs = self.store.list()
        self.assertEqual(len(msgs), self.mod.MAX_MESSAGES)
        self.assertEqual(msgs[0]["body"], "m5")


class FakesPins(unittest.TestCase):
    def env(self):
        vals = {}
        for line in (LC / "versions.env").read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                k, _, v = line.partition("=")
                vals[k.strip()] = v.strip()
        return vals

    def test_images_are_pinned_by_digest(self):
        vals = self.env()
        for key in ("MAILPIT_IMAGE", "SMS_SINK_IMAGE", "CLOUDFLARED_IMAGE"):
            self.assertRegex(vals[key], r"^[a-z0-9./-]+:v?[0-9][0-9A-Za-z.-]*@sha256:[0-9a-f]{64}$", key)

    def test_sink_reuses_the_apis_python_pin_and_the_manifest_has_no_other_image(self):
        vals = self.env()
        dockerfile = (PLUGIN / "stacks/nextjs-fastapi/files/services/api/Dockerfile").read_text()
        self.assertIn(vals["SMS_SINK_IMAGE"], dockerfile)
        manifest = (LC / "manifests/fakes.yaml").read_text()
        self.assertEqual(sorted(re.findall(r'image: "(@[A-Z_]+@)"', manifest)), ["@MAILPIT_IMAGE@", "@SMS_SINK_IMAGE@"])

    def test_up_sh_has_a_fakes_flag_and_stays_on_the_kind_context(self):
        up = (LC / "up.sh").read_text()
        self.assertIn("--fakes", up)
        for line in up.splitlines():
            stripped = line.lstrip().removeprefix("| ")
            if stripped.startswith("kubectl "):
                self.assertIn("--context", stripped, line)

    def test_sink_is_stdlib_only(self):
        tree = SINK.read_text()
        imports = set(re.findall(r"^(?:from|import)\s+([a-z_]+)", tree, re.M))
        self.assertTrue(imports <= {"json", "os", "re", "threading", "time", "typing", "uuid", "http", "urllib"}, imports)


if __name__ == "__main__":
    unittest.main()
