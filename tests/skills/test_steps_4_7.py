import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "plugins" / "pavedline" / "skills"
sys.path.insert(0, str(ROOT / "scripts"))


PINNED = "npx @redocly/cli@2.71.0 lint docs/api/openapi.yaml"
S5 = ("domain-model", "db-schema", "multi-tenancy", "api-contract")


def read(name):
    d = SKILLS / name
    parts = [(d / "SKILL.md").read_text()]
    for f in sorted((d / "references").glob("*.md")) if (d / "references").is_dir() else []:
        parts.append(f.read_text())
    return "\n".join(parts)


def ordered(t, marks):
    idx = [t.index(m) for m in marks]
    return idx == sorted(idx)


class Step4Contracts(unittest.TestCase):
    def test_rounds_in_order(self):
        t = read("system-design")
        self.assertTrue(ordered(t, ["## Round 1: platform", "## Round 2: behaviour", "## Round 3: reach"]))

    def test_every_area_has_a_heading(self):
        q = (SKILLS / "system-design/references/questions.md").read_text()
        areas = ["Backend", "Auth", "Security and compliance", "Concurrency", "Time and scheduling",
                 "Scheduled jobs", "Performance", "Images and files", "Real-time", "Notifications",
                 "Payments taken by tenants", "Billing", "Accessibility", "Mobile offline", "Multi-region",
                 "Service mesh", "Website, blog and SEO", "Search", "Availability and recovery"]
        heads = re.findall(r"^## (.+)$", q, re.M)
        self.assertEqual(heads, areas)

    def test_exact_strings(self):
        t = read("system-design")
        for s in ("Clerk (default), or do you need something else?",
                  '"Not needed" is valid only with a recorded reason',
                  "Next.js is frontend only", "WCAG 2.2 AA", "never designed to a free tier"):
            self.assertIn(s, t)

    def test_outputs_named(self):
        t = read("system-design")
        for s in ("docs/architecture/SYSTEM-DESIGN.md", "docs/architecture/AUTH.md",
                  "docs/architecture/TENANCY-LIFECYCLE.md", "docs/production/LEAD-TIME.md", "WAITING.md"):
            self.assertIn(s, t)

    def test_tenancy_stages(self):
        t = (SKILLS / "system-design/references/tenancy-lifecycle.md").read_text()
        for s in ("Create", "Sync and repair", "Suspend / offboard", "Export", "Delete", "Legal surface",
                  "Support access", "Limits"):
            self.assertIn("**%s**" % s, t)
        self.assertEqual(len(re.findall(r"^\d\. \*\*", t, re.M)), 8)
        self.assertIn("not applicable (decision 0002)", t)

    def test_reentry(self):
        t = read("system-design")
        self.assertIn("STALE", t)
        self.assertIn("supersedes", t)

    def test_surfaces(self):
        t = read("system-design")
        self.assertIn("decision 0005", t)
        self.assertIn("questions for a dropped surface are skipped", t)

    def test_v01_projects_get_folders(self):
        t = read("system-design")
        self.assertIn("when missing", t)
        self.assertIn("when missing", read("backend-evaluate"))

    def test_backend_evaluate(self):
        t = read("backend-evaluate")
        for s in ("FastAPI is the preferred default",
                  "every must-have need has a supported, maintained path",
                  "no blocker in concurrency, real-time or background work",
                  "the team can run it", "the founder decides", "The founder decides"):
            self.assertIn(s, t)

    def test_sources_have_urls_and_dates(self):
        t = (SKILLS / "system-design/references/sources.md").read_text()
        self.assertIn("https://", t)
        self.assertRegex(t, r"2026-\d\d-\d\d")

    def test_spec_points_to_system_design(self):
        t = read("spec")
        self.assertNotIn("later Pavedline release", t)
        self.assertIn("system-design", t.split("## 6. Close step 3")[1])

    def test_step_page_linked(self):
        self.assertTrue((ROOT / "docs/steps/04-system-design.md").exists())
        self.assertIn("04-system-design.md", (ROOT / "docs/steps/03-spec.md").read_text())




