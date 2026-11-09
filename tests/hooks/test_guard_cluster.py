import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "plugins" / "pavedline" / "scripts" / "hooks" / "guard_cluster.py"


def run_raw(stdin, ctx=None, path=None):
    env = dict(os.environ)
    env.pop("PAVEDLINE_TEST_KUBE_CONTEXT", None)
    if ctx is not None:
        env["PAVEDLINE_TEST_KUBE_CONTEXT"] = ctx
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env
    )


def run(command, ctx="prod", **kw):
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    return run_raw(json.dumps(event), ctx, **kw)


class ClusterGuardTests(unittest.TestCase):
    def blocked(self, command, ctx="prod", **kw):
        r = run(command, ctx, **kw)
        self.assertEqual(r.returncode, 2, (command, r.stderr))
        self.assertIn("Blocked", r.stderr)

    def allowed(self, command, ctx="prod", **kw):
        r = run(command, ctx, **kw)
        self.assertEqual(r.returncode, 0, (command, r.stderr))

    def test_blocks_delete_on_cloud_context(self):
        self.blocked("kubectl delete ns x")

    def test_blocks_context_flag_override(self):
        self.blocked("kubectl --context prod apply -f x", "kind-pavedline-demo")

    def test_blocks_chained_mutation(self):
        self.blocked("kubectl get pods && kubectl delete ns x")

    def test_blocks_helm_upgrade(self):
        self.blocked("helm upgrade r chart")

    def test_allows_read_only(self):
        for c in ["kubectl get pods", "helm list", "kubectl logs x", "kubectl describe pod x",
                  "kubectl top node", "kubectl explain pod", "kubectl version",
                  "kubectl config view", "helm status r", "helm get values r",
                  "helm template r c", "helm lint c", "kubectl rollout status deploy/x",
                  "argocd app list", "argocd app get x", "ls -la"]:
            with self.subTest(c=c):
                self.allowed(c)

    def test_allows_local_mutation(self):
        self.allowed("kubectl apply -f x", "kind-pavedline-demo")

    def test_every_mutating_verb_blocks(self):
        for v in "apply create delete edit patch replace scale rollout label annotate drain cordon taint set".split():
            with self.subTest(v=v):
                self.blocked(f"kubectl {v} x")
        for v in "install upgrade uninstall rollback".split():
            with self.subTest(v=v):
                self.blocked(f"helm {v} x")

    def test_nested_forms(self):
        for c in ['bash -c "kubectl delete ns x"', "sh -c 'kubectl delete ns x'",
                  'eval "helm upgrade r c"', "echo $(kubectl delete ns x)",
                  "echo `kubectl delete ns x`", 'echo "$(kubectl delete ns x)"',
                  "sudo bash -lc 'kubectl apply -f x'", "(kubectl delete ns x)",
                  "{ kubectl delete ns x; }", "kubectl get pods\nkubectl delete ns x",
                  "bash -c \"bash -c 'kubectl delete ns x'\"",
                  "echo ns | xargs kubectl delete ns"]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_chained_and_piped(self):
        for c in ["true; kubectl apply -f x", "echo y | kubectl delete -f -",
                  "false || kubectl delete ns x", "kubectl get pods & kubectl delete ns x"]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_context_override_forms(self):
        for c in ["kubectl --context prod delete ns x", "kubectl --context=prod delete ns x",
                  "helm --kube-context prod upgrade r c", "helm --kube-context=prod upgrade r c",
                  "kubectl delete ns x --context prod", "kubectl --context kind-other delete ns x"]:
            with self.subTest(c=c):
                self.blocked(c, "kind-pavedline-demo")
        for c in ["kubectl --context kind-pavedline-a delete ns x",
                  "kubectl --context=kind-pavedline-a delete ns x",
                  "helm --kube-context=kind-pavedline-a upgrade r c"]:
            with self.subTest(c=c):
                self.allowed(c, "prod")

    def test_kind_but_not_pavedline_blocks(self):
        self.blocked("kubectl delete ns x", "kind-other")
        self.allowed("kubectl delete ns x", "kind-pavedline-demo")

    def test_kubeconfig_override(self):
        for c in ["kubectl --kubeconfig f delete ns x", "kubectl --kubeconfig=f delete ns x",
                  "KUBECONFIG=f kubectl delete ns x", "export KUBECONFIG=f; kubectl delete ns x",
                  "env KUBECONFIG=f helm upgrade r c"]:
            with self.subTest(c=c):
                self.blocked(c, "kind-pavedline-demo")
        self.allowed("KUBECONFIG=f kubectl --context kind-pavedline-a delete ns x", "prod")
        self.allowed("kubectl --kubeconfig f --context=kind-pavedline-a apply -f x", "prod")

    def test_server_cluster_override_blocks(self):
        for c in ["kubectl --server https://x delete ns y", "kubectl -s https://x delete ns y",
                  "kubectl --cluster prod delete ns y"]:
            with self.subTest(c=c):
                self.blocked(c, "kind-pavedline-demo")

    def test_prefixes(self):
        for c in ["sudo kubectl delete ns x", "env X=1 kubectl delete ns x", "X=1 kubectl delete ns x",
                  "/usr/local/bin/kubectl delete ns x", "kubectl.exe delete ns x",
                  "command kubectl delete ns x", "sudo -u root kubectl delete ns x",
                  "kubectl -n foo delete pod x", "time kubectl delete ns x", "nohup kubectl delete ns x"]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_use_context_to_non_kind_blocks(self):
        self.blocked("kubectl config use-context prod && kubectl get pods", "kind-pavedline-demo")
        self.allowed("kubectl config use-context kind-pavedline-demo")
        self.allowed("kubectl config current-context")

    def test_argocd(self):
        for c in ["argocd app sync x", "argocd app delete x", "argocd app set x --p a=b",
                  "argocd app create x", "argocd app patch x", "argocd app rollback x 1",
                  "argocd app terminate-op x", "argocd proj create p", "argocd proj delete p",
                  "argocd repo add https://r", "argocd repo rm https://r",
                  "argocd cluster add c", "argocd cluster rm c"]:
            with self.subTest(c=c):
                self.blocked(c, "prod")
                self.allowed(c, "kind-pavedline-demo")

    def test_context_lookup_failure_blocks_mutation_only(self):
        self.blocked("kubectl delete ns x", ctx=None, path="/nonexistent")
        self.allowed("kubectl get pods", ctx=None, path="/nonexistent")

    def test_non_bash_and_malformed_input_fail_open(self):
        for stdin in ["", "not json", "[]", json.dumps({"tool_name": "Bash"}),
                      json.dumps({"tool_name": "Bash", "tool_input": {"command": 5}}),
                      json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}})]:
            with self.subTest(stdin=stdin):
                self.assertEqual(run_raw(stdin, "prod").returncode, 0)

    def test_unbalanced_quotes_still_blocks(self):
        self.blocked("kubectl delete ns 'x")

    def test_bootstrap_with_yes_needs_a_kind_context(self):
        for c in ["bash bootstrap.sh --context prod --repo-url u --yes",
                  "sh infra/profiles/byo-kubernetes/bootstrap.sh --context prod --repo-url u --yes",
                  "FOO=1 bash ./bootstrap.sh --repo-url u --yes",
                  "bootstrap.sh --context kind-other --repo-url u --yes",
                  "bootstrap.sh --context=prod --repo-url u --yes"]:
            with self.subTest(c=c):
                self.blocked(c, "kind-pavedline-demo")
        self.allowed("bash bootstrap.sh --context kind-pavedline-byo --repo-url u --yes")
        self.allowed("bash bootstrap.sh --context prod --repo-url u")
        self.allowed("bash bootstrap.sh --context prod --repo-url u --print")

    def test_mutating_tofu_and_terraform_blocked(self):
        for c in ["tofu apply", "terraform apply -auto-approve", "terraform state rm x.y",
                  "tofu destroy", "terraform import a.b id", "tofu taint a.b", "tofu untaint a.b",
                  "terraform state mv a b", "terraform state push f", "tofu state replace-provider a b",
                  "terraform force-unlock id", "tofu workspace delete x",
                  "cd infra && terraform -chdir=x apply", "env X=1 tofu apply"]:
            with self.subTest(c=c):
                self.blocked(c, "kind-pavedline-demo")
                self.assertIn("the founder runs this (step 12)", run(c, "kind-pavedline-demo").stderr)

    def test_read_only_tofu_allowed(self):
        for c in ["tofu init", "tofu validate", "tofu fmt -check", "tofu plan -out p", "terraform show p",
                  "tofu providers", "tofu version", "terraform output", "tofu graph",
                  "terraform state list", "tofu workspace list"]:
            with self.subTest(c=c):
                self.allowed(c)

    def test_more_writing_kubectl_verbs_blocked(self):
        for c in ["kubectl --context prod cp a b", "kubectl cp a pod:/b", "kubectl replace -f x",
                  "kubectl rollout restart deploy/x", "kubectl set image d/x c=i", "kubectl debug pod/x",
                  "kubectl taint node n k=v:NoSchedule", "kubectl drain n", "kubectl cordon n",
                  "kubectl uncordon n", "kubectl label ns x a=b", "kubectl annotate ns x a=b",
                  "kubectl edit cm x", "kubectl apply -k ."]:
            with self.subTest(c=c):
                self.blocked(c)

    def test_restore_drill_printing_form_allowed(self):
        self.allowed("scripts/restore_drill.sh --cloud-context prod --yes-i-am-the-founder")


if __name__ == "__main__":
    unittest.main()
