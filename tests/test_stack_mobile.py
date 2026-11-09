import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/pavedline"
PACK = PLUGIN / "stacks/nextjs-fastapi"
FILES = PACK / "files"
MOBILE = FILES / "apps/mobile"
API = FILES / "services/api"
SKILL = PLUGIN / "skills/mobile-build"
EXACT = re.compile(r"^\d+\.\d+\.\d+$")

# Expo SDK 58 version table (bundledNativeModules.json of expo 58.0.19) and the other exact pins.
PINS = {
    "expo": "58.0.19", "react": "19.3.0", "react-native": "0.88.0", "expo-constants": "58.0.13",
    "expo-status-bar": "58.0.4", "jest-expo": "58.0.12", "@testing-library/react-native": "14.1.0",
    "eslint-plugin-react-native-a11y": "3.5.1", "typescript": "5.9.3",
}
RULING_8_URL = "https://docs.github.com/en/actions/reference/runners/github-hosted-runners"


def pack_yaml():
    return (PACK / "pack.yaml").read_text()


def mobile_block():
    text = pack_yaml()
    m = re.search(r"^  mobile:\n(.*?)(?=^  \w|^\S)", text, flags=re.M | re.S)
    return m.group(1) if m else ""


class MobileFiles(unittest.TestCase):
    def test_files_exist(self):
        for rel in ("package.json", "tsconfig.json", "app.config.ts", "index.ts", "eslint.config.mjs", ".gitignore",
                    "src/App.tsx", "src/UpdateRequired.tsx", "src/version.ts", "src/health.ts", "src/config.ts",
                    "src/__tests__/App.test.tsx", "src/__tests__/version.test.ts", "src/__tests__/health.test.ts"):
            self.assertTrue((MOBILE / rel).is_file(), rel)

    def test_pins_are_exact_and_match_the_expo_table(self):
        pkg = json.loads((MOBILE / "package.json").read_text())
        deps = {**pkg["dependencies"], **pkg.get("devDependencies", {})}
        for name, version in deps.items():
            self.assertRegex(version, EXACT, name)
        for name, version in PINS.items():
            self.assertEqual(deps.get(name), version, name)
        self.assertEqual(pkg["name"], "@app/mobile")
        self.assertEqual(pkg["jest"]["preset"], "jest-expo")
        for script in ("lint", "typecheck", "test", "prebuild"):
            self.assertIn(script, pkg["scripts"])

    def test_typescript_is_strict(self):
        ts = (MOBILE / "tsconfig.json").read_text()
        self.assertIn('"strict": true', ts)

    def test_a11y_rule_set_is_enabled(self):
        t = (MOBILE / "eslint.config.mjs").read_text()
        self.assertIn("eslint-plugin-react-native-a11y", t)
        self.assertIn("Biome cannot lint", t)
        self.assertIn("a11y.configs.all.rules", t)
        # every rule of the set is forced to error, so a warning level can never pass the lint
        self.assertIn("Object.fromEntries(Object.keys(a11y.configs.all.rules).map((name) => [name, 'error']))", t)
        self.assertNotIn("'warn'", t)
        self.assertIn("'react-native-a11y/has-accessibility-hint': 'off'", t)

    def test_skill_signing_rules_are_stated(self):
        s = (ROOT / "plugins/pavedline/skills/mobile-build/SKILL.md").read_text()
        for needle in ("process list", "chmod 600", "never runs on a self-hosted", "required reviewers",
                       "pull_request", "list-keychains", "ASC_KEY", "Volksverpetzer/eslint-plugin-react-native-a11y"):
            self.assertIn(needle, s)

    def test_native_projects_and_signing_material_are_ignored_and_absent(self):
        ignore = (MOBILE / ".gitignore").read_text()
        for needle in ("android/", "ios/", ".expo/", "*.p12", "*.keystore", "*.jks", "*.mobileprovision", "*.p8"):
            self.assertIn(needle, ignore)
        for bad in ("android", "ios", "node_modules", ".expo"):
            self.assertFalse((MOBILE / bad).exists(), bad)
        tracked = subprocess.run(["git", "ls-files", str(PACK)], cwd=ROOT, capture_output=True, text=True).stdout.split()
        for path in tracked:
            self.assertFalse(re.search(r"\.(p12|jks|keystore|mobileprovision|p8|pem)$", path), path)
            self.assertNotEqual(pathlib.Path(path).name, "eas.json", path)
            self.assertNotRegex(path, r"apps/mobile/(android|ios)/")

    def test_config_has_placeholders_and_no_eas_or_store_config(self):
        t = (MOBILE / "app.config.ts").read_text()
        self.assertIn("com.example.app", t)
        for bad in ("projectId", "eas", "updates", "owner:", "credentials", "keystore"):
            self.assertNotIn(bad, t)
        self.assertIn("EXPO_PUBLIC_API_BASE_URL", t)

    def test_update_screen_has_no_way_past(self):
        t = (MOBILE / "src/UpdateRequired.tsx").read_text()
        self.assertNotIn("Pressable", t)
        self.assertNotIn("Button", t)
        self.assertNotIn("Linking", t)
        self.assertIn("accessibilityLabel", t)

    def test_screens_have_accessible_labels(self):
        t = (MOBILE / "src/App.tsx").read_text()
        self.assertIn("accessibilityLabel", t)
        self.assertIn("accessibilityRole", t)
        self.assertIn("/healthz", (MOBILE / "src/health.ts").read_text())

    def test_lockfile_has_the_mobile_importer(self):
        lock = (FILES / "pnpm-lock.yaml").read_text()
        self.assertRegex(lock, r"(?m)^  apps/mobile:$")
        self.assertIn("expo@58.0.19", lock)

    def test_workspace_files_unchanged_in_shape(self):
        self.assertIn("apps/*", (FILES / "pnpm-workspace.yaml").read_text())

    def test_example_overlay_is_not_polluted(self):
        self.assertFalse((PACK / "example/apps/mobile").exists())


