"""The three alerts: public endpoints, the newest database backup, scheduled jobs.

Runs as a CronJob. Reads /app/config.json, NOTIFY_URL and HEARTBEAT_URL from the environment, the cluster through the
pod's service account. One JSON message per failing check goes to NOTIFY_URL (at most once per repeatEvery); when every
check passes it GETs HEARTBEAT_URL. Exit 0 = the run completed; exit 1 = it could not (missing configuration, or a
message could not be delivered), so the Job fails loudly. Standard library only.
"""
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

SA = "/var/run/secrets/kubernetes.io/serviceaccount"
API = "https://kubernetes.default.svc"
STATE = "alerts-state"


def parse_duration(text):
    m = re.fullmatch(r"(\d+)([smhd])", str(text).strip())
    if not m:
        raise ValueError(f"bad duration {text!r}; use a number and s, m, h or d (30s, 36h, 2d)")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def parse_time(text):
    """RFC3339 (Kubernetes uses `Z`; fractions and offsets are accepted too) to epoch seconds. ValueError otherwise."""
    if not isinstance(text, str):
        raise ValueError(f"missing or non-text timestamp {text!r}")
    d = datetime.fromisoformat(text.strip())
    if d.tzinfo is None:
        raise ValueError(f"timestamp without a time zone: {text!r}")
    return d.timestamp()


def human(seconds):
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= n:
            return f"{int(seconds // n)}{unit}"
    return f"{int(seconds)}s"


def scrub(text):
    """Never let a URL (a webhook URL is a credential) into a message or a log line."""
    return re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://\S+", "<url>", str(text))


def reason(exc):
    return f"{type(exc).__name__}: {scrub(exc)}"


class Failure:
    def __init__(self, check_id, kind, message):
        self.id, self.kind, self.message = check_id, kind, message


def safely(check_id, kind, fn):
    """Run one check in isolation: a malformed value makes THAT check fail, with a reason, and nothing else."""
    try:
        return fn()
    except Exception as exc:  # any crash is an alert, never silence
        return [Failure(check_id, kind, f"could not evaluate this check: {reason(exc)}")]


def check_endpoints(cfg, http_get):
    """Each endpoint is asked in its own thread; one total deadline (endpointTimeout + 1s) covers them all."""
    eps = cfg.get("endpoints") or []
    try:
        timeout = parse_duration(cfg.get("endpointTimeout", "10s"))
    except ValueError as exc:
        return [Failure("endpoint-config", "endpoint", f"could not evaluate this check: {reason(exc)}")]
    results = {}

    def ask(i, e):
        try:
            results[i] = ("status", http_get(e["url"], timeout))
        except Exception as exc:  # any failure to answer is a failed check
            results[i] = ("error", reason(exc))

    threads = []
    for i, e in enumerate(eps):
        t = threading.Thread(target=ask, args=(i, e), daemon=True)
        t.start()
        threads.append(t)
    end = time.time() + timeout + 1
    for t in threads:
        t.join(max(0.0, end - time.time()))
    out = []
    for i, e in enumerate(eps):
        name = str(e.get("name", i))
        cid = f"endpoint-{i}-" + re.sub(r"[^A-Za-z0-9._-]", "-", name)
        kind, value = results.get(i, ("timeout", None))
        if kind == "timeout":
            out.append(Failure(cid, "endpoint", f"{name} did not answer within {human(timeout)}"))
        elif kind == "error":
            out.append(Failure(cid, "endpoint", f"{name} is unreachable: {value}"))
        elif not 200 <= value < 300:
            note = " (a redirect is not followed; use the final URL)" if 300 <= value < 400 else ""
            out.append(Failure(cid, "endpoint", f"{name} answered {value}{note}"))
    return out


def check_backup(cfg, api_get, now):
    b = cfg.get("backup") or {}
    name = b.get("scheduledBackup")
    if not name:
        return []
    return safely(f"backup-{name}", "backup", lambda: _check_backup(cfg, b, name, api_get, now))


