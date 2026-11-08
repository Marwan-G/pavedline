---
name: system-design
description: Step 4 of Pavedline. Asks the mandatory system-design questions in three short rounds (platform, behaviour, reach), records one decision per answer, and writes SYSTEM-DESIGN.md with numbers, AUTH.md, TENANCY-LIFECYCLE.md and the lead-time register. Use when STATE.md says STEP 4 and the founder says go.
---

# system-design

Step 4. Output: `docs/architecture/SYSTEM-DESIGN.md` (with numbers), `docs/architecture/AUTH.md`, `docs/architecture/TENANCY-LIFECYCLE.md`, `docs/production/LEAD-TIME.md`, items in `WAITING.md`, and one decision per answered area. Create `docs/architecture/` and `docs/production/` when missing (a project started with v0.1 has neither); never fail on their absence.

Design work (the documents) goes to the `architect` agent (subagent type `pavedline:architect`); vendor and version facts go to the `researcher` agent (subagent type `pavedline:researcher`). Give each a self-contained prompt: the files to read, the question, the report format. Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## 1. Read first, in order

`CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `docs/spec/SPEC.md`, `docs/business/BRIEF.md`. Take tenancy from decision 0002, compliance from decision 0003 and surfaces from decision 0005. Ask only what is undecided; never re-ask a step-0 or step-2 question. If `STATE.md` says `STEP: 4 — System design`, continue; if it says an earlier step, say so and ask.

Surfaces: per decision 0005, questions for a dropped surface are skipped (no mobile: no Mobile offline, no push, no store lead times; no website or blog: no Website, blog and SEO; no web app: no real-time screens). Record "skipped: surface dropped (decision 0005)" in `SYSTEM-DESIGN.md`.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. How to ask

Rounds, not one long session. In each round, take the areas of `${CLAUDE_SKILL_DIR}/references/questions.md` in order, **one area at a time**: say what the question is, give the options, state the recommended default and what it changes, then wait. "Default" is a valid answer. **"Not needed" is valid only with a recorded reason.** No area may be skipped silently, merged into another area: ask every area of the round in the order of the list, and before closing a round compare the areas of `${CLAUDE_SKILL_DIR}/references/questions.md` with the decisions written, then ask any area that has none. Record each answer as a decision (format of `decisions/0000-template.md`, numbered after the highest existing), with a "Stale outputs" section. Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record.

Any new service or billable resource, even a free one, follows the ask-before-adding rule: say what it is, what it will do, why nothing already in use does it and its verified cost, and wait for the founder to approve. Costs are checked on the web (see `${CLAUDE_SKILL_DIR}/references/sources.md`), at expected user counts, and are never designed to a free tier. Add each approved service to `SERVICES.md`.

### Round 1: platform

Backend (run the `backend-evaluate` skill; the founder decides) · Auth (`${CLAUDE_SKILL_DIR}/references/auth-contract.md`) · tenancy lifecycle (`${CLAUDE_SKILL_DIR}/references/tenancy-lifecycle.md`) · Security and compliance. **Next.js is frontend only:** no business logic, only a pass-through auth-cookie proxy, checked by a CI boundary check.

### Round 2: behaviour

Concurrency · Time and scheduling · Scheduled jobs · Performance · Images and files · Real-time · Notifications · Payments taken by tenants · Billing.

### Round 3: reach

Accessibility (**WCAG 2.2 AA** default) · Mobile offline · Multi-region · Service mesh · Website, blog and SEO · Search · Availability and recovery.

## 3. Write the outputs

**One fill-in turn.** Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

- `SYSTEM-DESIGN.md`: one section per area, each with the decision number, the answer and **numbers** (users, requests per second, p95, RPO, RTO, sizes). No "TBD": an unknown number is written as a labelled assumption with the way to measure it.
- `AUTH.md`: the auth contract and the chosen provider's implementation.
- `TENANCY-LIFECYCLE.md`: the eight stages. Single-tenant (decision 0002): write "not applicable (decision 0002)" and nothing else.
- `LEAD-TIME.md` and `WAITING.md`: every item that takes days or weeks outside our control (payment provider verification, SMS sender registration, Apple and Google developer accounts and store review, processor agreements, domain verification), each with what, who, how long and what it blocks, written to both files now so it is finished by step 12.

Check: every area has a decision or a recorded reason; every number has a unit; every new service is in `SERVICES.md`.

## 4. Re-entry

Any of steps 1–7 can be reopened. If a step-4 answer changes later, record a new decision that supersedes the old one (`Status: superseded by NNNN` on the old file; the new one says `supersedes NNNN`), list the downstream outputs it makes stale in its "Stale outputs" section (for example `docs/data/SCHEMA.md`, affected Figma screens, `ARCHITECTURE.dot`) and add each to `STATE.md ▶ STALE` with the decision number. They stay there until updated.

## 5. Close step 4

Records-consistency pass first: dispatch the `reviewer` agent (subagent type `pavedline:reviewer`), blind, once, on the decisions and the step-4 outputs (`SYSTEM-DESIGN.md`, `AUTH.md`, `TENANCY-LIFECYCLE.md`, `LEAD-TIME.md`) for contradictions. `VERDICT: REJECT` means rework and a narrow re-review; only `VERDICT: APPROVE` lets `STATE.md` move on. Write the verdict and every finding to `docs/reviews/04-system-design-review.md` (create `docs/reviews/` when missing); on REJECT the file lists the findings to rework, so a fresh session resumes from it.

Edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 5 — Data and API
LAST: <timestamp> — step 4 done: SYSTEM-DESIGN.md, AUTH.md, TENANCY-LIFECYCLE.md, LEAD-TIME.md written; verdict in docs/reviews/04-system-design-review.md
NEXT: step 5 — domain model, schema, API contract
```

Commit. Print the closing block (done, changed, next, waiting on you, clear-safe). Ask: **go?** The founder approves each decision; do not move on without that.
