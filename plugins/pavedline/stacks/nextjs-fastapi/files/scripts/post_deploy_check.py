#!/usr/bin/env python3
"""Run a PR's `Post-deploy check:` lines against the LOCAL kind cluster, in a small allow-listed language. No shell.

    python3 scripts/post_deploy_check.py <project> [--validate-only] [--retries N]   # one check per line on stdin

Each line is parsed with shlex and must be exactly one of:

    http <host> <path> <status>
        GET http://127.0.0.1:8080<path> with the Host header; <host> must end .localtest.me or .localhost
    kubectl-get <namespace> <kind>[/<name>] [--jsonpath={<expr>} [--equals=<value>]]
        kubectl --context kind-pavedline-<project> -n <namespace> get <kind>[/<name>]; kinds: pod deployment service
        httproute cluster job configmap (never secret); --equals needs --jsonpath and compares the trimmed output
    log-event <namespace> <deployment> <event>
        kubectl --context kind-pavedline-<project> -n <namespace> logs deployment/<deployment> --all-pods --since=15m
        (at most 5 MB): passes when one JSON line has "event": "<event>" (docs/observability/EVENTS.md); the log
        text is never printed

Anything else, and any shell metacharacter (; | & $ ( ) < > ` backslash, control characters), is `rejected check`
(exit 2) before ANY line runs. kubectl runs with an empty environment (a sanitised PATH, a temp HOME) and a temporary
kubeconfig that holds only the kind context. Exit 0 all passed, 1 a check failed, 2 rejected.
"""
import argparse
import http.client
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

KINDS = {"pod", "pods", "deployment", "deployments", "service", "services", "httproute", "httproutes", "cluster", "clusters",
         "job", "jobs", "configmap", "configmaps"}
BAD_CHARS = re.compile(r"[;|&$()<>`\\\x00-\x1f\x7f]")
LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
HOST = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,200}[a-z0-9])?$")
NAME = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
PATH = re.compile(r"^/[A-Za-z0-9_./~%:@+=?-]{0,500}$")
# Only status, the replica count, the name and the labels can be read: never env, data, stringData, annotations or a
# pod spec (they can hold secret material, and --equals would be a guessing oracle on them).
_SEG = r"[A-Za-z0-9_]{1,60}(?:\[(?:[0-9]{1,3}|\*)\])?"
JSONPATH = re.compile(r"^--jsonpath=(\{(?:\.items\[(?:[0-9]{1,3}|\*)\])?\.(?:status(?:\.%s)*|spec\.replicas|metadata\.name|metadata\.labels(?:\.[A-Za-z0-9_-]{1,63})?)\})$" % _SEG)
EVENT = re.compile(r"^[a-z][a-z0-9_]{0,60}(\.[a-z][a-z0-9_]{0,60}){1,5}$")
LOG_LINES = "5000"  # per pod
LOG_BYTES = "5000000"  # per pod
EQUALS = re.compile(r"^--equals=([A-Za-z0-9_.:/-]{0,200})$")


MAX_CHECKS = 20
DEFAULT_TOTAL_SECONDS = 300


CHILDREN = []  # running child processes, each in its own process group, killed when a signal arrives


def kill_children():
    for p in CHILDREN:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.wait(timeout=5)
        except Exception:  # noqa: BLE001 (best effort in a signal path)
            pass


def run_child(argv, **kw):
    """subprocess.run, but the child gets its own process group and is registered, so a signal that lands at ANY point
    (even while it is being spawned) kills it before the temporary files are removed."""
    timeout = kw.pop("timeout", None)
    # Signals are held while the child is spawned and registered, so a signal can never land after the fork but before
    # the child is known (it would then survive, still writing into the directories being removed). The child itself
    # starts with an empty signal mask.
    blocked = {signal.SIGTERM, signal.SIGHUP, signal.SIGINT}
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
    try:
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                             preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, set()), **kw)  # noqa: PLW1509
        CHILDREN.append(p)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
    try:
        out, err = p.communicate(timeout=timeout)
    except BaseException:
        kill_children()
        raise
    finally:
        if p in CHILDREN:
            CHILDREN.remove(p)
    return subprocess.CompletedProcess(argv, p.returncode, out, err)


