import importlib.util
import io
import json
import pathlib
import re
import shutil
import sys
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHART = ROOT / "plugins/pavedline/templates/infra/k8s/addons/alerts"
HELM = shutil.which("helm")
NOW = 1_800_000_000.0


def iso(t):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_checker():
    spec = importlib.util.spec_from_file_location("alerts_checker", CHART / "files/checker.py")
    mod = importlib.util.module_from_spec(spec)
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # never leave a __pycache__ in the shipped template
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def render(*sets, values=None):
    cmd = [HELM, "template", "alerts", str(CHART), "--namespace", "alerts", "--set", "enabled=true"]
    for s in sets:
        cmd += ["--set", s]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return r.stdout


def docs(text):
    return [d for d in re.split(r"(?m)^---\s*$", text) if re.search(r"(?m)^kind: ", d)]


def kind(d):
    return re.search(r"(?m)^kind: (\w+)", d).group(1)


class Fake:
    """A stand-in for the network: scripted HTTP answers and a scripted cluster API."""

    def __init__(self, http=None, api=None, post_status=200, post_fail=None, post_raise=None):
        self.http, self.api, self.post_status = http or {}, api or {}, post_status
        self.post_fail, self.post_raise = post_fail or {}, post_raise
        self.gets, self.posts, self.patches = [], [], []

    def get(self, url, timeout):
        self.gets.append(url)
        v = self.http.get(url, 200)
        if isinstance(v, Exception):
            raise v
        return v

    def post(self, url, body):
        msg = json.loads(body)
        if self.post_raise and msg["check"] in self.post_raise:
            raise self.post_raise[msg["check"]]
        self.posts.append((url, msg))
        return self.post_fail.get(msg["check"], self.post_status)

    def api_get(self, path):
        v = self.api.get(path)
        if isinstance(v, Exception):
            raise v
        return v

    def api_patch(self, path, body):
        self.patches.append((path, body))


