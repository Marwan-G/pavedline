#!/usr/bin/env python3
"""Copy a stack pack into a product repository (step 6) for the chosen surfaces and tenancy.

Usage: apply_stack.py --target DIR --pack nextjs-fastapi --surfaces api,web,site,mobile
                      [--tenancy multi|single] [--name SLUG] [--github-repo OWNER/REPO]
                      [--postgres-major N] [--dry-run]

--postgres-major N writes the PostgreSQL image the pack pins for major N (pack.yaml `postgres:`) into the copied
infra/k8s/apps/postgres/values.yaml; a major the pack does not pin exits 1 with "postgres major N not pinned in this
pack" and writes nothing. Without it the pack's default major is used.

Never overwrites: the full file list is computed first; if any pack file already exists in the target, nothing is
written, each clash is printed as "conflict: <path>", and the exit code is 1. The stack-neutral templates a product
started with an older Pavedline may lack (infra/, .github/, scripts/, renovate.json, .sanitize-denylist) are copied
when absent; one that exists and differs is kept ("kept: <path>"), never a conflict. An existing .gitignore is kept
and gains the pack's lines it lacks ("appended: .gitignore"). Standard library only.
"""
import argparse
import json
import os
import pathlib
import re
import sys

PLUGIN = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".import_linter_cache",
    ".pyright",
    ".next",
    ".turbo",
    ".expo",
    "playwright-report",
    "test-results",
}
SKIP_FILES = {".DS_Store"}
NEUTRAL_DIRS = ("infra", ".github", "scripts")
NEUTRAL_FILES = ("renovate.json", ".sanitize-denylist")
# Dropped for a single-tenant product (decision 0002): the RLS check, the cross-tenant leak fixture and its test.
LEAK_AND_RLS_FILES = (
    "scripts/rls_check.py",
    "services/api/tests/test_tenant_leak.py",
    "services/api/tests/test_rls_check.py",
)
RUN_HEADING = "## Stack: {pack}"
SLUG_RE = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")
REPO_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+")
BEGIN_RE = re.compile(r"^\s*(?:#|//|<!--)\s*pavedline-begin:\s*(.*?)\s*(?:-->)?\s*$")
END_RE = re.compile(r"^\s*(?:#|//|<!--)\s*pavedline-end\s*(?:-->)?\s*$")


def sub_once(pattern, new, text, dest, keep_prefix=False):
    """Replace the first match of pattern; a pack file without the line is an error, never a silent no-op."""
    repl = (lambda m: m.group(1) + new) if keep_prefix else (lambda _m: new)
    out, n = re.subn(pattern, repl, text, count=1)
    if n == 0:
        raise UsageError("%s: no Postgres image line to rewrite" % dest)
    return out


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- pack.yaml (the small subset it uses)


def _strip_comment(line: str) -> str:
    out = []
    quote = None
    prev = " "
    for ch in line:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and prev in " \t[{,":
            quote = ch
        elif ch == "#" and prev in " \t":
            break
        out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _scalar(text: str):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


KEY_RE = re.compile(r"^([^\s:#\-\[{\"'][^:]*?):(?:\s+(.*))?$")


def parse_pack(text: str) -> dict:
    lines = []
    for raw in text.splitlines():
        s = _strip_comment(raw)
        if s.strip():
            lines.append((len(s) - len(s.lstrip(" ")), s.strip()))

    def block(i: int, indent: int):
        if i < len(lines) and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
            items = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("-"):
                items.append(_scalar(lines[i][1][1:]))
                i += 1
            return items, i
        mapping = {}
        while i < len(lines) and lines[i][0] == indent:
            m = KEY_RE.match(lines[i][1])
            if not m:
                raise ValueError("pack.yaml: cannot parse: " + lines[i][1])
            key, val = m.group(1).strip(), m.group(2)
            i += 1
            if val is None or val == "":
                if i < len(lines) and lines[i][0] > indent:
                    mapping[key], i = block(i, lines[i][0])
                else:
                    mapping[key] = {}
            else:
                mapping[key] = _scalar(val)
        return mapping, i

    result, _ = block(0, 0) if lines else ({}, 0)
    return result


# ---------------------------------------------------------------- surface-aware text