class Rejected(Exception):
    pass


def parse(line):
    if not line.strip() or BAD_CHARS.search(line):
        raise Rejected("empty line or a shell metacharacter")
    try:
        tok = shlex.split(line, posix=True)
    except ValueError as e:
        raise Rejected(str(e))
    if tok[0] == "http" and len(tok) == 4:
        _, host, path, status = tok
        if not HOST.match(host) or not (host.endswith(".localtest.me") or host.endswith(".localhost")):
            raise Rejected("host must end .localtest.me or .localhost")
        if not PATH.match(path):
            raise Rejected("bad path")
        if not re.fullmatch(r"[1-5][0-9][0-9]", status):
            raise Rejected("status must be three digits")
        return ("http", host, path, int(status))
    if tok[0] == "kubectl-get" and len(tok) >= 3:
        ns, res = tok[1], tok[2]
        if not LABEL.match(ns):
            raise Rejected("bad namespace")
        kind, _, name = res.partition("/")
        if kind not in KINDS or (("/" in res) and not NAME.match(name)):
            raise Rejected("kind must be one of: " + ", ".join(sorted(k for k in KINDS if not k.endswith("s"))))
        jsonpath = equals = None
        for flag in tok[3:]:
            m = JSONPATH.match(flag)
            e = EQUALS.match(flag)
            if m and jsonpath is None:
                jsonpath = m.group(1)
            elif e and equals is None:
                equals = e.group(1)
            else:
                raise Rejected("only --jsonpath={...} (.status..., .spec.replicas, .metadata.name, .metadata.labels, optionally under .items[i]) and --equals=<value> are allowed")
        if equals is not None and jsonpath is None:
            raise Rejected("--equals needs --jsonpath")
        return ("kubectl-get", ns, res, jsonpath, equals)
    if tok[0] == "log-event" and len(tok) == 4:
        _, ns, deployment, event = tok
        if not LABEL.match(ns):
            raise Rejected("bad namespace")
        if not LABEL.match(deployment):
            raise Rejected("bad deployment name")
        if not EVENT.match(event):
            raise Rejected("event must be area.what_happened (lowercase snake case)")
        return ("log-event", ns, deployment, event)
    raise Rejected("unknown verb or wrong number of arguments (http <host> <path> <status> | kubectl-get <ns> <kind>[/<name>] ... | log-event <ns> <deployment> <event>)")


def run_http(check, retries):
    _, host, path, want = check
    port = int(os.environ.get("PAVEDLINE_GATEWAY_PORT", "8080"))
    got = None
    for attempt in range(max(1, retries)):
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.putrequest("GET", path, skip_host=True)
            c.putheader("Host", host)
            c.endheaders()
            got = c.getresponse().status
            c.close()
            if got == want:
                return None
        except OSError as e:
            got = str(e)
        if attempt + 1 < retries:
            time.sleep(1)
    return "http %s%s answered %s, not %s" % (host, path, got, want)


def kubeconfig(ctx, workdir):
    r = run_child(["kubectl", "config", "view", "--minify", "--flatten", "--context", ctx], timeout=60)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("could not extract the %s kubeconfig: %s" % (ctx, r.stderr.strip()))
    fd, path = tempfile.mkstemp(prefix="kubeconfig-", dir=workdir)  # mode 0600
    with os.fdopen(fd, "w") as f:
        f.write(r.stdout)
    return path


def run_kubectl(check, ctx, env):
    _, ns, res, jsonpath, equals = check
    argv = ["kubectl", "--context", ctx, "-n", ns, "get", res, "-o", ("jsonpath=" + jsonpath) if jsonpath else "name"]
    r = run_child(argv, env=env, timeout=60, cwd=env["HOME"])
    if r.returncode != 0:
        return "kubectl get %s -n %s failed: %s" % (res, ns, r.stderr.strip()[:200])
    if equals is not None and r.stdout.strip() != equals:
        return "kubectl get %s -n %s %s does not equal the expected value (the observed value is never printed)" % (res, ns, jsonpath)
    return None


POD_PREFIX = re.compile(r"^\[[^\]\s]{1,300}\] ")  # `--all-pods` prefixes each line with [pod/<name>/<container>]


