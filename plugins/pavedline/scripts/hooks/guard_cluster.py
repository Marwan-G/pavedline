#!/usr/bin/env python3
"""PreToolUse guard: only the disposable local kind-pavedline-* cluster may be changed."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

KIND_PREFIX = "kind-pavedline-"
TOOLS = {"kubectl", "helm", "argocd"}

KUBECTL_MUTATING = set(
    "apply create delete edit patch replace scale rollout label annotate drain cordon uncordon "
    "taint set run expose autoscale debug exec".split()
)
HELM_MUTATING = {"install", "upgrade", "uninstall", "delete", "rollback"}
ARGOCD_GROUPS = {"app", "proj", "repo", "cluster", "appset", "account", "gpg", "cert"}
ARGOCD_MUTATING = {"sync", "delete", "set", "unset", "create", "patch", "rollback",
                   "terminate-op", "edit", "actions", "update", "add", "rm", "remove",
                   "generate-token", "run"}
ARGOCD_MUTATING_PREFIXES = ("add-", "remove-", "delete-", "set-", "create-", "update-")

CONTEXT_FLAGS = {"--context", "--kube-context"}
KUBECONFIG_FLAGS = {"--kubeconfig"}
SERVER_FLAGS = {"--server", "--cluster", "--kube-apiserver", "--kube-token", "--kube-as-user"}
# Value-taking flags that can precede the verb.
OTHER_VALUE_FLAGS = {"-n", "--namespace", "--user", "--token", "--as", "--as-group",
                     "--request-timeout", "--cache-dir", "--certificate-authority",
                     "--client-certificate", "--client-key", "--tls-server-name"}


def current_context():
    forced = os.environ.get("PAVEDLINE_TEST_KUBE_CONTEXT")
    if forced is not None:
        return forced.strip()
    try:
        r = subprocess.run(["kubectl", "config", "current-context"], capture_output=True,
                           text=True, timeout=10)
    except Exception:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def parse(tool, args):
    """-> (positionals, explicit_context|None, kubeconfig_flag, server_flag)"""
    pos, ctx, kc, srv = [], None, False, False
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a == "--":
            pos.extend(args[i:])
            break
        if a.startswith("--") and "=" in a:
            name, val = a.split("=", 1)
            if name in CONTEXT_FLAGS:
                ctx = val
            elif name in KUBECONFIG_FLAGS:
                kc = True
            elif name in SERVER_FLAGS:
                srv = True
            continue
        if a in CONTEXT_FLAGS:
            ctx = args[i] if i < len(args) else ""
            i += 1
        elif a in KUBECONFIG_FLAGS:
            kc = True
            i += 1
        elif a in SERVER_FLAGS or (tool == "kubectl" and a == "-s"):
            srv = True
            i += 1
        elif a in OTHER_VALUE_FLAGS:
            i += 1
        elif a.startswith("-") and a != "-":
            continue
        else:
            pos.append(a)
    return pos, ctx, kc, srv


def mutating(tool, pos):
    """Is this invocation a cluster mutation? (looks at the first two positionals,
    so an unknown value-taking flag before the verb cannot hide it)"""
    head = pos[:2]
    if tool == "kubectl":
        if pos[:1] == ["rollout"] and pos[1:2] and pos[1] in ("status", "history"):
            return False
        return any(p in KUBECTL_MUTATING for p in head)
    if tool == "helm":
        return any(p in HELM_MUTATING for p in head)
    if len(pos) >= 2 and pos[0] in ARGOCD_GROUPS:
        sub = pos[1]
        return sub in ARGOCD_MUTATING or sub.startswith(ARGOCD_MUTATING_PREFIXES)
    return False


SHELLS = {"bash", "sh", "zsh", "dash"}


def runs_deploy_local(verb, args):
    """Is this `deploy_local.sh` itself or a shell given it as the script?"""
    if verb == "deploy_local.sh":
        return True
    if verb in SHELLS:
        for a in args:
            if a.startswith("-"):
                continue
            return os.path.basename(a).lower() == "deploy_local.sh"
    return False


def kubeconfig_overridden(cmds):
    for cmd in cmds:
        assigns, verb, args = _common.unwrap(cmd)
        if any(a.startswith("KUBECONFIG=") for a in assigns):
            return True
        if verb in ("export", "declare", "typeset", "set") and any(
            a.startswith("KUBECONFIG") for a in args
        ):
            return True
    return False


def check(command):
    """Return a block reason or None."""
    cmds = _common.shell_commands(command)
    kc_env = kubeconfig_overridden(cmds)
    for cmd in cmds:
        _, tool, args = _common.unwrap(cmd)
        if runs_deploy_local(tool, args):
            if kc_env:
                return ("Blocked: `deploy_local.sh` runs with a custom kubeconfig, so the target context is unknown. "
                        "Drop the kubeconfig override.")
            ctx = current_context()
            if not ctx.startswith(KIND_PREFIX):
                shown = ctx or "unknown (kubectl could not report it)"
                return (f"Blocked: `deploy_local.sh` would deploy while the kube context is {shown}. Agents may only "
                        f"change the disposable local cluster ({KIND_PREFIX}*). Switch with "
                        f"`kubectl config use-context {KIND_PREFIX}<project>` first.")
            continue
        if tool not in TOOLS:
            continue
        pos, ctx, kc_flag, srv = parse(tool, args)
        if tool == "kubectl" and pos[:2] == ["config", "use-context"]:
            target = pos[2] if len(pos) > 2 else ""
            if not target.startswith(KIND_PREFIX):
                return (f"Blocked: switching the kube context to {target or '(unknown)'} is not allowed. "
                        f"Only {KIND_PREFIX}* contexts may be used; create one with the pavedline local cluster script.")
            continue
        if not mutating(tool, pos):
            continue
        what = f"{tool} {' '.join(pos[:2])}".strip()
        if srv:
            return (f"Blocked: `{what}` targets a cluster through --server/--cluster, which bypasses the "
                    f"context check. Use --context {KIND_PREFIX}<project> on the local kind cluster.")
        if ctx is None:
            if kc_env or kc_flag:
                return (f"Blocked: `{what}` uses a custom kubeconfig, so the target context is unknown. "
                        f"Add an explicit --context {KIND_PREFIX}<project> or drop the kubeconfig override.")
            ctx = current_context()
        if not ctx.startswith(KIND_PREFIX):
            shown = ctx or "unknown (kubectl could not report it)"
            return (f"Blocked: `{what}` would change cluster context {shown}. Agents may only change the "
                    f"disposable local cluster ({KIND_PREFIX}*). Switch with "
                    f"`kubectl config use-context {KIND_PREFIX}<project>` or pass --context.")
    return None


def main():
    event = _common.read_event()
    if event is None:
        sys.stderr.write("pavedline guard_cluster: empty or invalid hook input; allowing.\n")
        _common.allow()
    ti = event.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if event.get("tool_name") == "Bash" and isinstance(cmd, str):
        reason = check(cmd)
        if reason:
            _common.block(reason)
    _common.allow()


if __name__ == "__main__":
    main()
