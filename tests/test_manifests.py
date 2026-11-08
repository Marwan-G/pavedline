import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class ManifestTests(unittest.TestCase):
    def test_marketplace_lists_pavedline(self):
        m = load(".claude-plugin/marketplace.json")
        self.assertEqual(m["name"], "pavedline")
        sources = [p.get("source") for p in m["plugins"]]
        self.assertIn("./plugins/pavedline", sources)
        self.assertEqual(
            m["allowCrossMarketplaceDependenciesOn"],
            ["claude-plugins-official", "knowledge-work-plugins", "ui-ux-pro-max-skill"],
        )

    def test_plugin_manifest(self):
        p = load("plugins/pavedline/.claude-plugin/plugin.json")
        self.assertEqual(p["name"], "pavedline")
        self.assertEqual(p["version"], (ROOT / "VERSION").read_text().strip())
        self.assertEqual(p["license"], "MIT")
        self.assertEqual(
            p["dependencies"],
            [
                "superpowers@claude-plugins-official",
                "mattpocock-skills@claude-plugins-official",
                "product-management@knowledge-work-plugins",
                "figma@claude-plugins-official",
                "ui-ux-pro-max@ui-ux-pro-max-skill",
            ],
        )

    def test_mcp_pins_playwright(self):
        mcp = load("plugins/pavedline/.mcp.json")
        servers = mcp.get("mcpServers", mcp)
        args = servers["playwright"]["args"]
        self.assertIn("@playwright/mcp@0.0.84", args)
        self.assertIn("--headless", args)


if __name__ == "__main__":
    unittest.main()