def _check_backup(cfg, b, name, api_get, now):
    ns = b["namespace"]
    cid = f"backup-{name}"
    max_age = parse_duration(cfg.get("backupMaxAge", "36h"))
    try:
        sched = api_get(f"/apis/postgresql.cnpg.io/v1/namespaces/{ns}/scheduledbackups/{name}")
        if sched is None:
            return [Failure(cid, "backup", f"ScheduledBackup {ns}/{name} does not exist")]
        cluster = sched["spec"]["cluster"]["name"]
        items = (api_get(f"/apis/postgresql.cnpg.io/v1/namespaces/{ns}/backups") or {}).get("items", [])
    except Exception as exc:
        return [Failure(cid, "backup", f"cannot read backups in {ns}: {reason(exc)}")]
    mine = [(parse_time(i["metadata"]["creationTimestamp"]), i) for i in items
            if i.get("spec", {}).get("cluster", {}).get("name") == cluster]
    mine.sort(key=lambda p: p[0], reverse=True)
    done = [p for p in mine if p[1].get("status", {}).get("phase") == "completed"]
    if not done:
        return [Failure(cid, "backup", f"no completed backup of cluster {cluster} exists")]
    created, newest_done = done[0]
    newer_failed = [i for t, i in mine if t > created and i.get("status", {}).get("phase") == "failed"]
    if newer_failed:
        return [Failure(cid, "backup", f"backup {newer_failed[0]['metadata']['name']} of cluster {cluster} failed")]
    ts = newest_done.get("status", {}).get("stoppedAt")
    finished = parse_time(ts) if ts else created
    age = now - finished
    if age > max_age:
        return [Failure(cid, "backup", f"the newest completed backup of cluster {cluster} is {human(age)} old (limit {human(max_age)})")]
    return []


def check_jobs(cfg, api_get, now):
    out = []
    for n, j in enumerate(cfg.get("jobs") or []):
        cid = f"job-{j.get('namespace', n)}-{j.get('name', n)}"
        out += safely(cid, "job", lambda j=j, cid=cid: _check_job(j, cid, api_get, now))
    return out


def _check_job(j, cid, api_get, now):
    ns, name = j["namespace"], j["name"]
    max_late = parse_duration(j["maxLate"])
    try:
        cj = api_get(f"/apis/batch/v1/namespaces/{ns}/cronjobs/{name}")
        if cj is None:
            return [Failure(cid, "job", f"CronJob {ns}/{name} does not exist")]
        jobs = (api_get(f"/apis/batch/v1/namespaces/{ns}/jobs") or {}).get("items", [])
    except Exception as exc:
        return [Failure(cid, "job", f"cannot read CronJob {ns}/{name}: {reason(exc)}")]
    mine = [(parse_time(i["metadata"]["creationTimestamp"]), i) for i in jobs
            if any(o.get("kind") == "CronJob" and o.get("name") == name for o in i["metadata"].get("ownerReferences") or [])]
    mine.sort(key=lambda p: p[0], reverse=True)
    if mine and any(c.get("type") == "Failed" and c.get("status") == "True"
                    for c in mine[0][1].get("status", {}).get("conditions") or []):
        return [Failure(cid, "job", f"the last run of {ns}/{name} ({mine[0][1]['metadata']['name']}) failed")]
    last = cj.get("status", {}).get("lastSuccessfulTime")
    if last:
        age = now - parse_time(last)
        if age > max_late:
            return [Failure(cid, "job", f"{ns}/{name} last succeeded {human(age)} ago (limit {human(max_late)})")]
    else:
        born = now - parse_time(cj["metadata"]["creationTimestamp"])
        if born > max_late:
            return [Failure(cid, "job", f"{ns}/{name} has never succeeded (created {human(born)} ago, limit {human(max_late)})")]
    return []


def decide(failures, state, now, repeat_every):
    """Return (to_send, state_patch). A failing check is sent once per repeat window; a passing one is forgotten."""
    to_send, patch = [], {}
    failing = {f.id for f in failures}
    for f in failures:
        try:
            due = now - float(state.get(f.id)) >= repeat_every
        except (TypeError, ValueError):  # no entry, or one that is not a number: treat as never sent
            due = True
        if due:
            to_send.append(f)
    for key in state:
        if key not in failing:
            patch[key] = None
    return to_send, patch


