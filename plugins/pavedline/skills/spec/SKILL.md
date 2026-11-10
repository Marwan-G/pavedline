---
name: spec
description: Step 3 of Pavedline. Writes docs/spec/SPEC.md (users, jobs, features per surface, non-goals, acceptance tests, non-functional needs, site map and URL plan) from the brief and the grilling decisions. Use when STATE.md says STEP 3 and the founder says go.
---

# spec

Step 3. The spec turns the decisions into something that can be built and tested. It does not ask the questions step 2 already settled, and it does not choose a stack (step 4).

## 1. Read first, in order

`PRODUCT.md`, `docs/business/VISION.md` if it exists, `docs/business/BRIEF.md`, `docs/business/SEO-STRATEGY.md`, every file in `decisions/`, `GLOSSARY.md`, `STATE.md`. Use the words of `GLOSSARY.md` exactly. If `STATE.md` says `STEP: 2 — Grill` and the founder confirms the decisions are complete, set `STEP: 3 — Spec` (fresh `date` timestamp in `LAST`) and continue. If step 2 is not finished (the `grilling` skill from `mattpocock-skills` has open questions, or `decisions/` has nothing beyond 0001–0007), say so and ask whether to continue; if the skill is missing, run `/pavedline:doctor`.

Ask who may be a data subject (age limit) and the default retention period for personal data, unless a decision already says.

Ask only what is undecided. Never re-ask a platform question (step 0) or a product decision (step 2).

## 2. Write `docs/spec/SPEC.md`

Use exactly these sections, in this order:

1. **Users**: who they are, one short paragraph each.
2. **Jobs**: what each user is trying to get done, as "When ..., I want ..., so I can ...".
3. **Features per surface**: one subsection for each surface the surfaces decision (`decisions/0005-*`) selected, from this fixed list: **Website**, **Blog**, **Web app**, **Mobile app**. A surface that was not selected gets a single line: "Not in scope (decision 0005)". Each feature: a name, one sentence, the job it serves, and priority (must, should, could).
4. **Non-goals**: what the product will not do, each with a reason.
5. **Acceptance tests**: one per must-have feature, in the form "Given ..., when ..., then ...". Number them `AT-001`, `AT-002`, and so on. Each says which surface it belongs to. Later steps map every one of them to a slice, so write them so a test can check them.
6. **Non-functional needs**: performance, availability, accessibility, privacy and, if compliance is in scope, the obligations from the compliance decision. Every need is measurable ("p95 under 300 ms"), or marked as an open question. Do not invent numbers: mark a guess as an assumption. The system-design numbers come at step 4.
7. **Site map and URL plan**: for the website and blog, a table of page · short stable URL · target query (from `docs/business/SEO-STRATEGY.md`) · search intent · conversion goal. The blog lives under `/blog` unless a decision says otherwise. For the web app and mobile app, a list of screens or routes. One page, one target query.

## 3. Check the spec

- Every must-have feature has at least one acceptance test.
- Every acceptance test traces to a job.
- No term is used that `GLOSSARY.md` does not define or that is not plain language.
- No service or billable resource is added silently. If the spec needs one, state what it is, what it would do, why nothing already in use does it and its verified cost, and wait for the founder's go.

## 4. Update the brief if needed

If the spec changes the pricing (a feature moves to another tier, a tier is added), edit the pricing section of `docs/business/BRIEF.md` (see the `pricing-model` skill) and say so in the summary. Do not leave them in disagreement.

## 5. Team mode

Read `STATE.md` for `MODE`. If it is `team`, use the `to-tickets` skill (from `mattpocock-skills`) to turn the must-have features into GitHub issues, one per feature, each linking its acceptance tests. If the skill is missing, run `/pavedline:doctor` and list the issues in the summary instead. Create issues only after the founder approves the spec. In solo mode, create none.

## 6. Close step 3

Edit `STATE.md` (see the `state` skill). Take the time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 4 — System design
LAST: <timestamp> — step 3 done: docs/spec/SPEC.md written
NEXT: step 4 — ask the system-design questions
```

Commit. Step 4 is the `system-design` skill: the next session runs it (or say "continue: step 4"). Ask: **go?** The founder approves the spec first; do not move on without that.

## Change mode

When the founder accepts an intent (`docs/intent/<file>` says `Status: accepted`), do not redo steps 1 to 3. Read the intent, then:

1. Update only the affected sections of `docs/spec/SPEC.md`.
2. Write a decision (next number, with `supersedes NNNN` where it changes an earlier one; the outputs it makes stale go to its "Stale outputs" section and to `STATE.md ▶ STALE`). It records `Intent: docs/intent/<file>`.
3. Add new `AT-NNN` acceptance tests numbered after the highest existing one; it never renumbers an existing test.
4. Set the intent's line to `Status: accepted → specced in decision NNNN`.

Then the `plan-graph` skill picks the new tests up: they stay unmapped until a slice proves them.
