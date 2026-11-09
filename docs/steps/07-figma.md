# Step 7: Figma

Starts when `STATE.md` says `STEP: 7` and you say go. Skill: `design-system-contract`. Agents: `designer` (the only one that writes to Figma) and `design-verifier` (blind gate).

## What it is for

Designing the whole product once, in Figma, in the vocabulary of your records: the same names in design and code, every screen in every state, before any slice is built.

## Before you start

You need a Figma account logged in through the Figma plugin. If the login is missing, the step stops and adds it to `WAITING.md`. Code Connect mapping may need an Organization or Enterprise plan; if Figma refuses it, the step writes a name table instead and says so.

## What you will be asked

Only what is undecided, one area at a time with options and a recommended default: the Figma file (a new private file, asked before it is created), style direction, tokens and themes, type and spacing, components, surfaces and navigation, flows, accessibility targets and the naming rule. "Default" is a valid answer.

## Output files

The Figma file (private), `docs/design/DESIGN.md` (with node links), `docs/design/tokens.json` (light and dark), Code Connect mappings or the name table, one decision per answer, and the gate's verdict in `docs/reviews/07-figma-review.md`.

## Checks and gate

Every screen of every surface in every state, the tenant-lifecycle and "please update" screens, accessibility annotations, tokens matching the Figma variables. Then a blind `design-verifier` must return `DESIGN VERDICT: APPROVE`, written to `docs/reviews/07-figma-review.md`; a `REJECT` means rework and re-check. Only then do you approve the visual: the verifier never does.

## Who approves

The design-verifier first, then you (the visual).

## Re-entry

A changed answer is a new decision that supersedes the old one and lists the outputs it makes stale; they stay in `STATE.md ▶ STALE` until updated.

## Hand-off

`STATE.md` is set to `STEP: 8 — Plan`.

Next: step 8 plans the first wave (`plan-graph`; see [08-plan.md](08-plan.md)).
