# Step 8: Plan

Starts when `STATE.md` says `STEP: 8` and you say go. Skill: `plan-graph`. Script: `plan_graph.py`.

## What it is for

Turning the acceptance tests of the spec into waves of small slices, so that every test is built and checked once. The first wave is a thin vertical slice: one core journey end to end, through every layer, on the web app and the API, running on your machine.

## What you will be asked

One question: "Approve wave <n> as planned?" It is asked on its own, and only an explicit yes counts. Anything accepted in `docs/intent/` is specced first (the `spec` skill's change mode), then planned.

## Output files

`docs/plans/<date>-wave-<n>.md` (slices with their tests, surfaces, branch, dependencies and gates), its `.dot` and `.svg`, and one decision recording your approval.

## Checks and gate

`plan_graph.py check` exits 0: every acceptance test maps to a slice, no duplicate or unknown slice, no dependency cycle, every surface selected in decision 0005. Later, `plan_graph.py status` prints `feature-complete` only when every test maps to a merged slice.

## Who approves

You approve the wave.

## Re-entry

A new accepted intent or a changed decision makes the plan stale; only slices not yet merged are replanned. A small change (a bug fix or a copy edit) skips steps 1 to 8.

## Hand-off

`STATE.md` is set to `STEP: 9 — Build`.

Next: [step 9](09-build.md) builds the first slice.
