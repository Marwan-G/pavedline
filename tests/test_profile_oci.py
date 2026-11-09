import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "plugins/pavedline/templates/infra/profiles/oci-oke"
FIXTURES = ROOT / "tests/fixtures/plan"
CI = ROOT / ".github/workflows/ci.yml"


def tf_text() -> str:
    return "\n".join(p.read_text() for p in sorted(PROFILE.glob("*.tf")))


def blocks(text: str, header_re: str) -> list[str]:
    """Return the brace-balanced body of every block whose header line matches header_re."""
    out = []
    for m in re.finditer(header_re + r"[^\n]*\{", text):
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        out.append(text[m.end():i])
    return out


def run_check(name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROFILE / "plan_check.py"), str(FIXTURES / name)],
        capture_output=True, text=True,
    )


class PlanCheck(unittest.TestCase):
    def test_delete_is_flagged(self):
        r = run_check("delete.json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("oci_objectstorage_bucket.backup", r.stdout)
        self.assertNotIn("oci_core_vcn.this", r.stdout)

    def test_replace_in_both_orders_is_flagged(self):
        for name, addr in (
            ("replace_delete_create.json", "oci_containerengine_cluster.this"),
            ("replace_create_delete.json", "oci_containerengine_node_pool.this"),
        ):
            r = run_check(name)
            self.assertEqual(r.returncode, 1, name)
            self.assertIn(addr, r.stdout)

    def test_create_update_noop_read_pass(self):
        r = run_check("create_update_noop.json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 to destroy, 0 replaced", r.stdout)

    def test_reads_stdin(self):
        data = (FIXTURES / "delete.json").read_text()
        r = subprocess.run([sys.executable, str(PROFILE / "plan_check.py")], input=data, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)

    def test_bad_json_is_not_a_pass(self):
        r = subprocess.run([sys.executable, str(PROFILE / "plan_check.py")], input="nope", capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)

    def test_allow_list_fails_closed(self):
        for name in ("forget.json", "upper.json", "string_actions.json", "deferred.json", "taint_replace.json"):
            self.assertEqual(run_check(name).returncode, 1, name)

    def test_deferred_changes_that_are_clean_still_fail_as_incomplete(self):
        r = run_check("deferred_clean.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("incomplete", r.stdout)

    def test_not_a_plan_is_exit_2_without_a_traceback(self):
        for name in ("empty_object.json", "no_changes_key.json", "changes_not_list.json", "null_entry.json"):
            r = run_check(name)
            self.assertEqual(r.returncode, 2, name)
            self.assertNotIn("Traceback", r.stderr, name)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, name)

    def test_empty_plan_is_clean(self):
        self.assertEqual(run_check("empty_plan.json").returncode, 0)

    def test_only_a_lone_taint_delete_is_allowed(self):
        r = run_check("taint_delete.json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("allowed: taint of a removed node", r.stdout)

    def test_fixtures_are_json(self):
        for p in FIXTURES.glob("*.json"):
            json.loads(p.read_text())


class Hcl(unittest.TestCase):
    def setUp(self):
        self.tf = tf_text()
        self.assertTrue(self.tf, "no .tf files")

    def test_no_cloud_init_anywhere(self):
        for word in ("user_data", "cloud_init", "cloud-init", "node_metadata", "ssh_authorized_keys"):
            self.assertNotIn(word, self.tf)

    def test_every_node_pool_sets_labels_natively_and_taints_through_the_provider(self):
        pools = blocks(self.tf, r'resource "oci_containerengine_node_pool"')
        self.assertTrue(pools)
        for body in pools:
            self.assertIn("initial_node_labels", body)
        self.assertRegex(self.tf, r'resource "kubernetes_node_taint"')
        # The default pools in variables.tf each carry labels and taints.
        variables = (PROFILE / "variables.tf").read_text()
        default = blocks(variables, r'variable "node_pools"')[0]
        self.assertRegex(default, r"labels\s*=")
        self.assertRegex(default, r"taints\s*=")

    def test_every_vault_secret_ignores_content_changes(self):
        secrets = blocks(self.tf, r'resource "oci_vault_secret"')
        self.assertTrue(secrets)
        for body in secrets:
            self.assertRegex(body, r"ignore_changes\s*=\s*\[[^\]]*secret_content")

    def test_vault_feeds_a_kubernetes_secret(self):
        self.assertRegex(self.tf, r'data "oci_secrets_secretbundle"')
        self.assertRegex(self.tf, r'resource "kubernetes_secret(_v1)?"')

    def test_no_ocid_or_region_endpoint_literals(self):
        for p in list(PROFILE.glob("*.tf")) + [PROFILE / "terraform.tfvars.example"]:
            text = p.read_text()
            self.assertNotRegex(text, r"ocid1\.", p.name)
            self.assertNotRegex(text, r"\.oraclecloud\.com", p.name)
            self.assertNotRegex(text, r"\b[a-z]{2}-[a-z]+-\d\b", p.name)

    def test_providers_and_cli_are_pinned_exactly(self):
        v = (PROFILE / "versions.tf").read_text()
        self.assertRegex(v, r'required_version\s*=\s*"[^"]+"')
        for src in ("oracle/oci", "hashicorp/kubernetes"):
            self.assertRegex(v, re.escape(src) + r'"\s*\n\s*version\s*=\s*"= \d+\.\d+\.\d+"')

    def test_no_unused_iam(self):
        self.assertNotIn("oci_identity_dynamic_group", self.tf)
        self.assertNotIn("secret-bundles", self.tf)

    def test_every_iam_policy_statement_block_names_its_consumer(self):
        iam = (PROFILE / "iam.tf").read_text()
        for m in re.finditer(r'resource "oci_identity_policy"', iam):
            self.assertIn("Consumer:", iam[max(0, m.start() - 400):m.start()])

    def test_lock_file_is_committed_with_hashes_for_three_platforms(self):
        lock = (PROFILE / ".terraform.lock.hcl").read_text()
        for prov in ("oracle/oci", "hashicorp/kubernetes"):
            self.assertIn(prov, lock)
        self.assertGreaterEqual(lock.count("h1:"), 2)
        self.assertGreaterEqual(lock.count("zh:"), 6)

    def test_api_cidr_validation_rejects_wide_ranges_and_ipv6(self):
        v = (PROFILE / "variables.tf").read_text()
        body = blocks(v, r'variable "api_allowed_cidrs"')[0]
        self.assertIn("cidrhost", body)
        self.assertRegex(body, r">= 16")

    def test_budget_positive_and_auth_modes_are_variables(self):
        v = (PROFILE / "variables.tf").read_text()
        self.assertRegex(blocks(v, r'variable "budget_amount"')[0], r"> 0")
        self.assertIn('variable "kubernetes_auth_mode"', v)
        self.assertIn("var.kubernetes_auth_mode", (PROFILE / "versions.tf").read_text())
        self.assertNotIn('"security_token",', (PROFILE / "versions.tf").read_text())

    def test_kubernetes_secret_refuses_the_placeholder(self):
        body = blocks(self.tf, r'resource "kubernetes_secret_v1"')[0]
        self.assertIn("precondition", body)
        self.assertIn("placeholder-set-in-console", body)

    def test_plan_and_state_are_ignored_and_called_secret(self):
        ig = (PROFILE / ".gitignore").read_text()
        for pat in ("plan.out", "*.tfstate", "*.tfstate.*"):
            self.assertIn(pat, ig)
        r = (PROFILE / "README.md").read_text()
        self.assertRegex(r, r"plan\.out[^\n]*secret|secret[^\n]*plan\.out")

    def test_backend_is_local_and_holds_no_credentials(self):
        self.assertNotRegex(self.tf, r'backend\s+"(?!local)')
        self.assertNotRegex(self.tf, r"(?i)(access_key|secret_key|private_key)\s*=\s*\"")

    def test_bucket_is_versioned_with_a_lifecycle_rule_and_budget_has_alerts(self):
        self.assertRegex(self.tf, r'versioning\s*=\s*"Enabled"')
        self.assertIn("oci_objectstorage_object_lifecycle_policy", self.tf)
        self.assertIn("oci_budget_budget", self.tf)
        self.assertIn("oci_budget_alert_rule", self.tf)

    def test_arm64_shape_is_a_variable_defaulting_to_ampere(self):
        variables = (PROFILE / "variables.tf").read_text()
        self.assertIn("VM.Standard.A1.Flex", variables)

    def test_only_tfvars_example_is_shipped(self):
        self.assertTrue((PROFILE / "terraform.tfvars.example").exists())
        self.assertEqual(list(PROFILE.glob("*.tfvars")), [])

    def test_sources_name_every_pin_with_a_date(self):
        s = (PROFILE / "SOURCES.md").read_text()
        v = (PROFILE / "versions.tf").read_text()
        for ver in re.findall(r'version\s*=\s*"= (\d+\.\d+\.\d+)"', v):
            self.assertIn(ver, s)
        self.assertRegex(s, r"20\d\d-\d\d-\d\d")
        self.assertIn("OpenTofu", s)
        self.assertRegex(s, r"(?i)business source licen[sc]e")


class SecretBindings(unittest.TestCase):
    def setUp(self):
        self.variables = (PROFILE / "variables.tf").read_text()
        self.example = (PROFILE / "terraform.tfvars.example").read_text()
        self.readme = (PROFILE / "README.md").read_text()

    def test_one_secret_can_carry_several_keys(self):
        body = blocks(self.variables, r'variable "k8s_secret_bindings"')[0]
        self.assertRegex(body, r"keys\s*=\s*map\(string\)")
        self.assertNotRegex(body, r"\bkey\s*=\s*string")
        self.assertNotRegex(body, r"vault_secret\s*=\s*string")
        sec = blocks(self.tf_text_all(), r'resource "kubernetes_secret_v1"')[0]
        self.assertRegex(sec, r"for\s+\w+,\s*\w+\s+in\s+.*keys")

    def test_example_builds_the_secret_the_chart_reads(self):
        self.assertIn("db-backup-s3", self.example)
        self.assertIn("access-key-id", self.example)
        self.assertIn("secret-access-key", self.example)
        self.assertIn("backup-s3-access-key", self.example)
        self.assertIn("backup-s3-secret-key", self.example)
        self.assertNotIn("ACCESS_KEY_ID", self.example)

    def tf_text_all(self):
        return tf_text()

    def test_readme_says_bound_values_pass_through_state(self):
        self.assertNotRegex(self.readme, r"(?i)never passes through Terraform")
        self.assertNotRegex((PROFILE / "iam.tf").read_text(), r"(?i)never passes through Terraform")
        self.assertRegex(self.readme, r"(?i)bound[^\n]*(pass|end)[^\n]*state|state[^\n]*bound")
        self.assertIn("kubectl create secret", self.readme)  # the way to keep a value out of state

    def test_object_storage_service_policy_is_scoped_to_the_backup_bucket(self):
        pol = blocks(tf_text(), r'resource "oci_identity_policy" "object_storage_service"')[0]
        m = re.search(r"manage object-family[^\n]*", pol)
        self.assertIn("where target.bucket.name = '${var.backup_bucket_name}'", m.group(0))

    def test_data_pool_label_and_taint_are_documented_for_the_database_chart(self):
        self.assertIn("workload=data:NoSchedule", self.readme)
        self.assertIn("cluster.nodeSelector", self.readme)
        self.assertIn("cluster.tolerations", self.readme)
        self.assertIn("cluster.nodeSelector", self.example)


class Readme(unittest.TestCase):
    def test_five_founder_steps_in_order(self):
        r = (PROFILE / "README.md").read_text()
        needles = ["oci session authenticate", "tofu init", "tofu plan", "plan_check.py", "tofu apply"]
        pos = []
        for n in needles:
            self.assertIn(n, r)
            pos.append(r.index(n))
        self.assertEqual(pos, sorted(pos))

    def test_state_rules_and_agent_statement(self):
        r = (PROFILE / "README.md").read_text()
        self.assertIn("0 to destroy", r)
        self.assertRegex(r, r"(?i)state rm")
        self.assertRegex(r, r"(?i)nothing here is applied by the agent")


class CiJob(unittest.TestCase):
    def test_profile_oci_job(self):
        ci = CI.read_text()
        self.assertIn("profile-oci:", ci)
        for cmd in ("tofu fmt -check -recursive", "tofu init -backend=false", "tofu validate",
                    "tests.test_profile_oci", "CHECKOV_IMAGE", "-lockfile=readonly"):
            self.assertIn(cmd, ci)
        self.assertEqual(len(re.findall(r"bridgecrew/checkov:", ci)), 0, "one Checkov pin: read it, do not repeat it")


if __name__ == "__main__":
    unittest.main()
