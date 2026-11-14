"""Build-time events: the register ships with the API stack and every step names its part."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PLUGIN = ROOT / "plugins" / "pavedline"
STACK = PLUGIN / "stacks" / "nextjs-fastapi"


def text(rel):
    return (PLUGIN / rel).read_text()


class EventsRegister(unittest.TestCase):
    def test_the_register_and_its_check_ship_with_the_api_surface(self):
        pack = (STACK / "pack.yaml").read_text()
        api = pack.split("  api:")[1].split("\n  web:")[0]
        self.assertIn("scripts/events_check.py", api)
        self.assertIn("docs/observability/EVENTS.md", api)
        self.assertTrue((STACK / "files/docs/observability/EVENTS.md").is_file())
        self.assertTrue((STACK / "files/scripts/events_check.py").is_file())
        self.assertTrue((STACK / "files/services/api/app/events.py").is_file())

    def test_ci_and_the_starter_run_the_check(self):
        ci = (STACK / "files/.github/workflows/ci-api.yml").read_text()
        self.assertIn("python3 ../../scripts/events_check.py --root ../..", ci)
        self.assertIn('"scripts/events_check.py"', ci)
        self.assertIn("step api-events-check a_events", (ROOT / "scripts/starter_check.sh").read_text())

    def test_the_api_no_longer_logs_plain_text(self):
        main = (STACK / "files/services/api/app/main.py").read_text()
        self.assertNotIn("logging.basicConfig", main)
        self.assertIn("configure_logging(settings.log_level)", main)

    def test_each_step_names_its_part(self):
        for rel, needles in {
            "skills/system-architecture/references/questions.md": ["docs/observability/EVENTS.md", "chosen at step 12"],
            "skills/plan-graph/SKILL.md": ["Events: <event names this slice adds, or none>", "failure paths"],
            "skills/quality-gates/SKILL.md": ["scripts/events_check.py", "log-event <namespace> <deployment> <event>",
                                              "every new error path logs one"],
            "skills/quality-gates/references/reviewer-prompts.md": ["`log_event` field"],
            "agents/builder.md": ["docs/observability/EVENTS.md", "never secrets, bodies or personal data"],
            "agents/reviewer.md": ["docs/observability/EVENTS.md"],
            "skills/deploy/SKILL.md": ["`log-event <namespace> <deployment> <event>`", "never printed"],
            "skills/lessons/SKILL.md": ["**An event.**"],
            "skills/go-to-production/references/launch.md": ["docs/observability/EVENTS.md", "alert candidates"],
            "templates/docs/production/LAUNCH.md": ["docs/observability/EVENTS.md"],
            "templates/docs/rules-index.md": ["docs/observability/EVENTS.md"],
            "templates/.github/pull_request_template.md": ["log-event <namespace> <deployment> <event>"],
            "stacks/nextjs-fastapi/files/scripts/deploy_local.sh": ["log-event <ns> <deployment> <event>"],
            "skills/fastapi-service/SKILL.md": ["clear_log_context()", "hide_parameters=True"],
        }.items():
            t = text(rel)
            for n in needles:
                self.assertIn(n, t, "%s: %s" % (rel, n))

    def test_the_builder_rules_stay_numbered(self):
        t = text("agents/builder.md")
        nums = [int(line.split(".")[0]) for line in t.splitlines() if line[:2].rstrip(".").isdigit() and ". **" in line[:6]]
        self.assertEqual(nums, list(range(1, len(nums) + 1)))

    def test_the_step_10_page_lists_the_verb(self):
        self.assertIn("log-event <namespace> <deployment> <event>", (ROOT / "docs/steps/10-deploy.md").read_text())

    def test_the_spec_keeps_tools_out_and_events_in(self):
        spec = (ROOT / "docs/superpowers/specs/2026-11-07-pavedline-design.md").read_text()
        self.assertIn("Observability and tracing tools (decided)", spec)
        self.assertIn("docs/observability/EVENTS.md", spec)


if __name__ == "__main__":
    unittest.main()
