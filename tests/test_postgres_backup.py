import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK = ROOT / "plugins/pavedline/stacks/nextjs-fastapi"
CHART = PACK / "files/infra/k8s/apps/postgres"
DRILL = PACK / "files/scripts/restore_drill.sh"
HELM = shutil.which("helm")


def render(*values, sets=()):
    cmd = [HELM, "template", "db", str(CHART), "--namespace", "postgres", "-f", str(CHART / "values.yaml")]
    for v in values:
        cmd += ["-f", str(CHART / v)]
    for s in sets:
        cmd += ["--set", s]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return r.stdout


def docs(text):
    """Split rendered YAML into {kind: document text}."""
    out = {}
    for d in re.split(r"(?m)^---\s*$", text):
        m = re.search(r"(?m)^kind: (\w+)", d)
        if m:
            out.setdefault(m.group(1), []).append(d)
    return out


@unittest.skipUnless(HELM, "helm is not installed; the chart render tests run in CI")
class PostgresBackupChart(unittest.TestCase):
    REAL = ("backup.enabled=true", "backup.objectStore.endpointURL=https://s3.acme.test",
            "backup.objectStore.destinationPath=s3://acme-prod-db/db")

    def test_production_has_three_instances_anti_affinity_and_backups_once_real_values_are_set(self):
        d = docs(render("values-production.yaml", sets=self.REAL))
        cluster = d["Cluster"][0]
        self.assertRegex(cluster, r"(?m)^  instances: 3$")
        self.assertIn("enablePodAntiAffinity: true", cluster)
        self.assertIn("podAntiAffinityType: required", cluster)
        self.assertRegex(cluster, r"barman-cloud\.cloudnative-pg\.io")
        self.assertIn("isWALArchiver: true", cluster)
        self.assertIn("barmanObjectName: db-backups", cluster)
        store = d["ObjectStore"][0]
        self.assertIn("apiVersion: barmancloud.cnpg.io/v1", store)
        self.assertRegex(store, r'retentionPolicy: "30d"')
        self.assertIn("destinationPath:", store)
        self.assertIn("endpointURL:", store)
        self.assertIn("name: db-backup-s3", store)
        sched = d["ScheduledBackup"][0]
        self.assertIn("method: plugin", sched)
        self.assertIn("name: barman-cloud.cloudnative-pg.io", sched)
        self.assertIn("immediate: true", sched)
        self.assertRegex(sched, r'schedule: "0 0 2 \* \* \*"')

    def test_staging_and_production_ship_backups_off_with_the_placeholder_block_until_step_12(self):
        for env in ("staging", "production"):
            text = (CHART / f"values-{env}.yaml").read_text()
            self.assertRegex(text, r"(?m)^backup:\n  enabled: false$", env)
            self.assertIn("example", text)  # the placeholders stay, step 12 replaces them
            self.assertIn("step 12", text)
            d = docs(render(f"values-{env}.yaml"))
            self.assertNotIn("ObjectStore", d)
            self.assertNotIn("ScheduledBackup", d)
            self.assertNotIn("plugins:", d["Cluster"][0])
            self.assertIn("podAntiAffinityType: required", d["Cluster"][0])

    def test_enabled_backups_that_point_at_a_placeholder_refuse_to_render(self):
        for env in ("staging", "production"):
            with self.assertRaises(AssertionError) as cm:
                render(f"values-{env}.yaml", sets=("backup.enabled=true",))
            self.assertIn("step 12", str(cm.exception), env)
        for sets in (
            ("backup.enabled=true", "backup.objectStore.endpointURL=https://s3.example.com",
             "backup.objectStore.destinationPath=s3://acme-prod-db/db"),
            ("backup.enabled=true", "backup.objectStore.endpointURL=https://s3.acme.test",
             "backup.objectStore.destinationPath=s3://example-prod-backups/db"),
        ):
            with self.assertRaises(AssertionError) as cm:
                render(sets=sets)
            self.assertIn("placeholder", str(cm.exception))
            self.assertIn("step 12", str(cm.exception))

    def test_every_common_placeholder_spelling_is_refused(self):
        for bad in ("https://s3.changeme.io", "https://<s3 endpoint>", "https://s3.TODO", "https://REPLACE-ME", "https://S3.Example.COM"):
            with self.assertRaises(AssertionError, msg=bad) as cm:
                render(sets=("backup.enabled=true", f"backup.objectStore.endpointURL={bad}",
                             "backup.objectStore.destinationPath=s3://acme-prod-db/db"))
            self.assertIn("placeholder", str(cm.exception), bad)
        with self.assertRaises(AssertionError):
            render(sets=("backup.enabled=true", "backup.objectStore.endpointURL=https://s3.acme.test",
                         "backup.objectStore.destinationPath=s3://<bucket>/db"))
        with self.assertRaises(AssertionError):
            render(sets=("backup.enabled=true", "backup.objectStore.endpointURL=", "backup.objectStore.destinationPath=s3://acme-prod-db/db"))

    def test_a_real_name_that_merely_contains_a_placeholder_word_renders(self):
        for bucket in ("todolist-backups", "replacement-parts-db", "exampleton-prod"):
            d = docs(render(sets=("backup.enabled=true", "backup.objectStore.endpointURL=https://s3.acme.test",
                                  f"backup.objectStore.destinationPath=s3://{bucket}/db")))
            self.assertIn(bucket, d["ObjectStore"][0])
        for bad in ("https://s3.example.org", "https://example.com", "https://x.test/CHANGEME", "https://x.test/Todo"):
            with self.assertRaises(AssertionError, msg=bad):
                render(sets=("backup.enabled=true", f"backup.objectStore.endpointURL={bad}",
                             "backup.objectStore.destinationPath=s3://acme-prod-db/db"))

    def test_node_selector_and_tolerations_render_into_the_cluster_affinity(self):
        text = render("values-production.yaml", sets=(
            "cluster.nodeSelector.workload=data",
            "cluster.tolerations[0].key=workload", "cluster.tolerations[0].operator=Equal",
            "cluster.tolerations[0].value=data", "cluster.tolerations[0].effect=NoSchedule"))
        cluster = docs(text)["Cluster"][0]
        self.assertRegex(cluster, r"(?m)^  affinity:\n(?:    .*\n)*?    nodeSelector:\n      workload: data$")
        self.assertRegex(cluster, r"(?m)^    tolerations:\n      - effect: NoSchedule\n        key: workload\n        operator: Equal\n        value: data$")
        self.assertIn("podAntiAffinityType: required", cluster)
        # a single instance has no anti-affinity but still honours the data pool
        one = docs(render(sets=("cluster.nodeSelector.workload=data",)))["Cluster"][0]
        self.assertIn("nodeSelector:", one)
        self.assertNotIn("enablePodAntiAffinity", one)

    def test_node_selector_and_tolerations_are_empty_by_default(self):
        for values in ((), ("values-local.yaml",), ("values-production.yaml",)):
            cluster = docs(render(*values))["Cluster"][0]
            self.assertNotIn("nodeSelector", cluster)
            self.assertNotIn("tolerations", cluster)

    def test_enabled_backups_need_a_credentials_secret_name(self):
        with self.assertRaises(AssertionError) as cm:
            render(sets=self.REAL + ("backup.objectStore.credentialsSecret=",))
        self.assertIn("credentialsSecret", str(cm.exception))
        self.assertIn("step 12", str(cm.exception))

    def test_real_looking_endpoint_and_secret_render(self):
        d = docs(render(sets=self.REAL))
        self.assertIn("https://s3.acme.test", d["ObjectStore"][0])
        self.assertIn("ScheduledBackup", d)

    def test_default_and_local_values_render_no_backup_objects(self):
        for values in ((), ("values-local.yaml",)):
            text = render(*values)
            d = docs(text)
            self.assertNotIn("ObjectStore", d)
            self.assertNotIn("ScheduledBackup", d)
            self.assertNotIn("plugins:", d["Cluster"][0])
            self.assertNotIn("barman", text)

    def test_enabled_backup_without_an_endpoint_fails_to_render(self):
        with self.assertRaises(AssertionError) as cm:
            render(sets=("backup.enabled=true",))
        self.assertIn("destinationPath is required", str(cm.exception))

    def test_antiaffinity_is_a_value_and_defaults_to_required(self):
        self.assertIn("podAntiAffinityType: required", render(sets=("cluster.instances=3",)))
        self.assertIn("podAntiAffinityType: preferred", render(sets=("cluster.instances=3", "cluster.antiAffinity=preferred")))

    def test_the_full_check_overlay_is_production_shaped_and_local(self):
        overlay = PACK / "example-full/infra/k8s/apps/postgres/values-local.yaml"
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(CHART, tmp / "postgres")
        shutil.copy(overlay, tmp / "postgres/values-local.yaml")
        r = subprocess.run([HELM, "template", "db", str(tmp / "postgres"), "--namespace", "postgres",
                            "-f", str(tmp / "postgres/values.yaml"), "-f", str(tmp / "postgres/values-local.yaml")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = docs(r.stdout)
        self.assertRegex(d["Cluster"][0], r"(?m)^  instances: 3$")
        self.assertIn("seaweedfs-s3.seaweedfs", d["ObjectStore"][0])
        self.assertIn("ScheduledBackup", d)


class RestoreDrillScript(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = self.tmp / "calls.log"
        fake = self.tmp / "bin/kubectl"
        fake.parent.mkdir()
        fake.write_text('#!/bin/sh\necho "kubectl $*" >> "%s"\nexit 1\n' % self.log)
        fake.chmod(0o755)

    def run_drill(self, *args):
        env = dict(os.environ, PATH=f"{self.tmp / 'bin'}:{os.environ['PATH']}")
        return subprocess.run(["bash", str(DRILL), *args], capture_output=True, text=True, env=env, timeout=60)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_syntax_and_strict_mode(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(DRILL)]).returncode, 0)
        body = [l for l in DRILL.read_text().splitlines()[1:] if l.strip() and not l.strip().startswith("#")]
        self.assertEqual(body[0].strip(), "set -euo pipefail")
        self.assertTrue(os.access(DRILL, os.X_OK))

    def test_refuses_a_target_equal_to_the_source_before_any_kubectl_call(self):
        r = self.run_drill("ci", "--source", "db", "--target", "db")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("is the source cluster", r.stderr)
        self.assertEqual(self.calls(), "")

    def test_refuses_a_non_kind_context_before_any_kubectl_call(self):
        for ctx in ("prod-cluster", "kind-other", "pavedline-ci", "kind-pavedline"):
            r = self.run_drill("--context", ctx)
            self.assertEqual(r.returncode, 2, ctx + r.stderr)
            self.assertIn("refusing context", r.stderr)
        self.assertEqual(self.calls(), "")

    def test_a_cloud_context_needs_the_founder_flag_and_only_prints(self):
        r = self.run_drill("--cloud-context", "oke-prod")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.calls(), "")
        r = self.run_drill("--cloud-context", "oke-prod", "--yes-i-am-the-founder")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NOTHING was run", r.stdout)
        self.assertIn("--context oke-prod", r.stdout)
        self.assertEqual(self.calls(), "")

    def test_a_kind_looking_context_that_is_not_a_kind_node_is_refused(self):
        r = self.run_drill("ci")  # the fake kubectl fails every call, so no kind control-plane node is found
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not point at the kind node", r.stderr)
        mutating = re.compile(r"kubectl .* (apply|create|delete|patch|exec|replace|scale)\b")
        self.assertNotRegex(self.calls(), mutating)

    def test_a_failing_target_precheck_aborts_instead_of_meaning_absent(self):
        # a kubectl whose "get cluster db-restore" fails with something other than NotFound must stop the drill
        fake = self.tmp / "bin/kubectl"
        fake.write_text(r'''#!/bin/sh
echo "kubectl $*" >> "%s"
case "$*" in
  *"get nodes"*) echo node/pavedline-ci-control-plane ;;
  *"get cluster db-restore"*) echo "Unable to connect to the server: net/http: TLS handshake timeout" >&2; exit 1 ;;
  *"get cluster db"*) echo db ;;
  *) exit 0 ;;
esac
''' % self.log)
        r = self.run_drill("ci")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("RESTORE DRILL FAIL", r.stdout)
        self.assertIn("could not tell whether cluster db-restore exists", r.stderr)
        self.assertNotRegex(self.calls(), r"kubectl .* (apply|create|delete) ")

    def test_the_cloud_plan_quotes_the_context(self):
        r = self.run_drill("--cloud-context", "x$(touch pwned)y z", "--yes-i-am-the-founder")
        self.assertEqual(r.returncode, 0, r.stderr)
        quoted = subprocess.run(["bash", "-c", 'printf %q "$1"', "_", "x$(touch pwned)y z"], capture_output=True, text=True).stdout
        self.assertIn("--context " + quoted + " ", r.stdout)
        self.assertNotIn("--context x$(touch pwned)y z", r.stdout)
        self.assertNotIn("$K", r.stdout)  # the plan uses a quoting-safe shell function, not an unquoted string

    def test_bad_usage_exits_2(self):
        for args in (["--bogus"], [], ["ci", "extra"], ["ci", "--timeout", "abc"], ["Bad_Name"]):
            self.assertEqual(self.run_drill(*args).returncode, 2, args)

    def test_structure_writes_a_marker_and_must_read_it_back(self):
        text = DRILL.read_text()
        # a random marker is written to the source, as the owner, through the direct read-write service
        self.assertRegex(text, r"MARKER=.*/dev/urandom")
        self.assertIn("-rw", text)
        self.assertIn("app_owner", text)
        self.assertIn("INSERT INTO pavedline_restore_drill", text)
        # the backup goes through the plugin and must complete
        self.assertIn("method: plugin", text)
        self.assertIn("completed", text)
        # the backup's last WAL segment is closed and archived BEFORE the restore (a standby backup ends in an unarchived one)
        self.assertIn("pg_switch_wal()", text)
        self.assertLess(text.index("pg_switch_wal()"), text.index("creating the restore cluster"))
        self.assertIn("pg_stat_archiver", text)
        # a NEW cluster is recovered from the object store, and read back from THAT cluster
        self.assertIn("recovery:", text)
        self.assertIn("serverName: ${SOURCE}", text)
        self.assertRegex(text, r'k exec -c postgres "\$\{TARGET\}-1" -- psql')
        # PASS is printed only after the read-back equals the marker; a mismatch or an empty read fails
        self.assertRegex(text, r'if \[ "\$GOT" != "\$MARKER" \]; then\n  fail')
        self.assertLess(text.index('"$GOT" != "$MARKER"'), text.index("RESTORE DRILL PASS"))
        self.assertEqual(text.count("RESTORE DRILL PASS"), 1)  # printed in one place only, after the comparison
        # every wait has a time limit
        self.assertIn('--timeout="${TIMEOUT}s"', text)
        self.assertIn("did not complete within ${TIMEOUT}s", text)
        # the restore cluster never archives into the live backups and is cleaned up
        restore = text.split("kind: Cluster", 1)[1].split("YAML", 1)[0]
        self.assertNotIn("plugins:", restore)
        self.assertIn('k delete cluster "$TARGET"', text)

    def test_the_drill_ships_with_the_api_surface(self):
        self.assertIn("scripts/restore_drill.sh", (PACK / "pack.yaml").read_text())


if __name__ == "__main__":
    unittest.main()