def apply_markers(text: str, chosen, known=None) -> str:
    """Keep a `pavedline-begin: a, b` ... `pavedline-end` block only when a listed surface is chosen."""
    out = []
    keep = True
    inside = False
    for line in text.splitlines(keepends=True):
        b = BEGIN_RE.match(line.rstrip("\r\n"))
        if b:
            if inside:
                raise ValueError("pavedline-begin inside another block")
            inside = True
            names = {n.strip() for n in b.group(1).split(",") if n.strip()}
            if known is not None and names - set(known):
                raise ValueError("marker names an unknown surface: " + ", ".join(sorted(names - set(known))))
            keep = bool(names & set(chosen))
            continue
        if END_RE.match(line.rstrip("\r\n")):
            if not inside:
                raise ValueError("pavedline-end without pavedline-begin")
            inside = False
            keep = True
            continue
        if keep:
            out.append(line)
    if inside:
        raise ValueError("pavedline-begin without pavedline-end")
    return "".join(out)


def valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.fullmatch(slug))


def valid_repo(repo: str) -> bool:
    if not REPO_RE.fullmatch(repo):
        return False
    return all(part not in (".", "..") for part in repo.split("/"))


def _entry_surfaces(entry: dict):
    s = entry.get("surface")
    return None if s is None else (s if isinstance(s, list) else [s])


def filter_local_deploy(obj, chosen):
    """Drop entries (dicts with a `surface`) of surfaces that are not chosen; the shared database goes with api."""
    chosen = set(chosen)
    if "api" in chosen:
        chosen |= {"postgres", "shared"}

    def keep(entry):
        names = _entry_surfaces(entry)
        return names is None or bool(set(names) & chosen)

    def walk(o):
        if isinstance(o, list):
            return [walk(x) for x in o if not (isinstance(x, dict) and "surface" in x and not keep(x))]
        if isinstance(o, dict):
            return {
                k: walk(v) for k, v in o.items() if not (isinstance(v, dict) and "surface" in v and not keep(v))
            }
        return o

    return walk(obj)


