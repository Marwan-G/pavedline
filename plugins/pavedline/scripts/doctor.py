#!/usr/bin/env python3
"""Check that every tool and plugin Pavedline needs is installed.

Usage: doctor.py
Prints a table (name, ok/missing, required/optional, fix) and a final summary
line. Exits 1 if any required check fails. Never installs anything and never
prints environment variables. Standard library only.
"""
import json
import platform as _platform
import shutil
import subprocess
import sys
from typing import Callable, List, NamedTuple, Optional


class Check(NamedTuple):
    name: str
    ok: bool
    required: bool
    fix: str


CLAUDE_FIX = "Install Claude Code: https://code.claude.com/docs/en/setup"

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
    ("terraform", "terraform", "https://developer.hashicorp.com/terraform/install", False),
]

RUNTIME_FIX_MAC = "brew install colima docker && colima start --cpu 4 --memory 10"
RUNTIME_FIX_OTHER = "https://docs.docker.com/engine/install/ (then start the Docker daemon)"

MP_CLAUDE = "claude-plugins-official"
PLUGINS = [
    ("superpowers@claude-plugins-official", "/plugin install superpowers@claude-plugins-official"),
    ("mattpocock-skills@claude-plugins-official", "/plugin install mattpocock-skills@claude-plugins-official"),
    (
        "product-management@knowledge-work-plugins",
        "/plugin marketplace add anthropics/knowledge-work-plugins then "
        "/plugin install product-management@knowledge-work-plugins",
    ),
    (
        "pavedline@pavedline",
        "/plugin marketplace add Marwan-G/pavedline then /plugin install pavedline@pavedline",
    ),
]


def docker_info_ok() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_tools(
    which: Callable[[str], Optional[str]] = shutil.which,
    platform: Optional[str] = None,
    docker_ok: Callable[[], bool] = docker_info_ok,
) -> List[Check]:
    mac = (platform or _platform.system()) == "Darwin"
    checks: List[Check] = []
    for name, formula, url, required in TOOLS[:8]:
        checks.append(Check(name, which(name) is not None, required, f"brew install {formula}" if mac else url))
    runtime_ok = which("docker") is not None and docker_ok()
    checks.append(Check("container runtime", runtime_ok, True, RUNTIME_FIX_MAC if mac else RUNTIME_FIX_OTHER))
    for name, formula, url, required in TOOLS[8:]:
        checks.append(Check(name, which(name) is not None, required, f"brew install {formula}" if mac else url))
    return checks


def check_plugins(listing_json: str) -> List[Check]:
    try:
        data = json.loads(listing_json)
        if not isinstance(data, list):
            raise ValueError("not a list")
    except (ValueError, TypeError):
        return [Check("claude", False, True, CLAUDE_FIX)]
    enabled = {p.get("id") for p in data if isinstance(p, dict) and p.get("enabled") is True}
    return [Check(pid, pid in enabled, True, fix) for pid, fix in PLUGINS]


def fetch_listing() -> Optional[str]:
    try:
        r = subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def render(checks: List[Check]) -> List[str]:
    rows = [("name", "status", "level", "fix")]
    for c in checks:
        rows.append((c.name, "ok" if c.ok else "missing", "required" if c.required else "optional", "" if c.ok else c.fix))
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    return [
        "  ".join(r[i].ljust(widths[i]) for i in range(3)) + ("  " + r[3] if r[3] else "")
        for r in rows
    ]


def run(which=shutil.which, platform=None, docker_ok=docker_info_ok, listing_json=None, out=print) -> int:
    checks = check_tools(which=which, platform=platform, docker_ok=docker_ok)
    if listing_json is None and which("claude") is not None:
        listing_json = fetch_listing()
    checks += check_plugins(listing_json if listing_json is not None else "")
    for line in render(checks):
        out(line)
    failed = sum(1 for c in checks if c.required and not c.ok)
    out("doctor: all required checks passed" if failed == 0 else f"doctor: {failed} required check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
