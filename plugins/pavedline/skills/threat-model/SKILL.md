---
name: threat-model
description: Step 6 of Pavedline, part 2 and the step's gate. Writes THREATS.md - threats per area (tenancy, auth, secrets, uploads, webhooks, and compliance when decision 0003 is yes), each with a mitigation and where it is enforced - then dispatches the blind reviewer on the three step-6 outputs, writes the verdict to docs/reviews/06-architecture-review.md and, on APPROVE and the founder's go, moves STATE.md to step 7. Use after system-architecture, while STATE.md says STEP 6.
---

# threat-model

Second and last skill of step 6. Output: `docs/architecture/THREATS.md` and one decision per answered question; it then runs the step's gate. Create `docs/architecture/` and `docs/reviews/` when missing. Design work goes to the `architect` agent (subagent type `pavedline:architect`) with a self-contained prompt; vendor and version facts to the `researcher` agent (subagent type `pavedline:researcher`). Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## 1. Read first, in order

`CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `docs/spec/SPEC.md`, `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md`, `TENANCY-LIFECYCLE.md`, `docs/architecture/ARCHITECTURE.dot`, `docs/architecture/DEPLOYMENT.md`, `docs/data/SCHEMA.md` (tenant roles, RLS, leak test) and `docs/api/openapi.yaml` (webhooks, uploads, scopes). Ask only what is undecided.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. Questions (one area at a time; options, recommended default, what it changes; wait)

"Default" is valid; "not needed" only with a recorded reason. None is skipped or merged; before closing compare the areas with the decisions written. Areas, in order, details in `${CLAUDE_SKILL_DIR}/references/areas.md`: assets and trust boundaries · tenancy · auth · secrets · uploads · webhooks · compliance (only when decision 0003 is yes; otherwise write "not applicable (decision 0003)") · abuse and availability · supply chain and CI. Record each answer as a decision (`decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record. A new service (a scanner, a secrets manager, a WAF): follow the ask-before-adding rule: what it is, what it will do, why nothing already in use does it, its verified cost; wait for the founder.

**One fill-in turn.** Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

## 3. Write `THREATS.md`

One section per area. Each threat is a table row with: id (`T-01`…), threat (what an attacker or a mistake does), asset, **mitigation**, **where it is enforced** (a named place that exists in the records: an RLS policy in `SCHEMA.md`, a scope in `openapi.yaml`, a CI check, a Helm NetworkPolicy in `DEPLOYMENT.md`, a stage in `TENANCY-LIFECYCLE.md`), and the check that proves it (a test, a CI job, a drill; the step that builds it). A mitigation with no enforcement place is not a mitigation: it is an open question for the founder. Areas: tenancy, auth, secrets, uploads, webhooks, compliance (when decision 0003 is yes), plus the rows `${CLAUDE_SKILL_DIR}/references/areas.md` lists. Check: every area has rows; no row lacks a mitigation or an enforcement place; every enforcement place exists in the records; no residual risk is hidden (list accepted ones with the founder's decision number).

## 4. The gate

1. Run all checks: the three outputs exist (`ARCHITECTURE.dot` with `ARCHITECTURE.svg`, `DEPLOYMENT.md`, `THREATS.md`); `dot -Tcanon -o /dev/null docs/architecture/ARCHITECTURE.dot` passes; every service in `SYSTEM-DESIGN.md` and `SERVICES.md` is in the diagram; every environment has its values file named; every threat has a mitigation and an enforcement place; every name is in `GLOSSARY.md`.
2. Dispatch the `reviewer` agent (subagent type `pavedline:reviewer`), **blind**, once, on the three outputs. Give it the file paths, `GLOSSARY.md`, `docs/spec/SPEC.md`, `decisions/`, `SYSTEM-DESIGN.md`, `SERVICES.md`, and the checklist (completeness, consistency with step 4 and step 5, glossary words, nothing contradicting a decision, every service drawn, every threat enforced, open choices marked as questions). Never give it your summary.
3. The reviewer ends `VERDICT: APPROVE` or `VERDICT: REJECT — <reason>`. Write the verdict and every finding to `docs/reviews/06-architecture-review.md`; on REJECT the file lists the findings to rework, so a fresh session resumes from it. A `REJECT` means rework and a narrow re-review, never arguing past it. Record each finding as fixed or accepted with a reason; re-run the checks of step 1 after rework.
4. Only after `VERDICT: APPROVE`, show the founder the outputs, the decisions and the verdict, and ask for the go. The `APPROVE` comes before the founder's go; the founder's go never replaces it.

## 5. Re-entry

Any of steps 1–7 can be reopened. A changed answer is a new decision superseding the old (`supersedes NNNN`); stale outputs go to `STATE.md ▶ STALE` with the number.

## 6. Close step 6

After `VERDICT: APPROVE` and the founder's go, edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 7 — Figma
LAST: <timestamp> — step 6 done: ARCHITECTURE.dot/.svg, DEPLOYMENT.md, THREATS.md; reviewer APPROVE, see docs/reviews/06-architecture-review.md
NEXT: step 7 — design system and screens in Figma
```

Commit. Print the closing block (done, changed, next, waiting on you, clear-safe). Ask: **go?**