def main(env=os.environ, now=None, http=None, api=None, out=sys.stdout):
    notify, heartbeat = env.get("NOTIFY_URL", ""), env.get("HEARTBEAT_URL", "")
    if not notify or not heartbeat:
        print("error: NOTIFY_URL and HEARTBEAT_URL must both be set (the alerts-targets Secret)", file=sys.stderr)
        return 1
    cfg = json.load(open(env.get("CHECKS_FILE", "/app/config.json")))
    now = time.time() if now is None else now
    h = http or Http()
    http_get, http_post = h.get, h.post
    api_get, api_patch = api if api is not None else (h.api_get, h.api_patch)
    ns = env.get("ALERTS_NAMESPACE", "alerts")
    failures = check_endpoints(cfg, http_get)
    failures += check_backup(cfg, api_get, now)
    failures += check_jobs(cfg, api_get, now)
    try:
        cm = api_get(f"/api/v1/namespaces/{ns}/configmaps/{STATE}") or {}
    except Exception as exc:
        print(f"warning: cannot read {STATE}: {exc}; every failing check will be sent", file=sys.stderr)
        cm = {}
    state = cm.get("data") or {}
    to_send, patch = decide(failures, state, now, parse_duration(cfg.get("repeatEvery", "6h")))
    delivered_all = True
    try:
        for f in to_send:
            body = json.dumps({"check": f.id, "kind": f.kind, "status": "failing", "message": f.message,
                               "text": f"[alert] {f.id}: {f.message}"})
            try:
                status = http_post(notify, body)
            except Exception as exc:  # the text of a URL error can contain the URL: print the class only
                print(f"error: could not deliver {f.id} to the notify URL ({type(exc).__name__})", file=sys.stderr)
                delivered_all = False
                continue
            if not 200 <= status < 300:
                print(f"error: the notify URL answered {status} for {f.id}", file=sys.stderr)
                delivered_all = False
                continue
            patch[f.id] = str(int(now))  # recorded for every message that went out, whatever happens to the rest
            print(f"notified {f.id}: {f.message}", file=out)
    finally:
        if patch:
            try:
                api_patch(f"/api/v1/namespaces/{ns}/configmaps/{STATE}", {"data": patch})
            except Exception as exc:  # the messages are out; a lost state only means a repeat later
                print(f"warning: cannot write {STATE}: {reason(exc)}", file=sys.stderr)
    if not delivered_all:
        return 1
    if not failures:
        try:
            status = http_get(heartbeat, 15)
        except Exception as exc:
            print(f"error: could not ping the heartbeat URL ({type(exc).__name__})", file=sys.stderr)
            return 1
        if not 200 <= status < 300:
            print(f"error: the heartbeat URL answered {status}", file=sys.stderr)
            return 1
        print("all checks passed; heartbeat sent", file=out)
    else:
        print(f"{len(failures)} check(s) failing; no heartbeat", file=out)
    return 0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # a 3xx surfaces as an HTTPError: it is a status, not a hop to follow


_OPENER = urllib.request.build_opener(_NoRedirect)


class Http:
    """Plain HTTP for the endpoint checks, the notify POST and the heartbeat; the cluster API with the pod's token."""

    @staticmethod
    def get(url, timeout):
        try:
            with _OPENER.open(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    @staticmethod
    def post(url, body):
        req = urllib.request.Request(url, data=body.encode(), method="POST", headers={"Content-Type": "application/json"})
        try:
            with _OPENER.open(req, timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def _api(self, method, path, body=None):
        token = open(f"{SA}/token").read().strip()
        ctx = ssl.create_default_context(cafile=f"{SA}/ca.crt")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/merge-patch+json"
        req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def api_get(self, path):
        return self._api("GET", path)

    def api_patch(self, path, body):
        return self._api("PATCH", path, body)


if __name__ == "__main__":
    sys.exit(main())
