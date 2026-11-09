#!/usr/bin/env python3
"""Check that every tool and plugin Pavedline needs is installed.

Usage: doctor.py
Prints a table (name, ok/missing, required/optional, fix) and a final summary
line. Exits 1 if any required check fails. The script only reports; the doctor skill does the
installing (after announcing, with the user's permission). Never prints environment variables. Standard library only.
"""
import json
import os
import platform as _platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Tuple


class Check(NamedTuple):
    name: str
    ok: bool
    required: bool
    fix: str
    status: str = ""


CLAUDE_FIX = "Install Claude Code: https://code.claude.com/docs/en/setup"

REDOCLY_PKG = "@redocly/cli@2.71.0"

# name -> (binary, brew formula, docs url, required)
TOOLS = [
    ("git", "git", "https://git-scm.com/downloads", True),
    ("gh", "gh", "https://cli.github.com/", True),
    ("python3", "python", "https://www.python.org/downloads/", True),
    ("node", "node", "https://nodejs.org/en/download", True),
    ("dot", "graphviz", "https://graphviz.org/download/", True),
    ("kubectl", "kubernetes-cli", "https://kubernetes.io/docs/tasks/tools/", True),
    ("helm", "helm", "https://helm.sh/docs/intro/install/", True),
    ("kind", "kind", "https://kind.sigs.k8s.io/docs/user/quick-start/#installation", True),
    ("colima", "colima", "https://github.com/abiosoft/colima#installation", False),
    ("uv", "uv", "https://docs.astral.sh/uv/getting-started/installation/", False),
    ("tofu or terraform", "opentofu", "https://opentofu.org/docs/intro/install/", False),
    # optional, used by step 5 (API contract lint); installed from npm, pinned
    ("redocly", REDOCLY_PKG, "https://redocly.com/docs/cli/installation", False),
]

RUNTIME_FIX_MAC = "brew install colima docker && colima start --cpu 4 --memory 10"
RUNTIME_FIX_OTHER = "https://docs.docker.com/engine/install/ (then start the Docker daemon)"

MP_CLAUDE = "claude-plugins-official"
PAVEDLINE_ID = "pavedline@pavedline"
PLUGINS = [
    ("superpowers@claude-plugins-official", "/plugin install superpowers@claude-plugins-official"),
    ("mattpocock-skills@claude-plugins-official", "/plugin install mattpocock-skills@claude-plugins-official"),
    (
        "product-management@knowledge-work-plugins",
        "/plugin marketplace add anthropics/knowledge-work-plugins then "
        "/plugin install product-management@knowledge-work-plugins",
    ),
    ("figma@claude-plugins-official", "/plugin install figma@claude-plugins-official"),
    (
        PAVEDLINE_ID,
        "/plugin marketplace add Marwan-G/pavedline then /plugin install pavedline@pavedline",
    ),
]

# optional plugins (design critique and style reference in step 7; the Grow loop's marketing skills after launch);
# never fail the doctor. Optional, not dependencies: Claude Code does not load a plugin whose dependency is missing.
OPTIONAL_PLUGINS = [
    (
        "impeccable@impeccable",
        "/plugin marketplace add pbakaus/impeccable then /plugin install impeccable@impeccable",
    ),
    (
        "ui-ux-pro-max@ui-ux-pro-max-skill",
        "/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill then "
        "/plugin install ui-ux-pro-max@ui-ux-pro-max-skill",
    ),
    (
        "marketing@knowledge-work-plugins",
        "/plugin marketplace add anthropics/knowledge-work-plugins then "
        "/plugin install marketing@knowledge-work-plugins",
    ),
]


def installed_node_version() -> Optional[str]:
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def redocly_node_ok(version: Optional[str]) -> bool:
    """Redocly CLI needs Node >=22.12 or >=20.19 <21 (see api-contract/references/sources.md)."""
    v = parse_version(version)
    if v is None:
        return False
    return (v >= (22, 12, 0)) or ((20, 19, 0) <= v < (21, 0, 0))


def docker_info_ok() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


VERSIONS_ENV = Path(__file__).resolve().parent / "local-cluster" / "versions.env"
HELM_URL = "https://helm.sh/docs/intro/install/"


