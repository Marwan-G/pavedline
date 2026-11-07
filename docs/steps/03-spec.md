# Step 3: Spec

Starts when you confirm the grilling decisions are complete.

## What it is for

Turning the decisions into something that can be built and tested. The spec does not choose a stack; that is step 4.

## Inputs

`PRODUCT.md`, `docs/business/BRIEF.md`, `docs/business/SEO-STRATEGY.md`, every file in `decisions/`, `GLOSSARY.md`
and `STATE.md`. If step 2 looks unfinished, you are asked whether to continue.

## What you will be asked

Only what is still undecided. Platform questions (step 0) and product decisions (step 2) are not asked again. If the
spec would need a new service or billable resource, you are told what it is, what it does, why nothing already in use
does it, and its verified cost, and nothing is added until you say so.

## Output files

`docs/spec/SPEC.md`, with these sections in order: users · jobs · features per surface (website, blog, web app, mobile
app; a surface you dropped says "Not in scope") · non-goals · acceptance tests (`AT-001`, `AT-002`, …) ·
non-functional needs · site map and URL plan. Every must-have feature has an acceptance test, and every acceptance
test traces to a job.

If the spec changes the pricing, the pricing section of `docs/business/BRIEF.md` is updated in the same step. In team
mode, once you approve the spec, one GitHub issue per must-have feature is created with `to-tickets`; in solo mode
none is.

## Who approves

You approve the spec.

## Hand-off to the next step

`STATE.md` is set to `STEP: 4 — System design`. Step 4 ships in a later Pavedline release (v0.2), so the guided flow
stops here for now: the spec, the brief and the decisions are the output of v0.1. They are plain files in your
repository; nothing about them depends on Pavedline.