class ReferencePaths(unittest.TestCase):
    """A skill's references live in the plugin, outside the project: name them with ${CLAUDE_SKILL_DIR}."""

    def test_references_use_skill_dir(self):
        for name in ("system-design", "backend-evaluate") + S5:
            t = (SKILLS / name / "SKILL.md").read_text()
            self.assertNotRegex(t, r"(?<!\})/?(?<![\w/])`references/", name)
            self.assertIn("${CLAUDE_SKILL_DIR}/references/", t, name)


class RoundCompleteness(unittest.TestCase):
    def test_no_area_skipped_or_merged(self):
        t = read("system-design")
        self.assertIn("merged into another area", t)
        self.assertIn("before closing a round compare the areas", t)




class Step5Contracts(unittest.TestCase):
    def test_skills_exist_with_sources(self):
        for n in S5:
            self.assertTrue((SKILLS / n / "SKILL.md").exists(), n)
        for n in ("db-schema", "multi-tenancy", "api-contract"):
            s = (SKILLS / n / "references/sources.md").read_text()
            self.assertIn("https://", s, n)
            self.assertRegex(s, r"2026-\d\d-\d\d", n)

    def test_outputs_named(self):
        t = "\n".join(read(n) for n in S5)
        for s in ("docs/data/DOMAIN.md", "docs/data/erd.dot", "docs/data/SCHEMA.md",
                  "docs/data/MIGRATIONS.md", "docs/api/openapi.yaml"):
            self.assertIn(s, t)

    def test_multi_tenancy_rules(self):
        t = read("multi-tenancy")
        for s in ("does not own", "BYPASSRLS", "FORCE ROW LEVEL SECURITY", "current_setting('app.tenant_id')",
                  "SET LOCAL", "session advisory locks", "Storage keys start with the tenant id",
                  "cross-tenant leak test", "not applicable (decision 0002)"):
            self.assertIn(s, t)

    def test_db_schema_rules(self):
        t = read("db-schema")
        for s in ("expand/contract", "every migration has a `down`", "never float", "read as text"):
            self.assertIn(s, t)

    def test_api_contract_rules(self):
        t = read("api-contract")
        for s in ("/v1", "Idempotency-Key", "the tenant comes from the verified token", PINNED,
                  "the step is not done"):
            self.assertIn(s, t)
        self.assertIn(PINNED, (SKILLS / "api-contract/references/sources.md").read_text())

    def test_gate_text(self):
        t = "\n".join(read(n) for n in S5)
        self.assertIn("VERDICT: APPROVE", t)
        self.assertIn("before the founder's go", t)
        self.assertIn("never arguing past it", t)
        self.assertIn("blind", t)

    def test_glossary_first(self):
        t = read("domain-model")
        self.assertIn("GLOSSARY.md", t)
        self.assertIn("adds the missing terms to `GLOSSARY.md` before using them", t)

    def test_step_skills_share_the_protocol(self):
        for n in S5:
            t = (SKILLS / n / "SKILL.md").read_text()
            self.assertIn("decisions/0000-template.md", t, n)
            self.assertIn("when missing", t, n)
            self.assertIn("${CLAUDE_SKILL_DIR}/references/", t, n)

    def test_tenant_column_name_is_fixed(self):
        for n in ("multi-tenancy", "db-schema", "domain-model"):
            t = read(n)
            self.assertIn("even when the glossary calls the tenant something else", t, n)
            self.assertIn("`tenant_id`", t, n)

    def test_cross_checks_before_writing(self):
        t = read("domain-model")
        self.assertIn("Cross-check the decisions against each other", t)
        for s in ("Entry points before the tenant is known", "People and logins", "Plan limits"):
            self.assertIn(s, t)

    def test_closes_to_step_6(self):
        self.assertIn("STEP: 6", read("api-contract"))

    def test_step_page_linked(self):
        self.assertTrue((ROOT / "docs/steps/05-data-and-api.md").exists())
        self.assertIn("05-data-and-api.md", (ROOT / "docs/steps/04-system-design.md").read_text())

    def test_credits(self):
        self.assertIn("saas-multi-tenant", (ROOT / "CREDITS.md").read_text())
        n = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertIn("saas-multi-tenant", n)
        self.assertIn("Permission is hereby granted", n)