def parse_version(text: Optional[str]) -> Optional[Tuple[int, int, int]]:
    m = re.match(r"^v?(\d{1,3})\.(\d{1,3})\.(\d{1,3})", text or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def helm_min_version() -> Tuple[int, int, int]:
    """HELM_MIN_VERSION from versions.env, the one place up.sh also reads it from."""
    for line in VERSIONS_ENV.read_text().splitlines():
        if line.startswith("HELM_MIN_VERSION="):
            v = parse_version(line.split("=", 1)[1].strip())
            if v:
                return v
    raise ValueError("HELM_MIN_VERSION missing from versions.env")


def installed_helm_version() -> Optional[str]:
    try:
        r = subprocess.run(["helm", "version", "--template", "{{.Version}}"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def helm_check(version: Optional[str], mac: bool) -> "Check":
    fix = "brew upgrade helm" if mac else HELM_URL
    need = helm_min_version()
    have = parse_version(version)
    need_text = ".".join(map(str, need))
    if have is None:
        return Check("helm", False, True, fix, "version unreadable")
    if have < need:
        return Check("helm", False, True, fix, f"too old ({version}, need {need_text}+)")
    return Check("helm", True, True, "", "ok")


def check_tools(
    which: Callable[[str], Optional[str]] = shutil.which,
    platform: Optional[str] = None,
    docker_ok: Callable[[], bool] = docker_info_ok,
    helm_version: Callable[[], Optional[str]] = installed_helm_version,
    node_version: Callable[[], Optional[str]] = installed_node_version,
) -> List[Check]:
    mac = (platform or _platform.system()) == "Darwin"
    checks: List[Check] = []
    for name, formula, url, required in TOOLS[:8]:
        if name == "helm" and which(name) is not None:
            checks.append(helm_check(helm_version(), mac))
            continue
        checks.append(Check(name, which(name) is not None, required, f"brew install {formula}" if mac else url))
    runtime_ok = which("docker") is not None and docker_ok()
    checks.append(Check("container runtime", runtime_ok, True, RUNTIME_FIX_MAC if mac else RUNTIME_FIX_OTHER))
    for name, formula, url, required in TOOLS[8:]:
        if name == "tofu or terraform":
            checks.append(Check(name, which("tofu") is not None or which("terraform") is not None, required,
                                f"optional (step 12): brew install {formula}, or Terraform: https://developer.hashicorp.com/terraform/install" if mac else url))
            continue
        if name == "redocly":
            checks.append(Check(name, which(name) is not None, required, f"optional: npx {formula} works without install, or npm install -g {formula}"))
            continue
        checks.append(Check(name, which(name) is not None, required, f"brew install {formula}" if mac else url))
    if which("node") is not None:
        ok = redocly_node_ok(node_version())
        checks.append(Check("node (for redocly)", ok, False,
                            "optional: Redocly CLI needs Node 22.12+ (or 20.19+ below 21); " + ("brew upgrade node" if mac else "https://nodejs.org/en/download"),
                            "ok" if ok else "too old"))
    return checks


def loaded_from_plugin_dir(script: Path = Path(__file__), home: Optional[Path] = None,
                           config_dir: Optional[Path] = None) -> bool:
    """True when this script is not inside Claude Code's plugin store, i.e. Pavedline is loaded with --plugin-dir.

    Docs (https://code.claude.com/docs/en/plugins-reference#environment-variables, checked 2026-11-08): the plugin
    path variables are not present in the environment of commands run through the Bash tool, and no other signal is
    documented. So the script's own location is used: installed plugins live under ~/.claude/plugins/, or under
    $CLAUDE_CONFIG_DIR/plugins when it is set (https://code.claude.com/docs/en/settings, checked 2026-11-09:
    CLAUDE_CONFIG_DIR makes Claude Code store settings, session history and plugins there instead).
    """
    if config_dir is None and os.environ.get("CLAUDE_CONFIG_DIR"):
        config_dir = Path(os.environ["CLAUDE_CONFIG_DIR"])
    store = (config_dir or (home or Path.home()) / ".claude") / "plugins"
    try:
        script.resolve().relative_to(store.resolve())
        return False
    except ValueError:
        return True


def _in_scope(p: dict, cwd: Optional[Path]) -> bool:
    """A listed plugin works here when it is user scope, or project/local scope for the current directory."""
    scope = p.get("scope")
    if scope == "user":
        return True
    if scope in ("project", "local") and isinstance(p.get("projectPath"), str):
        here = (cwd or Path.cwd()).resolve()
        root = Path(p["projectPath"]).resolve()
        return here == root or root in here.parents
    return False


def _install_fix(pid: str) -> str:
    return f"claude plugin install {pid} --scope user (or --scope project in this folder)"


def check_plugins(listing_json: str, plugin_dir_load: bool = False, cwd: Optional[Path] = None) -> List[Check]:
    try:
        data = json.loads(listing_json)
        if not isinstance(data, list):
            raise ValueError("not a list")
    except (ValueError, TypeError):
        return [Check("claude", False, True, CLAUDE_FIX)]
    present = {}  # id -> enabled and usable here
    elsewhere = set()  # ids enabled only at a scope that does not cover this directory
    for p in data:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            usable = p.get("enabled") is True and _in_scope(p, cwd)
            if p.get("enabled") is True and not usable:
                elsewhere.add(p["id"])
            present[p["id"]] = present.get(p["id"], False) or usable
    checks: List[Check] = []
    for pid, fix in PLUGINS:
        if pid == PAVEDLINE_ID:
            # Loaded via --plugin-dir the id is pavedline@inline, so accept any pavedline@ id.
            ids = [i for i in present if i.startswith("pavedline@")]
        else:
            ids = [pid] if pid in present else []
        if any(present[i] for i in ids):
            checks.append(Check(pid, True, True, "", "ok"))
        elif any(i in elsewhere for i in ids):
            checks.append(Check(pid, False, True, _install_fix(pid), "not available here"))
        elif ids:
            checks.append(Check(pid, False, True, f"/plugin enable {ids[0]}", "disabled"))
        elif pid == PAVEDLINE_ID and plugin_dir_load:
            checks.append(Check(pid, True, True, "", "ok (loaded with --plugin-dir)"))
        else:
            checks.append(Check(pid, False, True, fix, "missing"))
    return checks


def check_optional_plugins(listing_json: str, cwd: Optional[Path] = None) -> List[Check]:
    try:
        data = json.loads(listing_json)
        if not isinstance(data, list):
            raise ValueError("not a list")
    except (ValueError, TypeError):
        return []
    enabled = {p["id"] for p in data if isinstance(p, dict) and isinstance(p.get("id"), str) and p.get("enabled") is True and _in_scope(p, cwd)}
    other = {p["id"] for p in data if isinstance(p, dict) and isinstance(p.get("id"), str) and p.get("enabled") is True}
    return [
        Check(pid, True, False, "", "ok") if pid in enabled
        else Check(pid, False, False, _install_fix(pid), "not available here") if pid in other
        else Check(pid, False, False, fix, "missing")
        for pid, fix in OPTIONAL_PLUGINS
    ]


def check_env_local_ignored(cwd: Optional[Path] = None) -> List[Check]:
    """Inside a git repo that has an .env.local.example, .env.local must be git-ignored (it holds secrets)."""
    here = cwd or Path.cwd()
    try:
        top = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=30)
        if top.returncode != 0:
            return []
        root = Path(top.stdout.strip())
        if not (root / ".env.local.example").is_file():
            return []
        ig = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".env.local"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if ig.returncode == 0:
        return [Check(".env.local ignored by git", True, True, "", "ok")]
    return [Check(".env.local ignored by git", False, True, "echo '.env.local' >> .gitignore", "not ignored")]


def fetch_listing() -> Optional[str]:
    try:
        r = subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def render(checks: List[Check]) -> List[str]:
    rows = [("name", "status", "level", "fix")]
    for c in checks:
        rows.append((c.name, "ok" if c.ok else (c.status or "missing"), "required" if c.required else "optional", "" if c.ok else c.fix))
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    return [
        "  ".join(r[i].ljust(widths[i]) for i in range(3)) + ("  " + r[3] if r[3] else "")
        for r in rows
    ]


def run(which=shutil.which, platform=None, docker_ok=docker_info_ok, helm_version=installed_helm_version,
        listing_json=None, out=print) -> int:
    checks = check_tools(which=which, platform=platform, docker_ok=docker_ok, helm_version=helm_version)
    if listing_json is None and which("claude") is not None:
        listing_json = fetch_listing()
    checks += check_plugins(listing_json if listing_json is not None else "", plugin_dir_load=loaded_from_plugin_dir())
    checks += check_optional_plugins(listing_json if listing_json is not None else "")
    checks += check_env_local_ignored()
    for line in render(checks):
        out(line)
    failed = sum(1 for c in checks if c.required and not c.ok)
    out("doctor: all required checks passed" if failed == 0 else f"doctor: {failed} required check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
