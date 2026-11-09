---
name: domain-model
description: Step 5 of Pavedline, part 1. Turns the spec and the system design into the domain model - entities, rules, states, and the glossary words they use - asks only the undecided data questions, and writes DOMAIN.md and erd.dot. Use when STATE.md says STEP 5 and the founder says go; db-schema, multi-tenancy and api-contract follow.
---

# domain-model

Step 5 has four skills, run in this order: `domain-model` → `db-schema` → `multi-tenancy` → `api-contract`. This is the first. Output: `docs/data/DOMAIN.md`, `docs/data/erd.dot` (with its rendered `.svg`, see the `diagram` skill) and one decision per answered question. Create `docs/data/` and `docs/api/` when missing (a project started with v0.1 has neither); never fail on their absence.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 1. Read first, in order

The records of the shared rules, then `docs/spec/SPEC.md`, `docs/business/BRIEF.md` and the step-4 outputs `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md` and `TENANCY-LIFECYCLE.md`. Tenancy comes from decision 0002 (single-tenant is recorded there; then `TENANCY-LIFECYCLE.md` says `not applicable (decision 0002)`), compliance from 0003, surfaces from 0005.

Never re-ask a step-0, step-2 or step-4 answer. Continue when `STATE.md` says `STEP: 5 — Data and API`. The facts already decided (locking, time, retention, files, search, billing) become constraints on the model; cite the decision number.

## 2. Glossary first

Every entity, state and field name used in `DOMAIN.md` must exist in `GLOSSARY.md`, spelled identically to the UI, the API and the code. The skill adds the missing terms to `GLOSSARY.md` before using them (meaning, forbidden synonyms) and says which it added. A different word for an existing concept is a defect.

## 3. Questions

Before asking, **Cross-check the decisions against each other** and against the spec: a rule in one decision that a later decision contradicts (a constraint that covers only some states while another decision lets a record skip to a state outside them; a state with no transition to the one the spec needs; a spec field no screen collects; two names for one table) is raised as a question with a recommended fix in the first area it touches, never left for the architect or reviewer to find.

Ask per area as the shared rules say; the areas are in `${CLAUDE_SKILL_DIR}/references/questions.md`. A new service follows ask-before-adding.

## 4. Write the outputs

Before writing outputs, do the one fill-in turn of the shared rules.

- `docs/data/DOMAIN.md`: per entity - purpose, owner (tenant-owned or global), key attributes, relationships with cardinality, invariants (the rules the data must always satisfy, each traced to an acceptance test `AT-nnn` or a decision), state machine where the entity has states (states and legal transitions). Then a section "Cross-entity rules" and a section "Open questions" (must be empty when the step closes, or each marked with the decision that will answer it).
- `docs/data/erd.dot`: the entities and relationships, in the `diagram` skill's style, rendered to `erd.svg`; it must pass `dot -Tcanon`. Global tables and tenant-owned tables are visibly different (two colours, a legend).

Check: every spec feature touches an entity; every entity has an owner; every name is in `GLOSSARY.md`; no field stores money as a float; every state has a transition in and (unless terminal) out.

## 5. Hand on

Do not close the step here. Tell the founder the model is written and continue with `db-schema` (then `multi-tenancy` and `api-contract`, which closes the step).