class WorkflowLessons(unittest.TestCase):
    STEP45 = ("system-design", "domain-model", "db-schema", "multi-tenancy", "api-contract")

    def has(self, name, *needles):
        t = read(name)
        for n in needles:
            self.assertIn(n, t, "%s: %s" % (name, n))

    def test_auth_area(self):
        self.has("system-design", "session lifetime", "sign-up abuse limit")

    def test_support_access_grant(self):
        self.has("system-design", "grant duration")

    def test_delete_third_party(self):
        self.has("system-design", "third-party copies")

    def test_noindex(self):
        self.has("system-design", "noindex")

    def test_default_deny(self):
        self.has("system-design", "default-deny")

    def test_one_approval_turn(self):
        for n in self.STEP45:
            self.has(n, "one approval turn")
        self.assertIn("one approval turn", (ROOT / "plugins/pavedline/agents/architect.md").read_text())

    def test_fast_path(self):
        for n in self.STEP45:
            self.has(n, "default for the rest of this round")

    def test_records_consistency_pass(self):
        t = read("system-design")
        self.assertIn("reviewer", t)
        self.assertIn("VERDICT: REJECT", t)
        self.assertLess(t.index("VERDICT: REJECT"), t.index("STEP: 5 \u2014 Data and API"))

    def test_spec_data_subjects(self):
        self.has("spec", "age limit", "default retention")

    def test_api_contract_lessons(self):
        self.has("api-contract", "documented exception", "webhook event names", "ignored problems")

    def test_cross_tenant_job(self):
        self.has("multi-tenancy", "cross-tenant job")

    def test_reviewer_rule_4(self):
        t = (ROOT / "plugins/pavedline/agents/reviewer.md").read_text()
        self.assertIn("checks by reading only", t)
        self.assertNotIn("targeted checks", t)


class GateRecords(unittest.TestCase):
    def test_verdict_files(self):
        for n, f in (("system-design", "04-system-design-review.md"), ("api-contract", "05-data-and-api-review.md")):
            t = read(n)
            self.assertIn("docs/reviews/", t, n)
            self.assertIn(f, t, n)
            self.assertIn("LAST", t, n)

    def test_contract_checks(self):
        t = read("api-contract")
        for s in ("minimised fields", "every decided behaviour", "forbidden synonyms"):
            self.assertIn(s, t, s)

    def test_leak_test_exemption_reasons(self):
        self.assertIn("reason per exemption", read("multi-tenancy"))

    def test_polish(self):
        t = read("api-contract")
        self.assertIn("`decisions/`, the list of ignored problems, and the checklist", t)
        self.assertIn("(the audited admin role does not have it unless a decision says so)", read("multi-tenancy"))


