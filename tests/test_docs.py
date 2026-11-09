import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)|src=\"([^\"]+)\"")


def doc_files():
    files = [ROOT / "README.md", ROOT / "CREDITS.md", ROOT / "THIRD_PARTY_NOTICES.md"]
    files += sorted((ROOT / "docs").glob("*.md"))
    files += sorted((ROOT / "docs" / "steps").glob("*.md"))
    return files


class Docs(unittest.TestCase):
    def test_expected_files_exist(self):
        for rel in ("CREDITS.md", "THIRD_PARTY_NOTICES.md", "docs/environments.md", "docs/faq.md",
                    "docs/steps/00-start.md", "docs/steps/01-market.md",
                    "docs/steps/02-grill.md", "docs/steps/03-spec.md"):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_readme_links_resolve(self):
        for f in doc_files():
            text = f.read_text()
            for m in LINK.finditer(text):
                target = next(g for g in m.groups() if g)
                if re.match(r"^(https?:|mailto:|#)", target):
                    continue
                path = target.split("#")[0]
                self.assertTrue((f.parent / path).exists(), f"{f.name}: broken link {target}")

    def test_credits_cover_dependencies(self):
        credits = (ROOT / "CREDITS.md").read_text()
        manifest = json.loads((ROOT / "plugins/pavedline/.claude-plugin/plugin.json").read_text())
        for dep in manifest["dependencies"]:
            name = dep.split("@")[0]
            self.assertIn(name, credits, name)
        mcp = json.loads((ROOT / "plugins/pavedline/.mcp.json").read_text())
        for server in mcp["mcpServers"].values():
            for arg in server["args"]:
                if arg.startswith("@"):
                    self.assertIn(arg.rsplit("@", 1)[0], credits, arg)

    def test_readme_status_line(self):
        self.assertIn("Status: v0.1.", (ROOT / "README.md").read_text())

    def test_readme_says_what_it_sets_up(self):
        t = (ROOT / "README.md").read_text()
        self.assertIn("## What it sets up on your machine", t)
        self.assertLess(t.index("## What it sets up on your machine"), t.index("## Install"))
        env = {}
        for line in (ROOT / "plugins/pavedline/scripts/local-cluster/versions.env").read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k] = v
        k8s = re.search(r"kindest/node:(v[\d.]+)@", env["KIND_NODE_IMAGE"]).group(1)
        for needle in [f"Kubernetes {k8s}", f"Helm chart {env['ARGOCD_CHART_VERSION']}",
                       f"Helm chart {env['CNPG_CHART_VERSION']}", f"localhost:{env['REGISTRY_PORT']}",
                       "kind-pavedline-<project>", "loopback only", "down.sh <project> --all", "**Tested on:**"]:
            self.assertIn(needle, t, needle)
        self.assertNotRegex(t, r"@[A-Z_]+@", "unfilled README placeholder")

    def test_readme_privacy_and_install(self):
        t = (ROOT / "README.md").read_text()
        self.assertIn("Pavedline collects nothing. Every answer stays in your own repository.", t)
        self.assertIn("/plugin marketplace add Marwan-G/pavedline", t)
        install = t.split("## Why Pavedline exists")[0].split("## Install")[1]
        self.assertIn("/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill", install)
        self.assertIn("marketplace line is optional", install)
        self.assertNotIn("`figma`, `ui-ux-pro-max`", install)
        self.assertIn("ui-ux-pro-max", t.split("## Install")[1])
        arch = (ROOT / "docs/architecture.md").read_text()
        self.assertIn("`ui-ux-pro-max` (optional)", arch)
        self.assertNotIn("five dependencies", arch)
        self.assertIn("CREDITS.md", t)

    def test_third_party_notice(self):
        n = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertIn("saas-multi-tenant", n)
        self.assertIn("Copyright (c) 2026 Antigravity User", n)


    def test_contributing_headless_and_dependency_notes(self):
        t = (ROOT / "CONTRIBUTING.md").read_text()
        for s in ("silently loads nothing", "--add-dir", "--output-format stream-json --verbose", "no `timeout` command"):
            self.assertIn(s, t, s)

    def test_architecture_counts_match_tree(self):
        t = (ROOT / "docs/architecture.md").read_text()
        plug = ROOT / "plugins/pavedline"
        skills = len([d for d in (plug / "skills").iterdir() if (d / "SKILL.md").is_file()])
        agents = len(list((plug / "agents").glob("*.md")))
        self.assertIn("**%d skills, %d agents, MCP**" % (skills, agents), t)
        dot = (ROOT / "ARCHITECTURE.dot").read_text()
        self.assertIn("Skills (%d)" % skills, dot)
        self.assertIn("Agents (%d)" % agents, dot)


if __name__ == "__main__":
    unittest.main()
