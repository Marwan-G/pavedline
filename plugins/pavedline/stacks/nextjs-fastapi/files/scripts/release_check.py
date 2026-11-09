#!/usr/bin/env python3
"""Release evidence for promoting a merge commit to staging or production (spec 11.5, step 2).

    python3 scripts/release_check.py --sha <merge sha> [--repo OWNER/REPO] [--app NAME ...]

Run from the product repository (it reads infra/k8s/apps/*/values-staging.yaml names). Uses the GitHub CLI (`gh`),
read-only. Exit 0 only if all of this holds; every failure is printed:

  1. a CI run exists for the sha, every finished run concluded success (or skipped, by a path filter), at least one
     succeeded, and none is still running;
  2. the squash commit message carries no skip-CI marker (a marker builds nothing, so nothing would be verified);
  3. the image bump commit(s) for the sha exist and write an image DIGEST (sha256:<64 hex>, not the all-zero
     placeholder) with no mutable tag beside it. An app whose paths the change did not touch has no bump commit;
     name the apps that must have one with --app.
"""
import argparse
import base64
import json
import pathlib
import re
import subprocess
import sys

MARKERS = ("[skip ci]", "[ci skip]", "[no ci]", "[skip actions]", "[actions skip]", "***no_ci***",
           "skip-checks: true", "skip-checks:true")
DIGEST_RE = re.compile(r'^\s*digest:\s*["\']?(\S+?)["\']?\s*(#.*)?$', re.M)
TAG_RE = re.compile(r'^\s*tag:\s*\S', re.M)
ZERO = "sha256:" + "0" * 64


def gh(args):
    """Run gh, return parsed JSON; raise RuntimeError with gh's message on failure."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("gh %s failed: %s" % (" ".join(args[:2]), (r.stderr or r.stdout).strip()))
    try:
        return json.loads(r.stdout)
    except ValueError as e:
        raise RuntimeError("gh %s returned something that is not JSON: %s" % (" ".join(args[:2]), e))


def check_runs(sha, repo_args):
    problems = []
    runs = gh(["run", "list", "--commit", sha, "--limit", "100", "--json", "name,status,conclusion", *repo_args])
    if not runs:
        return ["no CI run exists for %s (a skip-CI marker, a path filter or a disabled workflow builds nothing)" % sha[:7]]
    succeeded = 0
    for run in runs:
        if run.get("status") != "completed":
            problems.append("CI run %s is %s, not finished" % (run.get("name"), run.get("status")))
        elif run.get("conclusion") == "success":
            succeeded += 1
        elif run.get("conclusion") != "skipped":
            problems.append("CI run %s concluded %s" % (run.get("name"), run.get("conclusion")))
    if not succeeded and not problems:
        problems.append("no CI run for %s concluded success (all were skipped)" % sha[:7])
    return problems


def check_message(sha, repo):
    msg = gh(["api", "repos/%s/commits/%s" % (repo, sha)]).get("commit", {}).get("message", "")
    return ["the commit message carries a skip-CI marker (%s): nothing was built, so nothing is verified" % m
            for m in MARKERS if m in msg.lower()]


def check_bumps(sha, repo, apps, required):
    problems = []
    found = 0
    for app in apps:
        path = "infra/k8s/apps/%s/values-staging.yaml" % app
        commits = gh(["api", "repos/%s/commits?path=%s&per_page=100" % (repo, path)])
        bumps = [c for c in commits if ("for %s" % sha[:7]) in c.get("commit", {}).get("message", "")]
        if not bumps:
            if app in required:
                problems.append("no image bump commit for %s touches %s" % (sha[:7], path))
            continue
        found += 1
        content = gh(["api", "repos/%s/contents/%s?ref=%s" % (repo, path, bumps[0]["sha"])])
        text = base64.b64decode(content.get("content", "")).decode("utf-8", "replace") if content.get("encoding") == "base64" else ""
        m = DIGEST_RE.search(text)
        digest = m.group(1) if m else ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            problems.append("%s at the bump commit has no image digest (got %r); a tag is mutable, only a digest is promoted" % (path, digest or "none"))
        elif digest == ZERO:
            problems.append("%s still holds the all-zero placeholder digest" % path)
        if TAG_RE.search(text):
            problems.append("%s has an image tag beside the digest; staging and production run the digest only" % path)
    if not found and not problems:
        problems.append("no image bump commit for %s exists (CI's tag-bump job has not run, or the change touched no app)" % sha[:7])
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sha", required=True, help="the merge (squash) commit sha")
    ap.add_argument("--repo", help="OWNER/REPO (default: the repository of the current directory)")
    ap.add_argument("--app", action="append", default=[], help="an app that must have an image bump commit (repeatable)")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        print("error: --sha must be the full 40-character commit sha", file=sys.stderr)
        return 2
    repo = args.repo or "{owner}/{repo}"
    repo_args = ["--repo", args.repo] if args.repo else []
    apps_dir = pathlib.Path("infra/k8s/apps")
    apps = sorted(p.parent.name for p in apps_dir.glob("*/values-staging.yaml")) if apps_dir.is_dir() else []
    for a in args.app:
        if a not in apps:
            apps.append(a)
    problems = []
    for step in (lambda: check_runs(args.sha, repo_args), lambda: check_message(args.sha, repo),
                 lambda: check_bumps(args.sha, repo, apps, set(args.app))):
        try:
            problems += step()
        except RuntimeError as e:
            problems.append(str(e))
    if problems:
        print("release evidence NOT ok for %s:" % args.sha[:7])
        for p in problems:
            print("  - " + p)
        return 1
    print("release evidence ok for %s: CI green, no skip-CI marker, image digest bump present" % args.sha[:7])
    return 0


if __name__ == "__main__":
    sys.exit(main())