class Step6Architecture(unittest.TestCase):
    def test_outputs_named(self):
        t = read("system-architecture") + read("threat-model")
        for s in ("docs/architecture/ARCHITECTURE.dot", "ARCHITECTURE.svg", "docs/architecture/DEPLOYMENT.md",
                  "docs/architecture/THREATS.md", "values-local.yaml", "values-staging.yaml",
                  "values-production.yaml", "namespace"):
            self.assertIn(s, t, s)

    def test_pack_and_gateway(self):
        t = read("system-architecture")
        self.assertIn("nextjs-fastapi", t)
        self.assertIn("Gateway API", t)
        self.assertIn("copied in a later release", t)

    def test_diagram_path_is_exact(self):
        self.assertIn("exactly that path", read("system-architecture"))
        self.assertIn("never write the system diagram there instead", read("system-architecture"))

    def test_no_templates_copied(self):
        t = read("system-architecture")
        self.assertIn("copies no stack templates", t)

    def test_every_step4_service_in_diagram(self):
        t = read("system-architecture")
        self.assertIn("every service named in `SYSTEM-DESIGN.md` and `SERVICES.md` appears in the diagram", t)
        self.assertIn("dot -Tcanon", t)

    def test_threat_areas(self):
        t = read("threat-model")
        for s in ("tenancy", "auth", "secrets", "uploads", "webhooks", "decision 0003", "compliance",
                  "mitigation", "enforced"):
            self.assertIn(s, t, s)
        self.assertIn("no row lacks a mitigation or an enforcement place", t)
        self.assertIn("every threat has a mitigation and an enforcement place", t)
        for s in ("id (`T-01`", "threat (what an attacker", "asset", "**mitigation**",
                  "**where it is enforced**", "the check that proves it"):
            self.assertIn(s, t, s)
        for s in ("`docs/architecture/ARCHITECTURE.dot`", "`docs/architecture/DEPLOYMENT.md`"):
            self.assertIn(s, t.split("## 2.")[0], s)

    def test_protocol(self):
        for n in ("system-architecture", "threat-model"):
            t = (SKILLS / n / "SKILL.md").read_text()
            for s in ("decisions/0000-template.md", "when missing", "${CLAUDE_SKILL_DIR}/references/",
                      "one approval turn", "default for the rest of this round", "ask-before-adding"):
                self.assertIn(s, t, "%s: %s" % (n, s))

    def test_gate_and_state(self):
        t = read("threat-model")
        self.assertIn("VERDICT: APPROVE", t)
        self.assertIn("docs/reviews/06-architecture-review.md", t)
        self.assertIn("STEP: 7", t)
        self.assertIn("go?", t)
        self.assertIn("LAST", t)
        self.assertIn("reviewer APPROVE, see docs/reviews/06-architecture-review.md", t)
        self.assertIn("docs/reviews/06-architecture-review.md",
                      (ROOT / "docs/steps/06-architecture.md").read_text())
        self.assertLess(t.index("VERDICT: APPROVE"), t.index("STEP: 7"))

    def test_sources_and_page(self):
        self.assertIn("https://", (SKILLS / "system-architecture/references/sources.md").read_text())
        self.assertTrue((ROOT / "docs/steps/06-architecture.md").exists())
        self.assertIn("06-architecture.md", (ROOT / "docs/steps/05-data-and-api.md").read_text())


ALL9 = ("system-design", "domain-model", "db-schema", "multi-tenancy", "api-contract",
        "system-architecture", "threat-model", "design-system-contract", "backend-evaluate")


