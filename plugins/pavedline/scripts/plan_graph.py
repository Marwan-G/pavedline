#!/usr/bin/env python3
"""Plan graph: check that every acceptance test maps to a slice, report progress, draw a wave.

  plan_graph.py check  [--repo DIR]   plans against SPEC.md; exit 1 on a problem, 2 when SPEC.md is missing
  plan_graph.py status [--repo DIR]   prints `feature-complete` (exit 0) only when every test maps to a merged slice
  plan_graph.py dot PLAN.md           writes PLAN.dot (one cluster per wave) and validates it with dot -Tcanon

A slice in a plan is a heading `### Slice <wave>.<n>: <title>` followed by the lines
`Tests: AT-001, AT-004`, `Surfaces: web, api`, `Branch: <name>`, `Depends on: <slice ids | none>` and,
for a later wave that proves an old test again, `Re-tests: AT-001`. Merged = a commit on the default
branch whose subject or body names the slice (`Slice 1.2`). Standard library only.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

AT_RE = re.compile(r"\bAT-\d{3,}\b")
SLICE_RE = re.compile(r"^### Slice (\S+?):\s*(.*)$", re.M)
FIELD_RE = re.compile(r"^(Tests|Surfaces|Branch|Depends on|Re-tests):\s*(.*)$", re.M)
SURFACE_WORDS = (("web", "web"), ("mobile", "mobile"), ("website", "site"), ("site", "site"), ("blog", "blog"))
FALLBACK_WARN = []
ALIASES = {"website": "site", "web app": "web", "mobile app": "mobile"}


def read_spec_tests(repo):
    spec = repo / "docs/spec/SPEC.md"
    if not spec.is_file():
        return None
    text = spec.read_text()
    m = re.search(r"^##[^\n]*[Aa]cceptance tests[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    body = m.group(1) if m else text
    seen = []
    for t in AT_RE.findall(body):
        if t not in seen:
            seen.append(t)
    return seen


def split_list(value):
    items = [v.strip() for v in re.split(r"[,\s]+", value.strip()) if v.strip()]
    return [] if [i.lower() for i in items] == ["none"] else items


def deferred_tests(repo):
    out = []
    for plan in sorted((repo / "docs/plans").glob("*.md")):
        if plan.name.lower() != "readme.md":
            for line in re.findall(r"^Deferred:\s*(.*)$", plan.read_text(), re.M):
                out += AT_RE.findall(line)
    return out


def parse_slices(repo):
    slices = []
    for plan in sorted((repo / "docs/plans").glob("*.md")):
        if plan.name.lower() == "readme.md":
            continue
        text = plan.read_text()
        heads = list(SLICE_RE.finditer(text))
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            fields = {k: v for k, v in FIELD_RE.findall(text[h.end():end])}
            sid = h.group(1)
            slices.append({
                "id": sid, "title": h.group(2).strip(), "file": plan.name,
                "wave": sid.split(".")[0],
                "tests": split_list(fields.get("Tests", "")),
                "re_tests": split_list(fields.get("Re-tests", "")),
                "surfaces": [s.lower() for s in split_list(fields.get("Surfaces", ""))],
                "deps": split_list(fields.get("Depends on", "")),
            })
    return slices


def selected_surfaces(repo):
    files = sorted((repo / "decisions").glob("0005-*.md"))
    if not files:
        return None
    text = files[0].read_text()
    line = re.search(r"^[-*\s]*Surfaces:\s*(.+)$", text, re.M)
    if line:
        names = {ALIASES.get(s.lower(), s.lower()) for s in split_list(line.group(1))}
        return names | {"api"}
    FALLBACK_WARN.append("decision 0005 has no `Surfaces:` line; falling back to words in its Decision section")
    m = re.search(r"^## Decision\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    low = (m.group(1) if m else text).lower()
    found = {"api"}
    for word, name in SURFACE_WORDS:
        if re.search(r"\b%s\b" % word, low):
            found.add(name)
    return found if len(found) > 1 else None


def find_cycle(slices):
    known = {x["id"] for x in slices}
    deps = {s["id"]: [d for d in s["deps"] if d in known] for s in slices}
    state = {}

    def visit(n, path):
        state[n] = 1
        for d in deps[n]:
            if state.get(d) == 1:
                return path + [n, d]
            if d not in state:
                c = visit(d, path + [n])
                if c:
                    return c
        state[n] = 2
        return None

    for n in deps:
        if n not in state:
            c = visit(n, [])
            if c:
                return c
    return None


def accepted_intents(repo):
    out = []
    for f in sorted((repo / "docs/intent").glob("*.md")):
        if f.name in ("README.md", "0000-template.md"):
            continue
        if re.search(r"^Status:\s*accepted\s*$", f.read_text(), re.M):
            out.append(f.name)
    return out


def check(repo):
    tests = read_spec_tests(repo)
    if tests is None:
        print("error: docs/spec/SPEC.md not found")
        return 2
    slices = parse_slices(repo)
    deferred = deferred_tests(repo)
    problems, warnings = [], []
    print("%d acceptance tests found in docs/spec/SPEC.md" % len(tests))
    if not tests:
        problems.append("no acceptance tests (AT-001 ...) in the Acceptance tests section of docs/spec/SPEC.md")
    for t in deferred:
        if t not in tests:
            problems.append("unknown test: %s (Deferred)" % t)
    ids = [s["id"] for s in slices]
    for sid in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append("duplicate slice id: %s" % sid)
    mapped = {}
    for s in slices:
        for t in s["tests"] + s["re_tests"]:
            if t not in tests:
                problems.append("unknown test: %s (slice %s)" % (t, s["id"]))
        for t in s["tests"]:
            mapped.setdefault(t, []).append(s["id"])
        for d in s["deps"]:
            if d not in ids:
                problems.append("unknown dependency: %s (slice %s)" % (d, s["id"]))
    for t in tests:
        if t not in mapped and t in deferred:
            continue
        if t not in mapped:
            problems.append("unmapped: %s" % t)
        elif len(mapped[t]) > 1:
            warnings.append("%s mapped twice (slices %s); a later wave uses `Re-tests:`" % (t, ", ".join(mapped[t])))
    only_deferred = [t for t in tests if t in deferred and t not in mapped]
    if only_deferred:
        warnings.append("%d tests deferred to later waves: %s" % (len(only_deferred), ", ".join(only_deferred)))
    cycle = find_cycle(slices)
    if cycle:
        problems.append("dependency cycle: %s" % " -> ".join(cycle))
    allowed = selected_surfaces(repo)
    if allowed is None:
        warnings.append("decision 0005 (surfaces) not found or unreadable; slice surfaces not checked")
    else:
        for s in slices:
            for surf in s["surfaces"]:
                if ALIASES.get(surf, surf) not in allowed:
                    problems.append("surface not selected in decision 0005: %s (slice %s)" % (surf, s["id"]))
    warnings.extend(dict.fromkeys(FALLBACK_WARN))
    pending = accepted_intents(repo)
    if pending:
        warnings.append("accepted intents not yet specced: %s; run spec change mode first" % ", ".join(pending))
    for p in problems:
        print("error: " + p)
    for w in warnings:
        print("warning: " + w)
    if not problems:
        print("ok: %d tests, %d slices" % (len(tests), len(slices)))
    return 1 if problems else 0


def default_ref(repo):
    r = subprocess.run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                       cwd=repo, capture_output=True, text=True)
    refs = ([r.stdout.strip()] if r.returncode == 0 and r.stdout.strip() else []) + ["main", "master", "HEAD"]
    for ref in refs:
        if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=repo, capture_output=True).returncode == 0:
            return ref
    return "HEAD"


def merged_slices(repo):
    """Slice ids merged on the default branch: a commit subject `Slice <id>...` or a `Slice: <id>` trailer;
    a `Revert "Slice ..."` subject un-merges it (an even number of reverts merges it again)."""
    r = subprocess.run(["git", "log", default_ref(repo), "--reverse", "--format=%s%x01%b%x02"],
                       cwd=repo, capture_output=True, text=True)
    merged = set()
    for entry in r.stdout.split("\x02"):
        if "\x01" not in entry:
            continue
        subject, body = entry.strip("\n").split("\x01", 1)
        m = re.match(r'^((?:Revert ")*)Slice\s+([^\s:"]+)', subject)
        if m:
            sid = m.group(2).rstrip(".,;")
            (merged.add if m.group(1).count("Revert") % 2 == 0 else merged.discard)(sid)
        elif not subject.startswith("Revert"):
            merged.update(re.findall(r"^Slice:\s*(\S+)\s*$", body, re.M))
    return merged


def status(repo):
    tests = read_spec_tests(repo)
    if tests is None:
        print("error: docs/spec/SPEC.md not found")
        return 2
    slices = parse_slices(repo)
    merged = merged_slices(repo)
    done = {t for s in slices if s["id"] in merged for t in s["tests"]}
    open_slices = [s["id"] for s in slices if s["id"] not in merged]
    open_tests = [t for t in tests if t not in done]
    if tests and slices and not open_tests:
        print("feature-complete")
        return 0
    if open_slices:
        print("open: " + ", ".join(open_slices))
    if open_tests:
        print("tests not yet in a merged slice: " + ", ".join(open_tests))
    if not slices:
        print("no slices found in docs/plans/")
    return 1


def q(s):
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def write_dot(plan):
    plan = pathlib.Path(plan)
    if not plan.is_file():
        print("error: %s not found" % plan)
        return 2
    repo = plan.resolve().parent.parent.parent
    slices = [s for s in parse_slices(repo) if s["file"] == plan.name]
    if not slices:
        print("error: no slices in %s" % plan)
        return 1
    lines = [
        "// Plan graph of %s: slices (nodes), dependencies (edges), one cluster per wave." % plan.name,
        "// Validate + render with the diagram skill; source of truth for the matching .svg.",
        "digraph plan {",
        '  graph [rankdir=LR, fontname="Helvetica", bgcolor="white", pad=0.4, label=%s, labelloc=t, fontsize=18];'
        % q("Plan: " + plan.stem),
        '  node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, fillcolor="#FFFFFF", color="#334155"];',
        '  edge  [fontname="Helvetica", fontsize=10, color="#475569"];',
    ]
    for wave in sorted({s["wave"] for s in slices}):
        lines.append("  subgraph cluster_wave_%s {" % re.sub(r"\W", "_", wave))
        lines.append('    label=%s; style="rounded,filled"; fillcolor="#EFF6FF"; color="#93C5FD";' % q("Wave " + wave))
        for s in slices:
            if s["wave"] == wave:
                label = "%s\n%s\n%s" % (s["id"], s["title"], ", ".join(s["tests"]))
                lines.append("    %s [label=%s];" % (q(s["id"]), q(label).replace("\n", "\\n")))
        lines.append("  }")
    for s in slices:
        for d in s["deps"]:
            lines.append("  %s -> %s;" % (q(d), q(s["id"])))
    lines.append("}")
    out = plan.with_suffix(".dot")
    out.write_text("\n".join(lines) + "\n")
    if shutil.which("dot"):
        r = subprocess.run(["dot", "-Tcanon", "-o", "/dev/null", str(out)], capture_output=True, text=True)
        if r.returncode != 0:
            print("error: dot -Tcanon failed: " + r.stderr.strip())
            return 1
    else:
        print("warning: graphviz 'dot' not found; %s not validated (run /pavedline:doctor)" % out.name)
    print("wrote %s" % out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "status"):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=".")
    p = sub.add_parser("dot")
    p.add_argument("plan")
    a = ap.parse_args(argv)
    if a.cmd == "dot":
        return write_dot(a.plan)
    repo = pathlib.Path(a.repo).resolve()
    return check(repo) if a.cmd == "check" else status(repo)


if __name__ == "__main__":
    sys.exit(main())
