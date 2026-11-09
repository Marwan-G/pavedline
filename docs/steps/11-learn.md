# Step 11: Learn (end of every wave)

Starts when `STATE.md` says `STEP: 11` and you say go. Skill: `lessons`.

## What it is for

Turning what happened in the wave into fewer repeated mistakes. The `retro` skill from `mattpocock-skills` looks for improvements to the working environment; `lessons` writes the result to `docs/retros/<date>.md` and files each lesson in the one right place.

## What you will be asked

To read the retro and decide on each proposed rule or intent. Nothing is added to the rules or the intents without your say.

## Output files

`docs/retros/<YYYY-MM-DD>.md`; edits to the home of each accepted rule (never a second copy); intents in `docs/intent/` with `Source: retro <date>`; overflow from `STATE.md` moved to `docs/archive/`.

## Checks and gate

`STATE.md` stays within 60 lines and `CLAUDE.md` within 150. Every lesson has exactly one outcome: a rule, an intent, or dropped with a reason. `plan_graph.py status` says whether the plan is feature-complete.

## Who approves

You read the retro and approve its outcomes.

## Re-entry

A later retro may correct an earlier lesson; old retros are history and are not edited.

## Hand-off

`STATE.md` is set from `plan_graph.py status`'s `integration wave:` line: `STEP: 8 — Plan` for the next feature wave (`not due`) or for the [integration wave](integration-wave.md) (`due`), `STEP: 9 — Build` while its slices are open (`planned`), and `STEP: 12 — Go to production` once it is `done`.

Next: [step 8](08-plan.md) plans the next wave.
