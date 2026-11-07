---
name: pricing-model
description: Writes the pricing section of docs/business/BRIEF.md in step 1 of Pavedline. Covers tiers, what each tier includes, how the product makes money, pricing references from competitors and open questions. Use after competitor-teardown, or when pricing changes.
---

# pricing-model

Writes the pricing section of `docs/business/BRIEF.md`. It proposes; the founder decides. It does not build a per-tenant cost model: that belongs to system design (step 4), when the stack is known.

## Steps

1. Read `PRODUCT.md`, `decisions/` and every `docs/business/competitors/*.md`. If there are no competitor files yet, run the `competitor-teardown` skill first.
2. Collect the pricing references: each competitor's tiers and prices, the unit they charge by (seat, usage, flat), and the URL and status (definite, inferred or unknown) from its file. Put them in a table. A price with no URL is marked unknown.
3. Propose how the product makes money, in one paragraph: who pays, for what, how often. Name the charging unit and say why it fits the product.
4. Propose tiers. For each tier: name, price (or "free"), the unit and limits, what it includes, and who it is for. Mark every number as sourced (link to a reference) or an assumption.
5. List open questions the founder must answer (free tier or not, annual discount, currencies, taxes, trial). Do not answer them.
6. Write the result as the `## Pricing` section of `docs/business/BRIEF.md`, with the subsections References, How the product makes money, Tiers, Open questions. Replace the section if it exists; never duplicate it.
7. If a running tool such as a billing provider would be needed, do not add it. State what it is, what it would do, why nothing already in use does it and its verified cost, and wait for the founder. Add the approval to `WAITING.md`.

Re-entry: if pricing changes at step 3 or later, update this section, then record a decision listing the outputs it makes stale (see the `state` skill).
