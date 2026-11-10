# Step 1: Market and SEO research

Starts when `STATE.md` says `STEP: 1` and you say go.

## What it is for

It gathers evidence about competitors, pricing, the market and search demand, so that the decisions of step 2 rest on
sources and not on memory. It gathers evidence; it does not decide product questions.

## Inputs

`PRODUCT.md`, `decisions/` and `STATE.md` from step 0, plus `docs/business/VISION.md` and the screenshots in `docs/business/references/` if you added them (references, never copied). You are asked once: "Which competitors, products or sites do
you already have in mind?" A list of any length is fine, including none; the researcher then proposes candidates and
you cut the list. If compliance is in scope, you are also asked which countries or regions the product serves.

## What you will be asked

The list of competitors above, the countries (if compliance is in scope), and, if you have them, exports from review
sites, which you place under `docs/business/reviews/`. Pavedline never scrapes review sites.

## How the research is done

A read-only `researcher` agent uses Playwright (or WebFetch) on public pages, and crawl4ai only if you installed it.
It respects `robots.txt` and each site's terms, uses public material only for anything behind a login, and never
handles credentials. Every claim carries a URL and is marked definite, inferred or unknown. The main session writes
the files; the researcher writes nothing.

## Output files

- `docs/business/competitors/<name>.md`, one per competitor
- `docs/business/landscape.dot` (and its `.svg`)
- `docs/business/BRIEF.md`: positioning, pricing, how the product makes money, market size (top-down and bottom-up,
  every number sourced or marked as an assumption)
- `docs/business/SEO-STRATEGY.md`: competitors' topics, queries and search intent, topic clusters, pillar pages, one
  target query per page
- `docs/business/regulatory-landscape.md`, only if compliance is in scope

## Who approves

You. The step stops and asks whether you approve `docs/business/BRIEF.md`.

## Hand-off to the next step

While it waits, `STATE.md` says `NEXT: waiting for the founder to approve docs/business/BRIEF.md`. After your go,
`STATE.md` is set to `STEP: 2 — Grill` and the grilling skill starts. Next: [step 2](02-grill.md).
