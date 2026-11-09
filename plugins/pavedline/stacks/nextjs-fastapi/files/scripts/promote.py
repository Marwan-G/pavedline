#!/usr/bin/env python3
"""Promote a staging-verified sha to production by pull request (step 12; spec 6.10).

    python3 scripts/promote.py --sha <full sha> [--record docs/production/deployments.md]

Run from the product repository. Refuses any sha without a record row in docs/production/deployments.md:

    staging · <40-hex sha> · verified (cloud) · <YYYY-MM-DD>

(written by the person who verified it). Then rewrites the image digests in infra/k8s/apps/*/values-production.yaml to
the ones values-staging.yaml holds AT THAT SHA (read with `git show`, never from the working tree), matched by image
repository, and prints the commands that open the pull request. The only command it runs is the read-only `git show`:
it never commits, pushes, merges or syncs.
"""
import argparse
import pathlib
import re
import shlex
import subprocess
import sys

REPO_RE = re.compile(r'^(\s*repository:\s*)["\']?([^"\'\s#]+)["\']?\s*(#.*)?$')
DIGEST_RE = re.compile(r'^(\s*digest:\s*)["\']?([^"\'\s#]*)["\']?(\s*#.*)?$')
GOOD = re.compile(r"sha256:[0-9a-f]{64}")
ZERO = "sha256:" + "0" * 64


FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def verified(record, sha):
    """None when the record has a staging row for sha, else the reason it does not (a row inside a code block or an
    unclosed fence is an error, never silently skipped)."""
    if not record.is_file():
        return "%s does not exist" % record
    row = re.compile(r"^[\s|*\-]*staging\s*[·|]\s*%s\s*[·|]\s*verified \(cloud\)\s*[·|]\s*\d{4}-\d{2}-\d{2}" % re.escape(sha))
    fence, found, hidden = None, False, False
    for n, line in enumerate(record.read_text().splitlines(), 1):
        if fence:
            c, ln, _ = fence
            if re.match(r"^ {0,3}%s{%d,}\s*$" % (re.escape(c), ln), line):
                fence = None
            elif row.match(line):
                hidden = True
            continue
        m = FENCE_OPEN_RE.match(line)
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = (m.group(1)[0], len(m.group(1)), n)
        elif row.match(line):
            found = True
    if fence:
        return "%s has an unclosed code fence at line %d; close it" % (record, fence[2])
    if hidden:
        return "%s holds the staging row for %s inside a code block; a quoted example is not a record" % (record, sha[:7])
    if not found:
        return ("%s has no row 'staging · %s · verified (cloud) · <date>'; verify %s on staging first (deploy skill), "
                "then the person who verified it records it" % (record, sha[:7], sha[:7]))
    return None


def staging_at(sha, path):
    """The staging values file as committed at sha (read-only), or None."""
    r = subprocess.run(["git", "show", "%s:./%s" % (sha, path.as_posix())], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def digests(text):
    """Map image repository to digest (the digest line follows its repository line)."""
    out, repo = {}, None
    for line in text.splitlines():
        m = REPO_RE.match(line)
        if m:
            repo = m.group(2)
            continue
        m = DIGEST_RE.match(line)
        if m and repo:
            out[repo] = m.group(2)
            repo = None
    return out


def rewrite(text, source):
    lines, repo, changed, problems = text.splitlines(keepends=True), None, [], []
    for i, line in enumerate(lines):
        m = REPO_RE.match(line.rstrip("\n"))
        if m:
            repo = m.group(2)
            continue
        m = DIGEST_RE.match(line.rstrip("\n"))
        if m and repo:
            new = source.get(repo)
            if new is None:
                problems.append("production image %s has no staging counterpart" % repo)
            elif m.group(2) != new:
                lines[i] = '%s"%s"%s\n' % (m.group(1), new, m.group(3) or "")
                changed.append(repo)
            repo = None
    return "".join(lines), changed, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sha", required=True, help="the full 40-character sha verified on staging")
    ap.add_argument("--record", default="docs/production/deployments.md")
    ap.add_argument("--apps-dir", default="infra/k8s/apps")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", a.sha):
        print("error: --sha must be the full 40-character commit sha", file=sys.stderr)
        return 2
    why = verified(pathlib.Path(a.record), a.sha)
    if why:
        print("refused: " + why)
        return 1
    problems, writes = [], []
    apps = sorted(pathlib.Path(a.apps_dir).glob("*/values-production.yaml"))
    for prod in apps:
        stg = prod.with_name("values-staging.yaml")
        if not any(DIGEST_RE.match(l) for l in prod.read_text().splitlines()):
            print("skipped: %s (no image to promote)" % prod.as_posix())  # a chart with no image digest, e.g. postgres
            continue
        staged = staging_at(a.sha, stg)
        if staged is None:
            problems.append("%s does not exist at %s" % (stg, a.sha[:7]))
            continue
        source = digests(staged)
        if not source:
            problems.append("%s at %s has no image digest bump" % (stg, a.sha[:7]))
            continue
        for repo, d in source.items():
            if not GOOD.fullmatch(d) or d == ZERO:
                problems.append("%s: staging digest for %s is %r, not a promotable digest" % (stg, repo, d or "none"))
        new, changed, probs = rewrite(prod.read_text(), source)
        problems += ["%s: %s" % (prod, p) for p in probs]
        if changed:
            writes.append((prod, new))
    if not apps:
        problems.append("no %s/*/values-production.yaml found" % a.apps_dir)
    if problems:
        print("promotion NOT done:")
        for p in problems:
            print("  - " + p)
        return 1
    for prod, new in writes:
        prod.write_text(new)
        print("updated " + str(prod))
    if not writes:
        print("production already runs staging's digests; nothing to change")
    s = a.sha[:7]
    print("\nPromotion is a pull request. Run these yourself:\n")
    print("  git switch -c promote/%s" % s)
    print("  git add %s" % shlex.quote(a.apps_dir.rstrip("/")) + "/*/values-production.yaml")
    print("  git commit -m 'Promote %s to production'" % s)
    print("  git push -u origin promote/%s" % s)
    print("  gh pr create --title 'Promote %s to production' --body 'Digests of the staging-verified %s'" % (s, a.sha))
    print("\nA person merges it and syncs production, verifies (cloud), then records a production row in %s." % shlex.quote(a.record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