class FinalReviewFixes(unittest.TestCase):
    def test_question_once_sentence(self):
        for n in ALL9:
            self.assertIn("decided in NNNN", read(n), n)
        self.assertNotIn("treated as already settled", read("system-design"))

    def test_narrowed_overlaps(self):
        self.assertIn("Identifiers decision", read("multi-tenancy"))
        self.assertIn("given decision 0006", (SKILLS / "system-architecture/references/questions.md").read_text())
        self.assertIn("beyond the Concurrency decision", read("api-contract"))

    def test_step_pages_name_review_files(self):
        for page, f in (("04-system-design.md", "04-system-design-review.md"),
                        ("05-data-and-api.md", "05-data-and-api-review.md"),
                        ("06-architecture.md", "06-architecture-review.md"),
                        ("07-figma.md", "07-figma-review.md")):
            self.assertIn("docs/reviews/" + f, (ROOT / "docs/steps" / page).read_text(), page)
        self.assertIn("BACKEND-EVALUATION.md", (ROOT / "docs/steps/04-system-design.md").read_text())
        self.assertIn("`reviewer`", (ROOT / "docs/steps/04-system-design.md").read_text())

    def test_min_app_version(self):
        self.assertIn("minimum supported app version", read("api-contract"))
        self.assertIn("minimum supported app version", read("system-architecture"))

    def test_idempotency_scoped(self):
        t = read("api-contract")
        for s in ("request fingerprint", "(tenant_id, principal, key)", "FORCE RLS", "422"):
            self.assertIn(s, t, s)
        self.assertNotIn("different body is a conflict", t)

    def test_openapi_31(self):
        self.assertIn("openapi: 3.1.x", read("api-contract"))
        self.assertIn("redocly-cli", (SKILLS / "api-contract/references/sources.md").read_text())

    def test_design_wording(self):
        t = read("design-system-contract")
        self.assertNotIn("the six required", t)
        self.assertIn("every required screen that applies", t)
        self.assertIn("a finding may cite node ids", t)
        self.assertNotIn("motion", (ROOT / "plugins/pavedline/templates/docs/design/README.md").read_text())

    def test_root_overview_wording(self):
        tpl = ROOT / "plugins/pavedline/templates"
        self.assertIn("docs/architecture/ARCHITECTURE.dot", (tpl / "docs/architecture/README.md").read_text())
        self.assertNotIn("first\n`ARCHITECTURE.dot`", (tpl / "docs/architecture/README.md").read_text())
        self.assertIn("step 6 updates the root overview", (tpl / "ARCHITECTURE.dot").read_text())
        self.assertIn("step 6 updates the root overview", read("system-architecture"))

    def test_leak_test_and_sample(self):
        t = (SKILLS / "multi-tenancy/references/rules.md").read_text()
        self.assertIn("errors or returns no rows", t)
        self.assertNotIn("SET LOCAL app.tenant_id = '<verified", t)
        self.assertIn("set_config('app.tenant_id', $1, true)", t)

    def test_step_chain(self):
        def close(n):
            return re.search(r"^STEP: (\d — [A-Za-z ]+)$", read(n), re.M).group(1)
        for prev, nxt in (("spec", "system-design"), ("system-design", "domain-model"),
                          ("api-contract", "system-architecture"), ("threat-model", "design-system-contract")):
            self.assertIn("`STEP: %s`" % close(prev), read(nxt), nxt)

    def test_agents_resolve(self):
        agents = ROOT / "plugins/pavedline/agents"
        for f in SKILLS.rglob("*.md"):
            for a in re.findall(r"pavedline:([a-z-]+)", f.read_text()):
                if a not in ("doctor", "start"):
                    self.assertTrue((agents / (a + ".md")).exists(), "%s: %s" % (f.name, a))


STEP_PAGES = {
    "04-system-design.md": "05-data-and-api.md",
    "05-data-and-api.md": "06-architecture.md",
    "06-architecture.md": "07-figma.md",
}


class StepPagesEnd(unittest.TestCase):
    def test_next_line_form(self):
        for page, nxt in STEP_PAGES.items():
            last = (ROOT / "docs/steps" / page).read_text().rstrip().splitlines()[-1]
            self.assertRegex(last, r"^Next: \[step \d+: [^\]]+\]\(%s\)\.$" % re.escape(nxt), page)
        last = (ROOT / "docs/steps/07-figma.md").read_text().rstrip().splitlines()[-1]
        self.assertRegex(last, r"^Next: step 8 .*later release\.$")


