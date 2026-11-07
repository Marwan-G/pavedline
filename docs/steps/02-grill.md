# Step 2: Grill

Starts after you approve the brief.

## What it is for

Turning the evidence into decisions. The `grilling` skill (from `mattpocock-skills`) interviews you about the product:
who it is for, what it does and does not do, what the hard choices are. Questions already answered at step 0 are not
asked again.

## Inputs

`PRODUCT.md`, the approved `docs/business/BRIEF.md`, `docs/business/SEO-STRATEGY.md`, and everything in `decisions/`.

## What you will be asked

Product questions, one at a time, driven by the grilling skill. If the skill is not installed, run
`/pavedline:doctor` for the install command.

## Output files

New decision records in `decisions/` (the numbering continues after `0007`), and the shared vocabulary of the
product in `GLOSSARY.md`. Pavedline's records are the place the answers live, so a new session resumes from files and
not from the conversation.

## Who approves

You. The interview ends when you say the decisions are complete. It does not end on its own.

## Hand-off to the next step

`STATE.md` is set to `STEP: 3 — Spec` and the `spec` skill runs. Next: [step 3](03-spec.md). Any earlier decision can
be reopened later with a new decision record that lists the outputs it makes stale.
