---
name: competitor-teardown
description: Step 1 of Pavedline, market and SEO research. Takes the competitors and sites the founder names, dispatches the researcher agent, and writes competitors/*.md, landscape.dot and SEO-STRATEGY.md from its sourced report. Use when STATE.md says STEP 1 and the founder says go.
---

# competitor-teardown

Step 1 of Pavedline. Every claim in the output has a URL and a status: definite, inferred or unknown. Follow the steps in order.

## 1. Start from the founder's sites

Read `PRODUCT.md`, `decisions/` and `STATE.md`. Ask once: "Which competitors, products or sites do you already have in mind?" Accept a list of any length, including none. If none, the researcher finds candidates from `PRODUCT.md`; show the list of candidates and let the founder cut it before step 2 below.

If the compliance decision (`decisions/0003-*`) says compliance is in scope, also ask which countries or regions the product serves. The regulatory landscape for them is part of the research (step 3).

## 2. Dispatch the researcher

Use the `researcher` agent (read-only plus web; it writes nothing). Brief it with: the product paragraph, the competitor list, the output you need (step 3) and the scraping rules below. One competitor per dispatch is fine; independent competitors may run in parallel.

If the `competitive-brief` or `synthesize-research` skill (from `product-management`) is installed, use it to shape the comparison and the synthesis. If it is not, run `/pavedline:doctor`, then continue without it.

### Scraping rules (the researcher follows them; repeat them in the brief)

- Playwright MCP is the default; crawl4ai is an allowed alternative.
- Respect `robots.txt` and each site's terms. If either forbids a page, skip it and note that in the file.
- Review sites (marketplaces, rating sites) only through a manual export or official APIs. Never scrape them. If the founder has no export, mark review evidence unknown.
- A competitor behind a login is researched from public material only: marketing pages, public docs, public pricing. Never sign up, sign in or work around a paywall.
- No credentials, keys, tokens or cookies, ever.

## 3. Ask for these outputs

For each competitor: features, pricing, public complaints, and the sources. For the whole market: sitemaps and topics of the competitors, the queries people search with and their search intent (autocomplete, "people also ask", trends), and, if compliance is in scope, the regulatory landscape with sources.

Every claim must carry a URL and be marked definite (read directly on a primary source), inferred (reasoned from sources; say which) or unknown (not found; say where it was looked for). Reject any claim without a URL: send it back or mark it unknown. Never fill a gap from memory.

## 4. Write the files (the main session writes them, not the researcher)

All paths are in the product repository.

- `docs/business/competitors/<name>.md`, one per competitor, kebab-case name. Sections: Summary (two lines) · Features · Pricing · Public complaints · Sources. Each bullet ends with its URL and `[definite]`, `[inferred]` or `[unknown]`.
- `docs/business/landscape.dot`: one node per competitor and per product area, edges for overlap, a note for cross-cutting rails. Follow the `diagram` skill for style, validation and rendering.
- `SEO-STRATEGY.md` (repo root), with these sections:
  1. Competitors' sitemaps and topics.
  2. Queries and search intent (informational, commercial, transactional, navigational).
  3. Topic clusters.
  4. Pillar pages: one per cluster, with its supporting pages.
  5. A target query for every planned page. One page, one target query. Table: page · target query · intent · cluster.
  6. Unknowns and what would settle them.
- If compliance is in scope: `docs/business/regulatory-landscape.md`, every statement with a URL and a status.

Classic search optimisation is the foundation. Do not promise rankings. `llms.txt` is optional and is not a ranking factor.

## 5. Continue with pricing and market size

Follow the `pricing-model` skill, then the `market-size` skill. Both write sections of `BRIEF.md`. Also put in `BRIEF.md` a Positioning section: who the product is for, what it does that the competitors do not, evidence linked to `competitors/*.md`.

## 6. Close step 1

Edit `STATE.md` (see the `state` skill). Take the time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 2 — Grill
LAST: <timestamp> — step 1 done: BRIEF.md, SEO-STRATEGY.md, competitors/*.md, landscape.dot
NEXT: step 2 — grill the product decisions with the grilling skill
```

Anything only the user can do (a review-site export, a login you cannot use) goes in `WAITING.md` as `- Fn · what · where/how · what it unblocks`. Commit the files. Then ask: **the founder approves the brief?** Step 2 (grilling, from the `mattpocock-skills` dependency; if it is missing run `/pavedline:doctor`) starts only on the founder's go. Do not duplicate grilling here: step 1 gathers evidence and does not decide product questions.
