---
name: domain-model
description: Step 5 of Pavedline, part 1. Turns the spec and the system design into the domain model - entities, rules, states, and the glossary words they use - asks only the undecided data questions, and writes DOMAIN.md and erd.dot. Use when STATE.md says STEP 5 and the founder says go; db-schema, multi-tenancy and api-contract follow.
---

# domain-model

Step 5 has four skills, run in this order: `domain-model` → `db-schema` → `multi-tenancy` → `api-contract`. This is the first. Output: `docs/data/DOMAIN.md`, `docs/data/erd.dot` (with its rendered `.svg`, see the `diagram` skill) and one decision per answered question. Create `docs/data/` and `docs/api/` when missing (a project started with v0.1 has neither); never fail on their absence.

Design work goes to the `architect` agent (subagent type `pavedline:architect`), with a self-contained prompt: the files to read, the document to write, the report format. Vendor and version facts go to the `researcher` agent (subagent type `pavedline:researcher`). Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## 1. Read first, in order

Records in the order of the `state` skill: `CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `docs/spec/SPEC.md`, `docs/business/BRIEF.md`, then the step-4 outputs `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md` and `TENANCY-LIFECYCLE.md`. Tenancy comes from decision 0002 (single-tenant is recorded there; then `TENANCY-LIFECYCLE.md` says `not applicable (decision 0002)`), compliance from 0003, surfaces from 0005. If `STATE.md` says `STEP: 5 — Data and API`, continue; if it says an earlier step, say so and ask.

Ask only what is undecided (the question-once rule of the plan); never re-ask a step-0, step-2 or step-4 answer. The facts already decided (locking, time, retention, files, search, billing) become constraints on the model; cite the decision number.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. Glossary first

Every entity, state and field name used in `DOMAIN.md` must exist in `GLOSSARY.md`, spelled identically to the UI, the API and the code. The skill adds the missing terms to `GLOSSARY.md` before using them (meaning, forbidden synonyms) and says which it added. A different word for an existing concept is a defect.

## 3. Questions

The tenant column is always named `tenant_id` and the setting `app.tenant_id`, even when the glossary calls the tenant something else (an organisation, a workspace, an account): the glossary records the mapping, and Pavedline's CI schema check looks for these names.

Before asking, **Cross-check the decisions against each other** and against the spec: a rule in one decision that a later decision contradicts (a constraint that covers only some states while another decision lets a record skip to a state outside them; a state with no transition to the one the spec needs; a spec field no screen collects; two names for one table) is raised as a question with a recommended fix in the first area it touches, never left for the architect or reviewer to find.

Per area: say what it decides, give the options, state the recommended default and what it changes, then wait. "Default" is a valid answer; "not needed" only with a recorded reason. No area is skipped silently or merged into another; before closing, compare the areas of `${CLAUDE_SKILL_DIR}/references/questions.md` with the decisions written and ask any area without one. Record each answer as a decision (format of `decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record.

Any new service or billable resource, even a free one: say what it is, what it will do, why nothing already in use does it and its verified cost, and wait for the founder to approve. Add approved ones to `SERVICES.md`.

## 4. Write the outputs

**One fill-in turn.** Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

- `docs/data/DOMAIN.md`: per entity - purpose, owner (tenant-owned or global), key attributes, relationships with cardinality, invariants (the rules the data must always satisfy, each traced to an acceptance test `AT-nnn` or a decision), state machine where the entity has states (states and legal transitions). Then a section "Cross-entity rules" and a section "Open questions" (must be empty when the step closes, or each marked with the decision that will answer it).
- `docs/data/erd.dot`: the entities and relationships, in the `diagram` skill's style, rendered to `erd.svg`; it must pass `dot -Tcanon`. Global tables and tenant-owned tables are visibly different (two colours, a legend).

Check: every spec feature touches an entity; every entity has an owner; every name is in `GLOSSARY.md`; no field stores money as a float; every state has a transition in and (unless terminal) out.

## 5. Re-entry

Any of steps 1–7 can be reopened. If an answer changes later, record a new decision that supersedes the old one (`Status: superseded by NNNN`; the new one says `supersedes NNNN`) and add each output it makes stale to `STATE.md ▶ STALE` with the decision number.

## 6. Hand on

Do not close the step here. Tell the founder the model is written and continue with `db-schema` (then `multi-tenancy` and `api-contract`, which closes the step).