def filter_package_json(text: str, workspace_names, files) -> str:
    data = json.loads(text)
    scripts = data.get("scripts", {})
    kept = {}
    for name, cmd in scripts.items():
        segments = []
        for seg in cmd.split("&&"):
            refs = re.findall(r"--filter\s+(\S+)", seg)
            files_used = re.findall(r"(?<![\w./-])(scripts/[\w./-]+)", seg)
            if all(r in workspace_names for r in refs) and all(f in files for f in files_used):
                segments.append(seg.strip())
        if segments:
            kept[name] = " && ".join(segments)
    data["scripts"] = kept
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _unquote(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"" else s


def _sections(lines, start, end):
    """Split the lines of a lockfile section into (key, lines) entries at two-space indent."""
    entries, current = [], None
    for line in lines[start:end]:
        m = re.match(r"^  (['\"]?)(\S.*?)\1:(?: .*)?$", line)
        if m and not line.startswith("   "):
            current = [m.group(2), [line]]
            entries.append(current)
        elif current is not None:
            current[1].append(line)
    return entries


def filter_lock(text: str, workspace_dirs) -> str:
    """Keep the importers of copied workspaces, and only the packages and snapshots they can reach."""
    lines = text.split("\n")

    def top(name):
        try:
            i = lines.index(name)
        except ValueError:
            return None, None
        j = len(lines)
        for k in range(i + 1, len(lines)):
            if lines[k] and not lines[k].startswith(" "):
                j = k
                break
        return i, j

    i0, i1 = top("importers:")
    if i0 is None:
        return text
    head, tail_start = lines[: i0 + 1], i1
    kept_importers, roots = [], []
    for key, block in _sections(lines, i0 + 1, i1):
        if key == "." or key in workspace_dirs:
            kept_importers.extend(block)
            group = None
            name = None
            for line in block[1:]:
                if re.match(r"^    (dependencies|devDependencies|optionalDependencies):$", line):
                    group = True
                    continue
                m = re.match(r"^      (\S.*?):$", line)
                if group and m:
                    name = _unquote(m.group(1))
                    continue
                v = re.match(r"^        version: (.+)$", line)
                if group and name and v:
                    ver = _unquote(v.group(1))
                    if not ver.startswith("link:"):
                        roots.append(ver if not ver[:1].isdigit() else name + "@" + ver)
    p0, p1 = top("packages:")
    s0, s1 = top("snapshots:")
    if p0 is None or s0 is None:
        out = head + kept_importers + lines[tail_start:]
        return "\n".join(out)
    snaps = _sections(lines, s0 + 1, s1)
    by_key = {k: b for k, b in snaps}
    reach, stack = set(), list(roots)
    while stack:
        k = stack.pop()
        if k in reach or k not in by_key:
            continue
        reach.add(k)
        group = False
        for line in by_key[k][1:]:
            if re.match(r"^    (dependencies|optionalDependencies):$", line):
                group = True
                continue
            if re.match(r"^    \S", line):
                group = False
                continue
            m = re.match(r"^      (['\"]?)(\S.*?)\1: (.+)$", line)
            if group and m:
                val = _unquote(m.group(3))
                # an npm alias (`name: other@1.2.3`) names the package itself
                stack.append(val if not val[:1].isdigit() else m.group(2) + "@" + val)
    base = {re.sub(r"\(.*$", "", k) for k in reach}
    pkgs = _sections(lines, p0 + 1, p1)
    out = list(head) + kept_importers
    # lines between importers and packages (blank lines, other top-level keys) are kept as they were
    out += lines[i1:p0 + 1]
    for k, b in pkgs:
        if k in base:
            out.extend(b)
    out += lines[p1:s0 + 1]
    for k, b in snaps:
        if k in reach:
            out.extend(b)
    out += lines[s1:]
    return "\n".join(out)


def title_from_slug(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def bundle_segment(slug: str) -> str:
    seg = slug.replace("-", "")
    return "app" + seg if seg[0].isdigit() else seg


# ---------------------------------------------------------------- the plan


class Entry:
    def __init__(self, dest: str, src: pathlib.Path, hard: bool, scan: bool = False):
        self.dest = dest
        self.src = src
        self.hard = hard
        self.scan = scan
        self.raw = src.read_bytes()
        self.final = self.raw
        self.exec = bool(src.stat().st_mode & 0o111) or dest.endswith(".sh")
        self.action = ""


def walk_files(root: pathlib.Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            p = pathlib.Path(dirpath) / f
            if p.is_file():
                yield p


def add_path(entries: dict, files_root: pathlib.Path, rel: str, hard: bool, scan: bool, required: bool = True):
    src = files_root / rel
    if src.is_dir():
        for p in walk_files(src):
            dest = p.relative_to(files_root).as_posix()
            entries.setdefault(dest, Entry(dest, p, hard, scan))
    elif src.is_file():
        entries.setdefault(rel, Entry(rel, src, hard, scan))
    elif required:
        raise UsageError("pack.yaml lists a path the pack does not contain: " + rel)


def through_symlink(target: pathlib.Path, rel: str) -> bool:
    """True when the destination or any folder between the target and it is a symlink (a write could leave the target)."""
    p = pathlib.PurePosixPath(rel)
    return any((target / str(a)).is_symlink() for a in list(p.parents) if str(a) != ".") or (target / rel).is_symlink()


def is_conflict(target: pathlib.Path, rel: str) -> bool:
    dest = target / rel
    if dest.exists() or dest.is_symlink():
        return True
    p = pathlib.PurePosixPath(rel)
    return any((target / str(a)).exists() and not (target / str(a)).is_dir() for a in p.parents if str(a) != ".")


def build_plan(args, pack: dict, pack_dir: pathlib.Path, surfaces: list):
    files_root = pack_dir / "files"
    entries: dict = {}
    chosen = set(surfaces)
    surf_defs = pack.get("surfaces", {})

    # 2. pack files per chosen surface
    for s in surfaces:
        d = surf_defs[s]
        for rel in list(d.get("paths", [])) + list(d.get("infra", [])):
            add_path(entries, files_root, rel, hard=True, scan=True)
    shared = pack.get("shared", {})
    if chosen & set(shared.get("needed_by", [])):
        for rel in shared.get("paths", []):
            add_path(entries, files_root, rel, hard=True, scan=False)
    common_soft = str(pack.get("common", {}).get("keep_if_present")).lower() == "true"
    for rel in pack.get("common", {}).get("paths", []):
        add_path(entries, files_root, rel, hard=not common_soft, scan=False)
    markers = {}
    for s, d in surf_defs.items():
        for m in d.get("ci_markers", []):
            markers[m.strip()] = s
    wf_dir = files_root / ".github/workflows"
    if wf_dir.is_dir():
        for wf in sorted(wf_dir.glob("*.yml")):
            first = wf.read_text(encoding="utf-8").split("\n", 1)[0].strip()
            owner = markers.get(first)
            if first.startswith("# pavedline-surface:") and owner is None:
                continue
            if owner is None or owner in chosen:
                rel = "/".join((".github", "workflows", wf.name))
                entries.setdefault(rel, Entry(rel, wf, True, True))
    for rel in pack.get("deploy", {}).get("paths", []):
        add_path(entries, files_root, rel, hard=True, scan=False)
    fragment = pack.get("run_fragment")
    if fragment:
        entries.pop(fragment, None)

    # 4. the local cluster scripts
    lc = PLUGIN / "scripts/local-cluster"
    if lc.is_dir():
        for p in walk_files(lc):
            dest = "scripts/local-cluster/" + p.relative_to(lc).as_posix()
            entries.setdefault(dest, Entry(dest, p, True))
    # 5. the pack's source list
    sources = pack_dir / "SOURCES.md"
    if sources.is_file():
        entries.setdefault("docs/architecture/STACK-SOURCES.md", Entry("docs/architecture/STACK-SOURCES.md", sources, True))

    # 1. stack-neutral templates (copied when absent, never a conflict)
    templates = PLUGIN / "templates"
    for sub in NEUTRAL_DIRS:
        for p in walk_files(templates / sub):
            dest = p.relative_to(templates).as_posix()
            entries.setdefault(dest, Entry(dest, p, False, scan=dest == ".github/CODEOWNERS"))
    for rel in NEUTRAL_FILES:
        if (templates / rel).is_file():
            entries.setdefault(rel, Entry(rel, templates / rel, False))

    # 6. single tenancy drops the RLS check and the leak fixture
    if args.tenancy == "single":
        for rel in LEAK_AND_RLS_FILES:
            entries.pop(rel, None)
    return entries


def postgres_image(pack: dict, major):
    """The image the pack pins for a PostgreSQL major (default major when none is asked for); None when unpinned."""
    pg = pack.get("postgres") or {}
    majors = {str(k): v for k, v in (pg.get("majors") or {}).items()}
    wanted = str(major if major is not None else pg.get("default_major", ""))
    return majors.get(wanted)


def postgres_test_image(pack: dict, major):
    pins = postgres_image(pack, major)
    return pins.get("test") if isinstance(pins, dict) else None


def append_missing_lines(current: str, pack_text: str) -> str:
    """Lines of the pack's text that the existing text lacks (comments and blanks skipped), appended after a header."""
    have = {line.strip() for line in current.splitlines()}
    missing = []
    for line in pack_text.splitlines():
        t = line.strip()
        if t and not t.startswith("#") and t not in have and t not in missing:
            missing.append(t)
    if not missing:
        return current
    base = current if current.endswith("\n") or not current else current + "\n"
    return base + "\n# Added by Pavedline (stack pack)\n" + "\n".join(missing) + "\n"


def transform(entries: dict, args, surfaces: list, known=None, pack=None):
    chosen = set(surfaces)
    files = set(entries)
    workspace_names = set()
    workspace_dirs = set()
    for dest, e in entries.items():
        m = re.match(r"^((?:apps|packages)/[^/]+)/package\.json$", dest)
        if m:
            workspace_dirs.add(m.group(1))
            try:
                workspace_names.add(json.loads(e.raw.decode("utf-8")).get("name", ""))
            except (ValueError, UnicodeDecodeError):
                pass
    owner = repo = None
    if args.github_repo:
        owner, repo = args.github_repo.split("/", 1)
    for dest, e in entries.items():
        data = e.raw
        if b"\0" not in data:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = None
        else:
            text = None
        if text is not None:
            if "pavedline-begin" in text or "pavedline-end" in text:
                text = apply_markers(text, chosen, known)
            if dest == "package.json":
                text = filter_package_json(text, workspace_names, files)
            elif dest == "pnpm-lock.yaml":
                text = filter_lock(text, workspace_dirs)
            elif dest == "infra/k8s/apps/postgres/values.yaml" and pack is not None:
                pins = postgres_image(pack, args.postgres_major)
                image = pins.get("cluster") if isinstance(pins, dict) else None
                if image:
                    text = sub_once(r"(?m)^image: .*$", "image: " + image, text, dest)
            elif dest == "infra/local-deploy.json":
                text = json.dumps(filter_local_deploy(json.loads(text), chosen), indent=2, ensure_ascii=False) + "\n"
            elif dest == ".github/workflows/ci-api.yml" and args.tenancy == "single":
                text = text.replace("PAVEDLINE_TENANCY: multi", "PAVEDLINE_TENANCY: single")
            elif dest == "apps/mobile/app.config.ts" and args.name:
                seg = bundle_segment(args.name)
                text = (
                    text.replace("name: 'Example'", "name: '" + title_from_slug(args.name) + "'")
                    .replace("slug: 'example'", "slug: '" + args.name + "'")
                    .replace("com.example.app", "com." + seg + ".app")
                )
            if dest == ".github/workflows/ci-api.yml" and pack is not None:
                image = postgres_test_image(pack, args.postgres_major)
                if image:
                    text = sub_once(r"(?m)^(        image: )postgres:\S+$", image, text, dest, keep_prefix=True)
            if owner and (dest.startswith("infra/") or dest == ".github/CODEOWNERS"):
                text = text.replace("ghcr.io/OWNER/REPO", "ghcr.io/" + owner.lower() + "/" + repo.lower())
                if dest == ".github/CODEOWNERS":
                    text = re.sub(r"@OWNER\b", lambda _m: "@" + owner, text)
            data = text.encode("utf-8")
        e.final = data


FILL_PATTERNS = (
    (re.compile(r"@OWNER\b"), "@OWNER (the GitHub owner)"),
    (re.compile(r"ghcr\.io/OWNER/REPO"), "ghcr.io/OWNER/REPO (the image repository)"),
    (re.compile(r"example\.com"), "example.com hostname (the product's domain)"),
    (re.compile(r"com\.example\.app"), "name, slug and bundle identifier (com.example.app)"),
)


def to_fill(entries: dict):
    out = []
    for dest in sorted(entries):
        e = entries[dest]
        if not e.scan or e.action not in ("created", "updated", "identical"):
            continue
        if not (dest.startswith(("infra/", ".github/")) or dest == "apps/mobile/app.config.ts"):
            continue
        try:
            text = e.final.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for pat, label in FILL_PATTERNS:
            if pat.search(text):
                out.append("to fill: " + dest + ": " + label)
    return out


# ---------------------------------------------------------------- the RUN.md fragment


def build_fragment(pack: dict, pack_dir: pathlib.Path, surfaces: list, tenancy: str) -> str:
    chosen = set(surfaces)
    frag_name = pack.get("run_fragment")
    text = ""
    if frag_name and (pack_dir / "files" / frag_name).is_file():
        text = apply_markers((pack_dir / "files" / frag_name).read_text(encoding="utf-8"), chosen, list(pack.get("surfaces", {})))
    text = re.sub(r"^## ", "### ", text, flags=re.M)
    # a heading whose code block lost every line goes with it
    text = re.sub(r"\*\*[^\n]*\*\*\n```[a-z]*\n```\n", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
    cmds = pack.get("surfaces", {}).get("api", {}).get("commands", {})
    if "api" in chosen and cmds:
        lines = ["", "", "**API checks (from `services/api`; `pytest` needs `DATABASE_URL`, an administrator URL of a throwaway Postgres).**", "```bash"]
        for k in ("install", "lint", "format_check", "types", "imports", "test"):
            if cmds.get(k):
                lines.append(cmds[k])
        lines.append("```")
        lines += ["", "**Schema and contract checks (from the repository root, against the migrated database).**"]
        if tenancy == "single":
            lines += [
                "",
                "- RLS check: not applicable (decision 0002).",
                "- Leak fixture (cross-tenant test): not applicable (decision 0002).",
            ]
            tail = [cmds[k] for k in ("contract_check",) if cmds.get(k)]
        else:
            tail = [cmds[k] for k in ("rls_check", "contract_check") if cmds.get(k)]
            lines += ["", "The cross-tenant leak fixture runs with `cd services/api && uv run pytest -q tests/test_tenant_leak.py`."]
        if tail:
            lines += ["", "```bash"] + tail + ["```"]
        text += "\n".join(lines)
    return text.strip("\n") + "\n"


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--surfaces", required=True, help="comma list of the pack's surfaces, e.g. api,web,site,mobile")
    ap.add_argument("--tenancy", choices=["multi", "single"], default="multi")
    ap.add_argument("--name", help="product slug (a DNS label); renames the mobile app")
    ap.add_argument("--github-repo", help="OWNER/REPO: fills the image repositories and CODEOWNERS")
    ap.add_argument("--postgres-major", type=int, help="PostgreSQL major from the product's database decision (the pack pins its own list)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stacks-dir", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.name is not None and not valid_slug(args.name):
        ap.error("--name must be a DNS label: lowercase letters, digits and '-', 1-63 characters, no leading or trailing '-'")
    if args.github_repo is not None and not valid_repo(args.github_repo):
        ap.error("--github-repo must look like OWNER/REPO")
    surfaces = []
    for s in args.surfaces.split(","):
        s = s.strip()
        if not s:
            ap.error("--surfaces: empty entry (give a comma list such as api,web)")
        if s not in surfaces:
            surfaces.append(s)
    stacks = pathlib.Path(args.stacks_dir) if args.stacks_dir else PLUGIN / "stacks"
    pack_dir = stacks / args.pack
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", args.pack) or not (pack_dir / "pack.yaml").is_file():
        ap.error("unknown pack: " + args.pack)
    try:
        pack = parse_pack((pack_dir / "pack.yaml").read_text(encoding="utf-8"))
    except ValueError as exc:
        ap.error(str(exc))
    known = list(pack.get("surfaces", {}))
    for s in surfaces:
        if s not in known:
            ap.error("unknown surface: " + s + " (the pack has: " + ", ".join(known) + ")")
    target = pathlib.Path(args.target)
    if not target.is_dir():
        print("error: target directory does not exist: " + args.target, file=sys.stderr)
        return 1
    if args.postgres_major is not None and postgres_image(pack, args.postgres_major) is None:
        print("error: postgres major %d not pinned in this pack" % args.postgres_major, file=sys.stderr)
        return 1

    try:
        entries = build_plan(args, pack, pack_dir, surfaces)
        transform(entries, args, surfaces, known, pack)
    except (UsageError, ValueError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2

    conflicts = sorted(d for d, e in entries.items() if (e.hard and is_conflict(target, d)) or through_symlink(target, d))
    # RUN.md is appended outside the plan: a symlink there (or in front of it) would be written through.
    if through_symlink(target, "RUN.md") and "RUN.md" not in conflicts:
        conflicts.append("RUN.md")
    if conflicts:
        for d in conflicts:
            print("conflict: " + d)
        print("nothing written: existing files are never overwritten", file=sys.stderr)
        return 1

    copied = kept = 0
    for dest in sorted(entries):
        e = entries[dest]
        path = target / dest
        if not (path.exists() or path.is_symlink()) and not any(
            (target / str(a)).exists() and not (target / str(a)).is_dir()
            for a in pathlib.PurePosixPath(dest).parents
            if str(a) != "."
        ):
            e.action = "created"
        elif e.hard:
            raise AssertionError("unreachable: a hard clash was reported above")
        elif not path.is_file():
            e.action = "kept"
        else:
            cur = path.read_bytes()
            if cur == e.final:
                e.action = "identical"
            elif cur == e.raw:
                e.action = "updated"
            elif dest == ".gitignore":
                merged = append_missing_lines(cur.decode("utf-8", "replace"), e.final.decode("utf-8", "replace"))
                if merged.encode("utf-8") == cur:
                    e.action = "identical"
                else:
                    e.action = "appended"
                    e.final = merged.encode("utf-8")
            else:
                e.action = "kept"
        if e.action == "kept":
            kept += 1
            print("kept: " + dest)
            continue
        if e.action == "identical":
            continue
        copied += 1
        verb = {"created": "create", "updated": "update", "appended": "append"}[e.action]
        if args.dry_run:
            print("would " + verb + ": " + dest)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() not in path.parent.resolve().parents and path.parent.resolve() != target.resolve():
            print("error: refusing to write outside the target: " + dest, file=sys.stderr)
            return 1
        path.write_bytes(e.final)
        if e.exec and e.action == "created":
            path.chmod(0o755)
        print(e.action + ": " + dest)

    run_md = target / "RUN.md"
    heading = RUN_HEADING.format(pack=args.pack)
    existing = run_md.read_text(encoding="utf-8") if run_md.is_file() else None
    if existing is None or not re.search(r"^" + re.escape(heading) + r"\s*$", existing, flags=re.M):
        fragment = build_fragment(pack, pack_dir, surfaces, args.tenancy)
        if args.dry_run:
            print("would append: RUN.md" if existing is not None else "would create: RUN.md")
        else:
            base = (existing.rstrip("\n") + "\n\n") if existing else ""
            run_md.write_text(base + heading + "\n\n" + fragment, encoding="utf-8")
            print("appended: RUN.md" if existing is not None else "created: RUN.md")

    fills = to_fill(entries)
    for line in fills:
        print(line)
    prefix = "dry run: would copy" if args.dry_run else "summary: copied"
    print("%s %d, kept %d, to fill %d" % (prefix, copied, kept, len(fills)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
