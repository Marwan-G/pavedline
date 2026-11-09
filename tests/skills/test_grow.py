import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "plugins" / "pavedline" / "skills"
TEMPLATES = ROOT / "plugins" / "pavedline" / "templates"
RULES = SKILLS / "state" / "references" / "step-rules.md"
POINTER = "Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`."


def read(name):
    d = SKILLS / name
    parts = [(d / "SKILL.md").read_text()]
    for f in sorted((d / "references").glob("*.md")) if (d / "references").is_dir() else []:
        parts.append(f.read_text())
    return "\n".join(parts)


def in_order(test, text, needles):
    pos = -1
    for n in needles:
        i = text.find(n, pos + 1)
        test.assertGreater(i, pos, f"missing or out of order: {n}")
        pos = i


class ContentOps(unittest.TestCase):
    def test_publish_loop_order(self):
        t = (SKILLS / "content-ops/SKILL.md").read_text()
        loop = t.split("## 2. The publish loop")[1].split("\n## ")[0]
        in_order(self, loop, ("1. **Brief", "2. **Draft", "3. **Human edit and fact-check",
                              "4. **SEO checklist", "5. **Pull request", "6. **Deploy",
                              "7. **Request indexing"))
        self.assertIn("the founder approves", loop.lower())

    def test_founder_approves_before_pr(self):
        t = (SKILLS / "content-ops/SKILL.md").read_text()
        self.assertLess(t.lower().index("the founder approves"), t.index("5. **Pull request"))
        for s in ("No pull request is opened before the founder's approval is recorded",
                  "quote the approval", "Never infer approval"):
            self.assertIn(s, t)

    def test_approval_is_a_verbatim_copy_and_owner_verifies(self):
        skill = (SKILLS / "content-ops/SKILL.md").read_text()
        agent = (ROOT / "plugins/pavedline/agents/growth.md").read_text()
        for name, t in (("skill", skill), ("agent", agent)):
            self.assertIn("verbatim copy of the founder's own reply in the current conversation", t, name)
            self.assertRegex(t, r"never writes `approved`", name)
        self.assertIn("owner session checks the quote", skill)
        self.assertIn("owner session checks the quote", agent)
        self.assertLess(skill.index("owner session checks the quote"), skill.index("opens the PR"))

    def test_grow_due_handoff_is_consistent(self):
        skill = (SKILLS / "content-ops/SKILL.md").read_text().split("## 3.")[1]
        agent = (ROOT / "plugins/pavedline/agents/growth.md").read_text()
        state = (SKILLS / "state/SKILL.md").read_text()
        self.assertIn("growth agent reports the GROW DUE line", skill)
        self.assertIn("owner session runs `date`, writes `STATE.md`", skill)
        self.assertIn("opens the PR", skill)
        self.assertIn("owner session", agent)
        self.assertIn("reports the `GROW DUE` line", agent)
        self.assertIn("owner session", state.split("`GROW DUE` holds")[1].split("\n")[0])

    def test_drafts_location_and_site_files(self):
        t = (SKILLS / "content-ops/SKILL.md").read_text()
        for s in ("docs/growth/briefs/", "until the founder approves", "apps/site/lib/posts.ts",
                  "apps/site/app/sitemap.ts", "owner session merges"):
            self.assertIn(s, t)
        self.assertNotIn("Only the founder runs a plugin skill", t)

    def test_robots_and_noindex_both_deliberate(self):
        t = (SKILLS / "seo-foundation/SKILL.md").read_text()
        self.assertIn("robots.txt blocks crawling on staging and the noindex header covers direct hits", t)

    def test_cadences(self):
        t = read("content-ops")
        for s in ("Weekly", "docs/growth/calendar.md", "Monthly", "docs/growth/YYYY-MM.md", "Search Console",
                  "seo-audit", "Quarterly", "refresh", "merge", "remove", "internal links"):
            self.assertIn(s, t)

    def test_grow_due_written(self):
        t = (SKILLS / "content-ops/SKILL.md").read_text()
        self.assertIn("STATE.md ▶ GROW DUE: <YYYY-MM-DD> — <what>", t)
        self.assertIn('date "+%Y-%m-%d"', t)

    def test_marketing_skills_and_deploy(self):
        t = read("content-ops")
        for s in ("seo-audit", "content-creation", "draft-content", "performance-report",
                  "marketing@knowledge-work-plugins", "deploy` skill", "GitOps",
                  "github.com/anthropics/knowledge-work-plugins/tree/main/marketing/skills"):
            self.assertIn(s, t)

    def test_founder_steps_and_ask_before_adding(self):
        t = read("content-ops")
        self.assertIn("request indexing", t.lower())
        self.assertIn("WAITING.md", t)
        self.assertIn("ask-before-adding", t)

    def test_pointer_and_size(self):
        t = (SKILLS / "content-ops/SKILL.md").read_text()
        self.assertIn("step-rules.md", t)
        self.assertLessEqual(len(t.splitlines()), 150)


class SeoFoundation(unittest.TestCase):
    def test_steps_covered(self):
        t = (SKILLS / "seo-foundation/SKILL.md").read_text()
        for s in ("Step 1", "Step 3", "Step 4", "Step 7", "Step 9", "Step 12", "SEO-STRATEGY.md",
                  "apps/site/lighthouserc.json", "ci-site.yml", "never duplicate"):
            self.assertIn(s, t)

    def test_staging_noindex(self):
        t = read("seo-foundation")
        for s in ("noindex", "X-Robots-Tag", "staging", "only production is indexable", "proxy.ts"):
            self.assertIn(s, t)

    def test_search_consoles_are_founder_steps(self):
        t = read("seo-foundation")
        for s in ("Google Search Console", "Bing Webmaster Tools", "sitemap", "founder", "WAITING.md",
                  "ask-before-adding", "never creates"):
            self.assertIn(s, t)

    def test_sources(self):
        t = (SKILLS / "seo-foundation/references/sources.md").read_text()
        for s in ("developers.google.com/search", "bing.com/webmasters", "web.dev/articles/vitals",
                  "2.5 s", "200 ms", "0.1", "2026-11-09"):
            self.assertIn(s, t)

    def test_site_actually_noindexes(self):
        site = ROOT / "plugins/pavedline/stacks/nextjs-fastapi/files/apps/site"
        self.assertIn("X-Robots-Tag", (site / "proxy.ts").read_text())


class GrowTemplates(unittest.TestCase):
    def test_growth_docs(self):
        for f in ("README.md", "calendar.md"):
            self.assertTrue((TEMPLATES / "docs/growth" / f).exists(), f)
        self.assertIn("| Date |", (TEMPLATES / "docs/growth/calendar.md").read_text())

    def test_state_template_has_grow_due(self):
        t = (TEMPLATES / "STATE.md").read_text()
        self.assertRegex(t, r"(?m)^GROW DUE: none")
        self.assertLessEqual(len(t.splitlines()), 60)

    def test_state_skill_describes_grow_due(self):
        t = (SKILLS / "state/SKILL.md").read_text()
        self.assertIn("`GROW DUE` holds", t)


if __name__ == "__main__":
    unittest.main()