class Step7Figma(unittest.TestCase):
    def test_skill_files(self):
        s = SKILLS / "design-system-contract"
        self.assertTrue((s / "SKILL.md").exists())
        self.assertIn("${CLAUDE_SKILL_DIR}/references/", (s / "SKILL.md").read_text())
        self.assertIn("https://", (s / "references/sources.md").read_text())
        self.assertRegex((s / "references/sources.md").read_text(), r"2026-\d\d-\d\d")

    def test_outputs_and_contract(self):
        t = read("design-system-contract")
        for s in ("docs/design/DESIGN.md", "docs/design/tokens.json", "light and dark", "Figma name = code name",
                  "every screen in every state", "empty", "loading", "error", "success", "no permission",
                  "offline on mobile", "accessibility annotations", "node links", "one frame set per surface"):
            self.assertIn(s, t, s)

    def test_required_screens(self):
        t = read("design-system-contract")
        for s in ("suspended tenant, export, delete, impersonation banner", "legal pages",
                  "please update"):
            self.assertIn(s, t, s)

    def test_figma_skills_named(self):
        t = read("design-system-contract")
        for s in ("`figma-use`", "`figma-generate-library`", "`figma-generate-design`", "`figma-use-figjam`",
                  "`figma-code-connect`", "`impeccable`", "`ui-ux-pro-max`"):
            self.assertIn(s, t, s)

    def test_code_connect_and_fallback(self):
        t = read("design-system-contract")
        self.assertIn("Code Connect", t)
        self.assertIn("Figma-name to code-name table", t)
        self.assertIn("Organization or Enterprise plan", t)
        self.assertIn("try the mapping once", t)

    def test_agents_foreground_and_team(self):
        t = read("design-system-contract")
        for s in ("pavedline:designer", "pavedline:design-verifier", "never a general-purpose agent",
                  "never schedule a wake-up", "never left in drafts"):
            self.assertIn(s, t, s)

    def test_gate_and_login(self):
        t = read("design-system-contract")
        self.assertIn("DESIGN VERDICT: APPROVE", t)
        self.assertIn("docs/reviews/07-figma-review.md", t)
        self.assertIn("then the founder approves the visual", t)
        self.assertIn("never approves a visual", t)
        self.assertIn("If the Figma login is missing, stop and add it to `WAITING.md`", t)
        self.assertLess(t.index("DESIGN VERDICT: APPROVE"), t.index("STEP: 8"))
        self.assertIn("step 8 ships in a later release", t)
        self.assertIn("go?", t)

    def test_protocol(self):
        t = (SKILLS / "design-system-contract/SKILL.md").read_text()
        for s in ("decisions/0000-template.md", "when missing", "one approval turn",
                  "default for the rest of this round", "ask-before-adding", "design-verifier", "designer"):
            self.assertIn(s, t, s)

    def test_nothing_private_or_urls_of_figma_files(self):
        t = read("design-system-contract")
        self.assertNotRegex(t, r"figma\.com/(design|board|file)/")

    def test_page_credits_readme(self):
        self.assertIn("docs/reviews/07-figma-review.md", (ROOT / "docs/steps/07-figma.md").read_text())
        c = (ROOT / "CREDITS.md").read_text()
        for row in (r for r in c.splitlines() if "ui-ux-pro-max" in r or "Figma plugin" in r):
            self.assertNotIn("not used in v0.1", row)
        row = [r for r in c.splitlines() if r.startswith("| [ui-ux-pro-max-skill]")][0]
        self.assertIn("**Installed** (`plugin.json` dependency", row)
        self.assertIn("Figma", c)



class Lessons(unittest.TestCase):
    STEP_SKILLS = ("system-design", "backend-evaluate", "domain-model", "db-schema", "multi-tenancy",
                   "api-contract", "system-architecture", "threat-model", "design-system-contract")

    def test_agents_use_dispatch_form(self):
        for n in self.STEP_SKILLS:
            t = read(n)
            for a in ("architect", "reviewer", "researcher", "designer", "design-verifier"):
                if re.search(r"`%s` agent|dispatch.{0,40}`?%s`?" % (a, a), t):
                    self.assertIn("pavedline:" + a, t, "%s: %s" % (n, a))

    def test_long_agents_wait_in_the_foreground(self):
        for n in self.STEP_SKILLS:
            t = read(n)
            if "`architect` agent" in t or "`designer` agent" in t:
                self.assertIn("in the foreground", t, n)


if __name__ == "__main__":
    unittest.main()