@unittest.skipUnless(HELM, "helm is not installed; the chart render tests run in CI")
class AlertsChart(unittest.TestCase):
    def test_it_ships_off_and_renders_nothing_until_enabled(self):
        r = subprocess.run([HELM, "template", "alerts", str(CHART), "--namespace", "alerts"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(docs(r.stdout), [])

    def test_the_chart_renders_a_cronjob_that_runs_the_three_checks(self):
        text = render("checks.endpoints[0].name=web", "checks.endpoints[0].url=https://app.acme.test/healthz",
                      "checks.jobs[0].namespace=api", "checks.jobs[0].name=nightly", "checks.jobs[0].maxLate=26h")
        kinds = [kind(d) for d in docs(text)]
        self.assertIn("CronJob", kinds)
        cfg = json.loads(json.loads(re.search(r"(?m)^  config\.json: (.*)$", text).group(1)))
        self.assertEqual(cfg["endpoints"], [{"name": "web", "url": "https://app.acme.test/healthz"}])
        self.assertEqual(cfg["backup"], {"namespace": "postgres", "scheduledBackup": "db-daily"})
        self.assertEqual(cfg["jobs"][0]["maxLate"], "26h")
        self.assertIn("def check_endpoints", text)
        self.assertIn("def check_backup", text)
        self.assertIn("def check_jobs", text)
        cron = [d for d in docs(text) if kind(d) == "CronJob"][0]
        self.assertIn('schedule: "*/5 * * * *"', cron)
        self.assertRegex(cron, r"image: python:3\.14\.9-slim@sha256:[0-9a-f]{64}")

    def test_schedule_and_thresholds_are_values(self):
        text = render("schedule=*/10 * * * *", "checks.backupMaxAge=12h", "checks.repeatEvery=1h", "checks.endpointTimeout=3s")
        self.assertIn('schedule: "*/10 * * * *"', text)
        cfg = json.loads(json.loads(re.search(r"(?m)^  config\.json: (.*)$", text).group(1)))
        self.assertEqual((cfg["backupMaxAge"], cfg["repeatEvery"], cfg["endpointTimeout"]), ("12h", "1h", "3s"))
        values = (CHART / "values.yaml").read_text()
        for key in ("schedule:", "backupMaxAge:", "repeatEvery:", "endpointTimeout:", "maxLate:", "secretName:"):
            self.assertIn(key, values)
        for tpl in (CHART / "templates").glob("*.yaml"):
            self.assertNotRegex(tpl.read_text(), r"36h|26h|6h|\*/5", tpl.name)

    def test_no_url_value_lives_in_the_chart_and_both_come_from_a_secret(self):
        values = (CHART / "values.yaml").read_text()
        uncommented = "\n".join(l for l in values.splitlines() if not l.strip().startswith("#"))
        self.assertNotRegex(uncommented, r"https?://")
        self.assertIn("endpoints: []", values)
        text = render()
        cron = [d for d in docs(text) if kind(d) == "CronJob"][0]
        for key in ("NOTIFY_URL", "HEARTBEAT_URL"):
            self.assertRegex(cron, rf"name: {key}\n\s+valueFrom: \{{secretKeyRef: \{{name: alerts-targets, key: {key}\}}\}}")
        self.assertNotIn("optional", cron)  # a missing Secret must stop the pod, loudly
        self.assertNotRegex(text, r"https?://hooks|https?://[a-z.]*heartbeat")

    def test_rbac_is_least_privilege(self):
        text = render("checks.jobs[0].namespace=api", "checks.jobs[0].name=nightly", "checks.jobs[0].maxLate=26h")
        roles = [d for d in docs(text) if kind(d) == "Role"]
        self.assertEqual({kind(d) for d in docs(text)} & {"ClusterRole", "ClusterRoleBinding"}, set())
        self.assertNotIn("*", "\n".join(re.findall(r"(?m)^\s+(?:verbs|resources|apiGroups): .*$", text)))
        by_ns = {re.search(r"namespace: (\S+)", d).group(1): d for d in roles if "name: alerts-read" in d}
        self.assertEqual(set(by_ns), {"postgres", "api"})
        self.assertIn("backups", by_ns["postgres"])
        self.assertIn("scheduledbackups", by_ns["postgres"])
        self.assertNotIn("cronjobs", by_ns["postgres"])
        self.assertIn("cronjobs", by_ns["api"])
        self.assertNotIn("backups", by_ns["api"])
        every_verb = set(re.findall(r"verbs: \[([^\]]*)\]", text))
        self.assertTrue(every_verb <= {"get", "list", "get, patch"}, every_verb)
        state = [d for d in roles if "name: alerts-state" in d][0]
        self.assertIn("resourceNames: [alerts-state]", state)
        self.assertIn("verbs: [get, patch]", state)
        for d in roles:
            self.assertNotRegex(d, r"\b(secrets|create|delete|update)\b")

    def test_the_backup_check_and_jobs_in_one_namespace_share_one_role(self):
        text = render("checks.jobs[0].namespace=postgres", "checks.jobs[0].name=x", "checks.jobs[0].maxLate=1h")
        roles = [d for d in docs(text) if kind(d) == "Role" and "namespace: postgres" in d]
        self.assertEqual(len(roles), 1)
        self.assertIn("backups", roles[0])
        self.assertIn("cronjobs", roles[0])

    def test_the_pod_is_locked_down(self):
        cron = [d for d in docs(render()) if kind(d) == "CronJob"][0]
        for s in ("runAsNonRoot: true", "readOnlyRootFilesystem: true", "allowPrivilegeEscalation: false",
                  "drop: [ALL]", "concurrencyPolicy: Forbid", "backoffLimit: 0", "type: RuntimeDefault"):
            self.assertIn(s, cron)

    def test_it_ships_as_an_addon_folder(self):
        self.assertTrue((CHART / "Chart.yaml").is_file())
        self.assertIn("alerts/", (CHART.parent / "README.md").read_text())


class CheckerLogic(unittest.TestCase):
    def setUp(self):
        self.c = load_checker()
        self.env = {"NOTIFY_URL": "http://sink/notify", "HEARTBEAT_URL": "http://sink/heartbeat", "ALERTS_NAMESPACE": "alerts"}
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_main(self, cfg, fake, state=None, now=NOW):
        cfgfile = self.tmp / "config.json"
        cfgfile.write_text(json.dumps(cfg))
        fake.api.setdefault("/api/v1/namespaces/alerts/configmaps/alerts-state", {"data": state or {}})
        out = io.StringIO()
        rc = self.c.main(env=dict(self.env, CHECKS_FILE=str(cfgfile)), now=now, http=fake, api=(fake.api_get, fake.api_patch), out=out)
        return rc, out.getvalue()

    def backup_api(self, phases, sched=True):
        base = "/apis/postgresql.cnpg.io/v1/namespaces/postgres"
        items = [{"metadata": {"name": f"b{i}", "creationTimestamp": iso(NOW - age)},
                  "spec": {"cluster": {"name": "db"}},
                  "status": {"phase": ph, "stoppedAt": iso(NOW - age + 30)}} for i, (ph, age) in enumerate(phases)]
        return {f"{base}/scheduledbackups/db-daily": {"spec": {"cluster": {"name": "db"}}} if sched else None,
                f"{base}/backups": {"items": items}}

    CFG = {"endpoints": [], "backup": {"namespace": "postgres", "scheduledBackup": "db-daily"}, "backupMaxAge": "36h",
           "jobs": [], "repeatEvery": "6h", "endpointTimeout": "5s"}

    def test_all_green_sends_the_heartbeat_and_nothing_else(self):
        fake = Fake(api=self.backup_api([("completed", 3600)]))
        rc, out = self.run_main(dict(self.CFG, endpoints=[{"name": "web", "url": "http://web/ok"}]), fake)
        self.assertEqual(rc, 0)
        self.assertEqual(fake.posts, [])
        self.assertEqual(fake.gets, ["http://web/ok", "http://sink/heartbeat"])

    def test_an_endpoint_that_is_down_or_not_2xx_is_one_message_and_no_heartbeat(self):
        for answer in (503, OSError("connection refused"), 404):
            fake = Fake(http={"http://web/ok": answer}, api=self.backup_api([("completed", 60)]))
            rc, _ = self.run_main(dict(self.CFG, endpoints=[{"name": "web", "url": "http://web/ok"}]), fake)
            self.assertEqual(rc, 0)
            self.assertEqual([p[1]["check"] for p in fake.posts], ["endpoint-0-web"], answer)
            self.assertNotIn("http://sink/heartbeat", fake.gets)
            self.assertEqual(fake.posts[0][0], "http://sink/notify")

    def test_a_backup_that_is_too_old_missing_or_failed_is_reported(self):
        cases = {
            "old": ([("completed", 40 * 3600)], True, "old"),
            "none": ([], True, "no completed backup"),
            "failed newer": ([("failed", 600), ("completed", 7200)], True, "failed"),
            "no scheduledbackup": ([("completed", 60)], False, "does not exist"),
        }
        for name, (phases, sched, word) in cases.items():
            fake = Fake(api=self.backup_api(phases, sched))
            self.run_main(self.CFG, fake)
            self.assertEqual([p[1]["check"] for p in fake.posts], ["backup-db-daily"], name)
            self.assertIn(word, fake.posts[0][1]["message"], name)

    def test_a_failed_backup_older_than_a_good_one_and_a_running_one_are_fine(self):
        fake = Fake(api=self.backup_api([("started", 30), ("completed", 3600), ("failed", 90000)]))
        self.run_main(self.CFG, fake)
        self.assertEqual(fake.posts, [])
        self.assertIn("http://sink/heartbeat", fake.gets)

    def job_api(self, last_success=None, created=NOW - 100000, failed_job=False, exists=True):
        base = "/apis/batch/v1/namespaces/api"
        cj = {"metadata": {"creationTimestamp": iso(created)}, "status": {}}
        if last_success is not None:
            cj["status"]["lastSuccessfulTime"] = iso(last_success)
        jobs = [{"metadata": {"name": "nightly-1", "creationTimestamp": iso(NOW - 500),
                              "ownerReferences": [{"kind": "CronJob", "name": "nightly"}]},
                 "status": {"conditions": [{"type": "Failed", "status": "True"}] if failed_job else []}}]
        return {f"{base}/cronjobs/nightly": cj if exists else None, f"{base}/jobs": {"items": jobs}}

    JOBCFG = {"jobs": [{"namespace": "api", "name": "nightly", "maxLate": "26h"}], "backup": {}}

    def test_a_late_or_failed_or_never_run_job_is_reported(self):
        cases = {
            "late": (self.job_api(last_success=NOW - 30 * 3600), "last succeeded"),
            "never": (self.job_api(last_success=None, created=NOW - 30 * 3600), "never succeeded"),
            "failed": (self.job_api(last_success=NOW - 600, failed_job=True), "failed"),
            "missing": (self.job_api(exists=False), "does not exist"),
        }
        for name, (api, word) in cases.items():
            fake = Fake(api=api)
            self.run_main(self.JOBCFG, fake)
            self.assertEqual([p[1]["check"] for p in fake.posts], ["job-api-nightly"], name)
            self.assertIn(word, fake.posts[0][1]["message"], name)
            self.assertNotIn("http://sink/heartbeat", fake.gets, name)

    def test_an_on_time_job_and_a_brand_new_one_pass(self):
        for api in (self.job_api(last_success=NOW - 3600), self.job_api(last_success=None, created=NOW - 600)):
            fake = Fake(api=api)
            self.run_main(self.JOBCFG, fake)
            self.assertEqual(fake.posts, [])
            self.assertIn("http://sink/heartbeat", fake.gets)

    def test_an_unreadable_cluster_api_is_itself_a_failing_check(self):
        fake = Fake(api={"/apis/postgresql.cnpg.io/v1/namespaces/postgres/scheduledbackups/db-daily": OSError("forbidden")})
        self.run_main(self.CFG, fake)
        self.assertEqual([p[1]["check"] for p in fake.posts], ["backup-db-daily"])
        self.assertIn("cannot read", fake.posts[0][1]["message"])

    def test_a_failing_check_is_not_resent_inside_the_repeat_window_but_is_after_it(self):
        cfg = dict(self.CFG, endpoints=[{"name": "web", "url": "http://web/ok"}])
        api = self.backup_api([("completed", 60)])
        fake = Fake(http={"http://web/ok": 503}, api=api)
        self.run_main(cfg, fake, state={"endpoint-0-web": str(int(NOW - 3600))})
        self.assertEqual(fake.posts, [])
        fake = Fake(http={"http://web/ok": 503}, api=self.backup_api([("completed", 60)]))
        self.run_main(cfg, fake, state={"endpoint-0-web": str(int(NOW - 7 * 3600))})
        self.assertEqual(len(fake.posts), 1)
        self.assertEqual(fake.patches[0][1], {"data": {"endpoint-0-web": str(int(NOW))}})

    def test_a_recovered_check_is_forgotten_so_it_alerts_again_at_once(self):
        fake = Fake(api=self.backup_api([("completed", 60)]))
        self.run_main(self.CFG, fake, state={"endpoint-0-web": str(int(NOW - 10))})
        self.assertEqual(fake.patches[0][1], {"data": {"endpoint-0-web": None}})
        self.assertIn("http://sink/heartbeat", fake.gets)

    def test_missing_targets_and_undelivered_messages_fail_the_run(self):
        for drop in ("NOTIFY_URL", "HEARTBEAT_URL"):
            env = {k: v for k, v in self.env.items() if k != drop}
            self.assertEqual(self.c.main(env=env), 1)
        fake = Fake(http={"http://web/ok": 503}, api=self.backup_api([("completed", 60)]), post_status=500)
        rc, _ = self.run_main(dict(self.CFG, endpoints=[{"name": "web", "url": "http://web/ok"}]), fake)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.patches, [])  # not recorded as sent

    # ---- review fixes ----
    def two_failing(self, **kw):
        cfg = dict(self.CFG, endpoints=[{"name": "a", "url": "http://a/x"}, {"name": "b", "url": "http://b/x"}])
        return cfg, Fake(http={"http://a/x": 503, "http://b/x": 503}, api=self.backup_api([("completed", 60)]), **kw)

    def test_a_failed_delivery_never_causes_a_resend_of_the_ones_already_delivered(self):
        cfg, fake = self.two_failing(post_fail={"endpoint-1-b": 500})
        rc, _ = self.run_main(cfg, fake)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.patches[-1][1], {"data": {"endpoint-0-a": str(int(NOW))}})
        # the next run, with the state that patch wrote, sends only the one that failed
        cfg, fake2 = self.two_failing()
        self.run_main(cfg, fake2, state={"endpoint-0-a": str(int(NOW))})
        self.assertEqual([p[1]["check"] for p in fake2.posts], ["endpoint-1-b"])

    def test_a_delivery_that_raises_is_caught_per_message(self):
        cfg, fake = self.two_failing(post_raise={"endpoint-0-a": OSError("boom http://hooks.acme.test/secret-token")})
        rc, _ = self.run_main(cfg, fake)
        self.assertEqual(rc, 1)
        self.assertEqual([p[1]["check"] for p in fake.posts], ["endpoint-1-b"])
        self.assertEqual(fake.patches[-1][1], {"data": {"endpoint-1-b": str(int(NOW))}})

    def test_one_malformed_value_fails_only_its_own_check(self):
        cfg = dict(self.CFG, endpoints=[{"name": "web", "url": "http://web/ok"}])
        # a non-numeric state value is "never sent"
        fake = Fake(http={"http://web/ok": 503}, api=self.backup_api([("completed", 60)]))
        rc, _ = self.run_main(cfg, fake, state={"endpoint-0-web": "garbage"})
        self.assertEqual((rc, [p[1]["check"] for p in fake.posts]), (0, ["endpoint-0-web"]))
        # a Backup without creationTimestamp: the backup check alerts, the endpoint check still runs
        api = self.backup_api([("completed", 60)])
        api["/apis/postgresql.cnpg.io/v1/namespaces/postgres/backups"]["items"].append(
            {"metadata": {"name": "odd"}, "spec": {"cluster": {"name": "db"}}, "status": {"phase": "completed"}})
        fake = Fake(http={"http://web/ok": 503}, api=api)
        rc, _ = self.run_main(cfg, fake)
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(p[1]["check"] for p in fake.posts), ["backup-db-daily", "endpoint-0-web"])
        self.assertIn("could not evaluate", [p[1] for p in fake.posts if p[1]["check"] == "backup-db-daily"][0]["message"])
        # a malformed job entry and a bad duration fail that job only
        jobs = {"jobs": [{"namespace": "api", "name": "nightly"}, {"namespace": "api", "name": "x", "maxLate": "soon"}], "backup": {}}
        fake = Fake(api=self.job_api(last_success=NOW - 60))
        self.run_main(jobs, fake)
        self.assertEqual(sorted(p[1]["check"] for p in fake.posts), ["job-api-nightly", "job-api-x"])

    def test_rfc3339_with_fractions_offsets_and_z_is_understood(self):
        base = NOW - 3600
        for text in (iso(base), iso(base)[:-1] + ".123456Z", iso(base)[:-1] + "+00:00", iso(base)[:-1] + ".5+00:00"):
            self.assertAlmostEqual(self.c.parse_time(text), base, delta=1, msg=text)
        with self.assertRaises(ValueError):
            self.c.parse_time("yesterday")
        api = self.backup_api([("completed", 60)])
        item = api["/apis/postgresql.cnpg.io/v1/namespaces/postgres/backups"]["items"][0]
        item["metadata"]["creationTimestamp"] = iso(NOW - 60)[:-1] + ".123456Z"
        item["status"]["stoppedAt"] = iso(NOW - 30)[:-1] + ".987Z"
        fake = Fake(api=api)
        self.run_main(self.CFG, fake)
        self.assertEqual(fake.posts, [])
        self.assertIn("http://sink/heartbeat", fake.gets)

    def test_a_slow_endpoint_fails_at_a_total_deadline_and_checks_run_in_parallel(self):
        import threading, time
        gate = threading.Event()
        self.addCleanup(gate.set)
        def slow(url, timeout):
            gate.wait(10)
            return 200
        eps = [{"name": f"s{i}", "url": f"http://s{i}/"} for i in range(5)]
        t0 = time.time()
        out = self.c.check_endpoints({"endpoints": eps, "endpointTimeout": "1s"}, slow)
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(len(out), 5)
        self.assertIn("within 1s", out[0].message)

    def test_endpoint_ids_are_unique_even_when_sanitised_names_collide(self):
        eps = [{"name": "a b", "url": "http://x/"}, {"name": "a-b", "url": "http://x/"}, {"name": "a b", "url": "http://y/"}]
        out = self.c.check_endpoints({"endpoints": eps}, lambda u, t: 503)
        self.assertEqual(len({f.id for f in out}), 3)

    def test_no_url_ever_reaches_a_message_or_the_job_log(self):
        secret = "http://hooks.acme.test/T0K3N"
        def boom(url, timeout):
            raise ValueError(f"bad url {url} {secret}")
        out = self.c.check_endpoints({"endpoints": [{"name": "w", "url": secret}]}, boom)
        self.assertNotIn("T0K3N", out[0].message)
        cfg, fake = self.two_failing(post_raise={"endpoint-0-a": ValueError(f"InvalidURL {secret}")})
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.run_main(cfg, fake)
        self.assertNotIn("T0K3N", err.getvalue())

    def test_redirects_are_not_followed_a_3xx_is_a_failed_delivery(self):
        import http.server, threading
        class H(http.server.BaseHTTPRequestHandler):
            def _do(self):
                healthy = self.path == "/ok"
                self.send_response(200 if healthy else 302)
                if not healthy:
                    self.send_header("Location", "/ok")
                self.send_header("Content-Length", "0")
                self.end_headers()
            do_GET = do_POST = _do
            def log_message(self, *a): pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        url = f"http://127.0.0.1:{srv.server_address[1]}/x"
        h = self.c.Http()
        self.assertEqual(h.post(url, "{}"), 302)
        self.assertEqual(h.get(url, 5), 302)

    def test_duplicate_endpoint_names_are_refused_by_the_chart(self):
        if not HELM:
            self.skipTest("helm")
        with self.assertRaises(AssertionError) as cm:
            render("checks.endpoints[0].name=web", "checks.endpoints[0].url=http://a/",
                   "checks.endpoints[1].name=web", "checks.endpoints[1].url=http://b/")
        self.assertIn("unique", str(cm.exception))

    def test_durations(self):
        self.assertEqual([self.c.parse_duration(x) for x in ("30s", "5m", "36h", "2d")], [30, 300, 129600, 172800])
        with self.assertRaises(ValueError):
            self.c.parse_duration("36")

    def test_the_script_is_standard_library_only(self):
        text = (CHART / "files/checker.py").read_text()
        mods = set(re.findall(r"(?m)^(?:import|from) (\w+)", text))
        self.assertTrue(mods <= set(sys.stdlib_module_names), mods)


if __name__ == "__main__":
    unittest.main()