def has_event(text, event):
    for line in text.splitlines():
        line = POD_PREFIX.sub("", line, count=1)
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("event") == event:
            return True
    return False


def run_log_event(check, ctx, env, retries, deadline):
    _, ns, deployment, event = check
    argv = ["kubectl", "--context", ctx, "-n", ns, "logs", "deployment/" + deployment, "--all-pods=true", "--since=15m",
            "--tail=" + LOG_LINES, "--limit-bytes=" + LOG_BYTES]
    problem = None
    for attempt in range(max(1, retries)):
        left = deadline - time.monotonic()
        if left <= 0:
            return problem or "checks timed out (the total time for all checks is capped)"
        try:
            # A log cut at --limit-bytes may end mid-character: decode leniently, never crash the run.
            r = run_child(argv, env=env, timeout=min(60, left), cwd=env["HOME"], errors="replace")
        except subprocess.TimeoutExpired:
            problem = "kubectl logs deployment/%s -n %s timed out" % (deployment, ns)
            continue
        if r.returncode != 0:
            problem = "kubectl logs deployment/%s -n %s failed: %s" % (deployment, ns, r.stderr.strip()[:200])
        elif has_event(r.stdout, event):
            return None
        else:
            problem = "no log line of deployment/%s -n %s has event %s in the last 15 minutes (the log text is never printed)" % (deployment, ns, event)
        if attempt + 1 < retries:
            time.sleep(1)
    return problem


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--retries", type=int, default=10)
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]{0,40}[a-z0-9])?", args.project):
        print("error: bad project name", file=sys.stderr)
        return 2
    lines = sys.stdin.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    checks = []
    for line in lines:
        try:
            checks.append(parse(line))
        except Rejected as e:
            print("rejected check: %r (%s)" % (line, e), file=sys.stderr)
            return 2
    if len(checks) > MAX_CHECKS:
        print("rejected check: too many checks (%d, at most %d)" % (len(checks), MAX_CHECKS), file=sys.stderr)
        return 2
    if not checks:
        print("rejected check: no checks given", file=sys.stderr)
        return 2
    if args.validate_only:
        return 0
    ctx = "kind-pavedline-" + args.project
    # A signal must unwind through `finally`, so the temporary kubeconfig is always removed.
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, lambda n, _f: sys.exit(128 + n))
    deadline = time.monotonic() + float(os.environ.get("PAVEDLINE_CHECK_TIMEOUT", DEFAULT_TOTAL_SECONDS))
    failed = 0
    work = home = None
    # Signals are held while the two temporary directories are created, so one can never arrive between the creation
    # and the `try:`. `work` holds only the kubeconfig; the child's HOME is a different directory, so a cache file a
    # child writes while it is being killed can never keep the credentials directory from being removed.
    blocked = {signal.SIGTERM, signal.SIGHUP, signal.SIGINT}
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
    try:
        work = tempfile.mkdtemp(prefix="pl-check-")
        home = tempfile.mkdtemp(prefix="pl-home-")
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
    try:
        kdir = os.path.dirname(shutil.which("kubectl") or "/usr/bin/kubectl")
        env = {"PATH": ":".join(dict.fromkeys([kdir, "/usr/local/bin", "/usr/bin", "/bin"])), "HOME": home}
        if any(c[0] in ("kubectl-get", "log-event") for c in checks):
            env["KUBECONFIG"] = kubeconfig(ctx, work)
        for c in checks:
            if time.monotonic() >= deadline:
                print("FAILED: checks timed out (the total time for all checks is capped)")
                failed += 1
                break
            if c[0] == "http":
                problem = run_http(c, args.retries)
            elif c[0] == "log-event":
                problem = run_log_event(c, ctx, env, args.retries, deadline)
            else:
                problem = run_kubectl(c, ctx, env)
            print(("ok: " if problem is None else "FAILED: ") + (" ".join(str(x) for x in c if x is not None) if problem is None else problem))
            failed += problem is not None
    finally:
        # Block signals again: the cleanup itself must not be interrupted half way.
        signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
        kill_children()
        for d in (work, home):
            for _ in range(5):
                shutil.rmtree(d, ignore_errors=True)
                if not os.path.exists(d):
                    break
                time.sleep(0.1)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