class PackYaml(unittest.TestCase):
    def test_mobile_surface(self):
        block = mobile_block()
        self.assertTrue(block, "no mobile surface in pack.yaml")
        self.assertIn("apps/mobile", block)
        self.assertIn('"# pavedline-surface: mobile"', block)
        for cmd in ("install:", "lint:", "types:", "test:", "prebuild:", "android_build:", "ios_build:"):
            self.assertIn(cmd, block)
        self.assertNotRegex(block, r"(?m)^    infra:")  # mobile is not deployed to Kubernetes
        self.assertIn("CI-only", block)

    def test_shared_files_are_needed_by_mobile(self):
        self.assertRegex(pack_yaml(), r"needed_by: \[web, site, mobile\]")

    def test_skill_is_enabled(self):
        self.assertIn("  - mobile-build", pack_yaml())


class SkillAndSources(unittest.TestCase):
    def test_skill_files(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertLessEqual(len(text.splitlines()), 150)
        self.assertRegex(text, r"(?m)^name: mobile-build$")
        for needle in ("temporary keychain", "deleted", "founder step", "ask-before-adding", "Ruling 8", RULING_8_URL,
                       "security create-keychain", "security import", "security delete-keychain", "always()",
                       "expo prebuild", "SERVICES.md", "X-Min-App-Version", "react-native-a11y", "macos-26"):
            self.assertIn(needle, text, needle)

    def test_sources_have_urls_and_dates(self):
        s = (SKILL / "references/sources.md").read_text()
        self.assertIn(RULING_8_URL, s)
        self.assertIn("2026-11-09", s)
        for pin in ("expo@58.0.19", "react-native@0.88.0", "jest-expo@58.0.12"):
            self.assertIn(pin, s)
        self.assertIn("docs.expo.dev/guides/monorepos", s)

    def test_pack_sources_list_mobile_pins(self):
        t = (PACK / "SOURCES.md").read_text()
        for needle in ("`expo`", "`react-native`", "`eslint-plugin-react-native-a11y`", "58.0.19"):
            self.assertIn(needle, t)


class MinAppVersionHeader(unittest.TestCase):
    def test_api_pack_sends_the_header(self):
        test = (API / "tests/test_min_app_version.py").read_text()
        self.assertIn("X-Min-App-Version", test)
        self.assertIn("min_app_version", (API / "app/settings.py").read_text())
        self.assertIn("MinAppVersionMiddleware", (API / "app/main.py").read_text())

    def test_documented_in_skills_and_example_contract(self):
        for rel in ("fastapi-service", "api-contract"):
            self.assertIn("X-Min-App-Version", (PLUGIN / f"skills/{rel}/SKILL.md").read_text(), rel)
        contract = (PACK / "example/docs/api/openapi.yaml").read_text()
        self.assertIn("X-Min-App-Version", contract)
        self.assertRegex(contract, r"(?m)^  headers:$")


if __name__ == "__main__":
    unittest.main()
