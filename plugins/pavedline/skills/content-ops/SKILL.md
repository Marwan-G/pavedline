---
name: content-ops
description: The Grow loop after launch. Runs the publish loop (brief, draft, human edit and fact-check with the founder's approval, SEO checklist, pull request, deploy through the deploy skill, request indexing), the weekly content calendar in docs/growth/calendar.md, the monthly Search Console review and seo-audit in docs/growth/YYYY-MM.md, and the quarterly refresh, merge or removal of posts. Writes STATE.md GROW DUE after each run. No pull request before the founder's approval is recorded. Use after the founder's go live, or when STATE.md GROW DUE is due.
---

# content-ops

The standing loop after step 12. Drafts are the agent's; publishing is the founder's. Outputs: `docs/growth/calendar.md`, `docs/growth/briefs/<slug>.md`, `docs/growth/YYYY-MM.md`, and `STATE.md ▶ GROW DUE`.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`. Read first: `STATE.md`, `SEO-STRATEGY.md`, `PRODUCT.md`, `GLOSSARY.md`, the `seo-foundation` skill and `docs/growth/` (create it from `templates/docs/growth/` when missing). Run it through the `growth` agent.

It uses Anthropic's marketing plugin (`marketing@knowledge-work-plugins`, optional: install it when the Grow loop starts; `/pavedline:doctor` lists it with the command): `seo-audit`, `content-creation`, `draft-content`, `performance-report` (skill names and date: `references/sources.md`). The agent calls them with its `Skill` tool; if one is missing, say so and ask the founder to run `/pavedline:doctor`. Their output is a draft, never a fact: check every claim.

## Before go-live

Drafts are allowed before go-live, but only briefs and drafts: before go-live the skill writes briefs and drafts only, marks the calendar row `draft (pre-launch)`, and never opens a publishing PR until `STATE.md` shows the product is live (the step 12 close).

## 1. Cadence

- **Weekly:** review `docs/growth/calendar.md`: move rows along, add the next pieces from `SEO-STRATEGY.md` and the last review, drop what no longer earns its place.
- **Monthly:** a Search Console review (queries, pages, clicks, impressions, indexing errors, Core Web Vitals report) plus `seo-audit` on the site, with `performance-report` for the numbers, written to `docs/growth/YYYY-MM.md`: findings, actions, next month's priorities. Search Console is the founder's account: ask them to paste the export or the figures.
- **Quarterly:** refresh, merge or remove posts (old, thin, overlapping, no traffic); re-check internal links (every page reachable, no orphans, no broken links); update redirects for anything merged or removed (301 for a merge, 410 for a removal).

## 2. The publish loop

Every piece runs these steps in this exact order; none is skipped or reordered.

1. **Brief.** `docs/growth/briefs/<slug>.md`: target query, search intent, outline, sources, the page's conversion goal, internal links to add.
2. **Draft.** `content-creation` / `draft-content` from the brief, kept in `docs/growth/briefs/` (or on a branch) until the founder approves; nothing goes into the site's content files before that, in the product's voice and glossary words. Real author, real facts; no invented quotes or numbers.
3. **Human edit and fact-check, the founder approves.** The founder edits, fact-checks and approves. Ask as its own question: "Approve `<slug>` for publication?" Never infer approval from silence, "default" or an earlier answer; only an explicit yes counts. The approval recorded in the brief is only ever a verbatim copy of the founder's own reply in the current conversation, with the date. The agent never writes `approved` or `published` (in the brief or the calendar) any other way. The owner session checks the quote against the conversation before it opens the PR.
4. **SEO checklist.** Unique title and description, one H1, canonical URL, short stable URL, Open Graph image, JSON-LD (Article, BreadcrumbList), alt text, internal links in and out, the post registered in `apps/site/lib/posts.ts` and listed by `apps/site/app/sitemap.ts`. The site's gate (`seo-foundation` §2) enforces the rest in CI.
5. **Pull request.** No pull request is opened before the founder's approval is recorded. The owner session opens it (the agent has no shell) and must quote the approval, verbatim (quote the approval, never paraphrase it), in the PR body and in the handoff file. Use a branch and worktree, the gates line and the rules of the shared flow.
6. **Deploy.** The owner session merges on the founder's say, then deploys through the `deploy` skill (GitOps, never by hand); staging stays `noindex`.
7. **Request indexing.** Founder step: in Google Search Console and Bing Webmaster Tools (accounts are the founder's; the agent never creates one; ask-before-adding). List it in `WAITING.md`; mark it done only on the founder's word. Update the calendar row to `indexing requested`.

## 3. After each run

The growth agent reports the GROW DUE line: `STATE.md ▶ GROW DUE: <YYYY-MM-DD> — <what>`, the next due date (weekly: next Monday; the monthly review and the quarterly pass when they fall earlier), computed from the caller's date. The owner session runs `date`, writes `STATE.md` (`GROW DUE` with `date "+%Y-%m-%d"`, and `LAST` with `date "+%Y-%m-%d %H:%M"`), keeps it within 60 lines, commits, and opens the PR. Then ask: **go?** for the next piece. At the start of any session a `GROW DUE` date on or before today means the loop is due: say so and offer to run it.
