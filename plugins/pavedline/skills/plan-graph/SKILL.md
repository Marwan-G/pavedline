---
name: plan-graph
description: Step 8 of Pavedline. Plans the next wave from the records - turns the acceptance tests of docs/spec/SPEC.md (and any accepted intents) into slices with the tests each proves, surfaces, branch, dependencies and gates, in docs/plans/<date>-wave-<n>.md plus a .dot graph, checks that every test maps to a slice with plan_graph.py, and asks the founder to approve the wave. The first wave is a thin vertical slice through every layer. Use while STATE.md says STEP 8, or when a later wave must be planned.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py *)
---

# plan-graph

Step 8. A plan says what gets built next, in slices small enough to review, and proves that every acceptance test of the spec lands in exactly one slice. Outputs: `docs/plans/<date>-wave-<n>.md`, its `.dot` and `.svg`, and a decision recording the founder's approval of the wave. Create `docs/plans/` when missing. Writing the plan itself is done with `superpowers:writing-plans`. Vendor and version facts go to the `researcher` agent (subagent type `pavedline:researcher`).

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 1. Read first, in order

After the records of the shared rules: `docs/spec/SPEC.md` (the acceptance tests `AT-001` and on), `docs/architecture/DEPLOYMENT.md`, `THREATS.md`, `SYSTEM-DESIGN.md`, `docs/design/DESIGN.md`, `docs/data/DOMAIN.md`, `docs/api/openapi.yaml`, `docs/intent/` and any earlier plan in `docs/plans/`. Surfaces come from decision 0005.

**Read in full:** the surfaces decision (0005), tenancy (0002), compliance (0003), backend and auth (step 4), the data and API decisions (step 5), the deployment and threat decisions (step 6), the design decision (step 7), and every decision marked accepted since. Other decisions may be read by title, through a decisions index if the project has one.

Continue when `STATE.md` says `STEP: 8 — Plan`.

**Accepted intents first.** List `docs/intent/*.md` with `Status: accepted`. Each one must be specced before it is planned: if any is not yet `specced in decision NNNN`, run the `spec` skill's change mode for it, then continue. `plan_graph.py check` warns about accepted intents not yet specced.

## 2. Write the wave

Use `superpowers:writing-plans`, overriding its output path to `docs/plans/<date>-wave-<n>.md` (date from `date +%F`). The header names the wave goal in one sentence. Then one slice per heading, in the format of `docs/plans/README.md`:

```
### Slice <wave>.<n>: <title>
Tests: AT-001, AT-004
Surfaces: web, api
Branch: <name>
Depends on: <slice ids, or none>
```

Under each slice: scope (what a person can do when it is merged), the files and folders it touches, the `AT-` ids it proves (the same as `Tests:`), and its gates: TDD, code review, security review, verification, plus the adversarial review (3b) when the slice touches auth, tenancy, IAM, infrastructure, CI, secrets, input parsing, payments or migrations. A slice that reopens an old test says `Re-tests: AT-001` and does not list it under `Tests:`.

Rules for the shape of a wave:

- **Wave 1 is a thin vertical slice** (spec section 6.7): one core journey end to end through every layer, on web and api, deployed to the local cluster. Mobile and the website follow in later waves.
- Each later wave adds whole journeys, never a layer alone. A slice is mergeable on its own and leaves the product working.
- A slice's surfaces are among those decision 0005 selected (`api` always counts).
- Every `AT-` id appears in exactly one slice's `Tests:`. Wave 1 maps only its own journey: list the rest in the plan header as `Deferred: AT-005, AT-006 (later waves)`. `check` fails only on a test neither mapped nor deferred in any plan, and warns with the deferred count; a deferred test is never feature-complete.
- Lead-time items from `docs/production/LEAD-TIME.md` that gate a slice (store accounts, domains) are listed in the slice and in `WAITING.md`.

## 3. Check and draw

Run from the repository root:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py check
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py dot docs/plans/<date>-wave-<n>.md
```

`check` exits 1 for an unmapped test, a duplicate slice id, an unknown test or dependency, a dependency cycle, or a surface the decision did not select; fix the plan and re-run. `dot` writes the `.dot` and validates it with `dot -Tcanon`. Render the `.svg` as the `diagram` skill says and commit both.

## 4. The approval

Show the plan as a short table (slice · tests · surfaces · depends on) and the graph. Approving the wave is its own question: ask "Approve wave <n> as planned?" (options: approve, change (say what), or split a slice) and wait. Never infer approval from a "default" answer to another question. Record the approval as a decision (`decisions/NNNN-wave-<n>-approved.md`; "Stale outputs": none) only after an explicit yes. Do not start building before it.

## 5. Re-entry and the light path

A changed answer in steps 1 to 7, or a new accepted intent, is a new decision that lists the plan as stale; replan only the slices not yet merged. `plan_graph.py status` says which slices are merged (a commit on the default branch whose subject starts `Slice <id>`, or with a `Slice: <id>` trailer; a revert un-merges it) and prints `feature-complete` only when every test maps to a merged slice. A small change (a bug fix or a copy edit) skips steps 1 to 8: it is one slice-sized branch with its own gates.

## 6. Close step 8

Edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 9 — Build
LAST: <timestamp> — step 8 done: docs/plans/<date>-wave-<n>.md approved (decision NNNN)
NEXT: step 9 — build slice <wave>.1
```

Commit and close as in the shared rules, then ask "go?" to start step 9: the build runs the first slice.
