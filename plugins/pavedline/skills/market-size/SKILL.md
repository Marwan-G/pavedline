---
name: market-size
description: Writes the market-size section of BRIEF.md in step 1 of Pavedline, with a top-down and a bottom-up estimate. Every number is sourced with a URL or marked as an assumption. Use after competitor-teardown.
---

# market-size

Writes the `## Market size` section of `BRIEF.md`. Honest, small and checkable beats impressive.

## Steps

1. Read `PRODUCT.md`, the pricing section of `BRIEF.md` and `docs/business/competitors/*.md`.
2. Define the market in one sentence: who the customers are, in which regions, for what job. Everything below is measured against that sentence.
3. **Top-down:** start from a published figure for the wider market (a report, a statistic office, a regulator). Narrow it step by step to the defined market. Each narrowing step shows its factor and why.
4. **Bottom-up:** count the customers you could reach (a sourced count of businesses or people), multiply by the share you could plausibly win in the first years, multiply by the price from the pricing section. Show the arithmetic.
5. Mark every number as `sourced` (with its URL, fetched now, never from memory) or `assumption` (say what it assumes and how it could be tested). A number with neither is not allowed.
6. Compare the two estimates. If they differ by more than a factor of three, say why and which one you trust more.
7. For research that needs the web, dispatch the `researcher` agent; it follows the rules in the `competitor-teardown` skill. If the `synthesize-research` skill is installed, use it; if not, run `/pavedline:doctor` and continue.
8. Write the section with: Definition · Top-down (table) · Bottom-up (table) · Comparison · Assumptions to test. Replace an existing section; never duplicate it.
