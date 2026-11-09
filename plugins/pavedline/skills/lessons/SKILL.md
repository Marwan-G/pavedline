---
name: lessons
description: Step 11 of Pavedline, at the end of every wave. Runs the retro skill from mattpocock-skills over the wave, writes docs/retros/<date>.md (what shipped, what went well, what hurt, gate findings by class, lessons), files each lesson as a rule in the one home docs/rules-index.md names, as an intent in docs/intent/ with Source - retro, or drops it with a reason, checks that STATE.md and CLAUDE.md stay small, and closes with the next wave to plan or the integration wave when plan_graph.py says feature-complete. Use while STATE.md says STEP 11.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py *)
---

# lessons

Step 11. A wave is not finished until its lessons are filed. Outputs: `docs/retros/<YYYY-MM-DD>.md`, edits to rule homes, intents in `docs/intent/`, and a trimmed `STATE.md`. Create `docs/retros/` from `templates/docs/retros/` when missing.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 1. Read first, in order

After the records of the shared rules: the wave's plan in `docs/plans/`, the merged slices' pull requests (the `Gates:` lines and the `accepted — <reason>` items), `docs/reviews/`, `STATE.md ▶ LEFT BEHIND`, the slices' `handoff/` files and `docs/rules-index.md`. Continue when `STATE.md` says `STEP: 11 — Learn`. If it names another step, say so and ask.

## 2. Run the retro

The `retro` skill of the `mattpocock-skills` plugin cannot be called by Claude (it is user-invoked only). Ask the founder to run `/mattpocock-skills:retro` for the wave and to paste or point to its output. It reads the session and proposes improvements to the environment: navigation, automated checks, coding standards, steering files, tool economy, information access. If the founder declines, or the plugin is missing (run `/pavedline:doctor`), fill the retro template yourself from the records and say in the retro that the retro skill was not used.

## 3. Write the retro

Copy `templates/docs/retros/0000-template.md` to `docs/retros/<date>.md` (date from `date +%F`; a second retro the same day gets a `-2` suffix). Fill:

- **What shipped:** slices and the `AT-` ids they proved, from the plan and the merged pull requests.
- **What went well** and **What hurt:** short, concrete, from the records, not from memory.
- **Gate findings by class:** count the findings of each class from the pull requests' gates lines and `docs/reviews/`, and say which classes repeat. A class that repeats is a candidate for a deterministic check, not only a rule.
- **Lessons:** one row each, with its outcome from section 4.

## 4. File each lesson once

Every lesson ends in exactly one outcome:

1. **A rule.** Find its home in `docs/rules-index.md` and edit that home. If the home is new, add a row to the index. Never a second copy: a rule stated in two files is a defect. Prefer a check (a script, a hook, a CI step) over prose when the violation is mechanical.
2. **An intent.** A change to the product or the process that needs the founder's decision: write `docs/intent/<YYYY-MM-DD>-<slug>.md` from `docs/intent/0000-template.md` with `Status: proposed` and `Source: retro <date>`. `spec` change mode picks it up once accepted.
3. **Dropped**, with a one-line reason in the retro.

Show the lessons as one table (lesson, outcome, where) and ask the founder to approve; "default" approves the recommended outcome for all. Apply only what is approved; record the rest as dropped.

## 5. Records bloat check

- `STATE.md` at most 60 lines: move closed items and old history to `docs/archive/<date>-<topic>.md`, keep the present state only.
- `CLAUDE.md` at most 150 lines: move detail to its home and leave a pointer.
- A rule that grew by amendments (a rule plus dated patches) is rewritten in its home as one current statement; the history stays in `decisions/`.

## 6. Close step 11

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py status`. Edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`.

If it prints `feature-complete` (every acceptance test maps to a merged slice):

```
STEP: 8 — Plan
LAST: <timestamp> — step 11 done: retro docs/retros/<date>.md (<n> rules, <m> intents, <k> dropped)
NEXT: the integration wave (ships in a later release)
```

At this point the contract is complete, so add `--feature-complete` to the `contract_check.py` step in the product's `.github/workflows/ci-api.yml` (and to `RUN.md`'s contract-check line) in this close, or write in `NEXT` that the integration wave does it. Without it CI never fails on a contract route the API still lacks.

Otherwise:

```
STEP: 8 — Plan
LAST: <timestamp> — step 11 done: retro docs/retros/<date>.md (<n> rules, <m> intents, <k> dropped)
NEXT: step 8 — plan wave <n+1>
```

Commit and close as in the shared rules, then ask: **go?** The founder reads the retro; that is the step's gate. Starting the next wave needs the founder's go.
