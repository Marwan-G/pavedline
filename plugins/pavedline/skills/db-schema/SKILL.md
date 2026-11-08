---
name: db-schema
description: Step 5 of Pavedline, part 2. Turns DOMAIN.md into PostgreSQL tables, constraints and indexes (SCHEMA.md) and an ordered, reversible migration plan (MIGRATIONS.md) using expand/contract. Use after domain-model, while STATE.md says STEP 5.
---

# db-schema

Second skill of step 5 (`domain-model` → `db-schema` → `multi-tenancy` → `api-contract`). Output: `docs/data/SCHEMA.md` and `docs/data/MIGRATIONS.md`, plus one decision per answered question. Create `docs/data/` when missing (a project started with v0.1 has none). The schema follows the domain model, never the other way round; if a table needs something `DOMAIN.md` lacks, change `DOMAIN.md` first.

Design work goes to the `architect` agent (subagent type `pavedline:architect`) with a self-contained prompt (files to read, document to write, report format); vendor and version facts go to the `researcher` agent (subagent type `pavedline:researcher`). Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## 1. Read first, in order

`CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `docs/spec/SPEC.md`, `docs/architecture/SYSTEM-DESIGN.md` (concurrency, time, retention, search, files), `AUTH.md`, `TENANCY-LIFECYCLE.md`, then `docs/data/DOMAIN.md` and `docs/data/erd.dot`. Database in Kubernetes or managed is decision 0006; roles come from `multi-tenancy`. Ask only what is undecided. Missing `DOMAIN.md`: stop and run `domain-model`.

The tenant column is always named `tenant_id` and the setting `app.tenant_id`, even when the glossary calls the tenant something else (an organisation, a workspace, an account): the glossary records the mapping, and Pavedline's CI schema check looks for these names.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. Questions

One area at a time: what it decides, options, the recommended default, what it changes; then wait. "Default" is a valid answer; "not needed" only with a recorded reason. Areas, in order (details in `${CLAUDE_SKILL_DIR}/references/rules.md`): naming and types · constraints and integrity · indexes · concurrency columns (version column or exclusion constraint, from the concurrency and time decisions) · retention columns and deletion paths · migration tooling and the order of migrations. None is skipped or merged into another; before closing compare the areas with the decisions written and ask any area that has none. Record each answer as a decision (`decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record.

A new service or billable resource, even a free one (a migration tool as a hosted service, a schema-diff SaaS): say what it is, what it will do, why nothing already in use does it, its verified cost; wait for the founder. Facts are checked on the web (`${CLAUDE_SKILL_DIR}/references/sources.md`).

## 3. Write the outputs

**One fill-in turn.** Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

- `docs/data/SCHEMA.md`: per table - name, owner (tenant or global), columns with type and nullability, primary key, foreign keys with `ON DELETE`, unique and check constraints, indexes (every foreign key and every column used in a `WHERE` of a spec'd query), and the glossary term it implements. Tenant tables follow the `multi-tenancy` skill (the `tenant_id` column, RLS); finish that skill before closing this document, and write its policy list into the same file. Money is integer minor units or `numeric`, **never float**; large sums and aggregates are read as text in code so they never overflow `bigint` (a driver may return a 64-bit integer as a lossy number). Timestamps are `timestamptz` in UTC.
- `docs/data/MIGRATIONS.md`: the ordered list of migrations. Each has a number, what it does, the `down` that reverses it, the data it touches and whether it is expand, backfill or contract. Rules: every migration has a `down` and the pair is tested (up, down, up); schema changes to a table in use follow **expand/contract** (add nullable column or new table → deploy code that writes both → backfill in batches → deploy code that reads the new shape → drop the old in a later migration), never a one-step rename or type change; a migration that cannot be reversed (data destruction) is named as such, needs its own decision and a backup note; migrations run as the owner role, never the runtime role; tenant creation is one transaction.

Check: every table in `SCHEMA.md` appears in `DOMAIN.md` and `erd.dot` and the reverse; every foreign key is indexed; no `float` or `real` on money; every migration has a `down`.

## 4. Re-entry

Any of steps 1–7 can be reopened. A changed answer is a new decision that supersedes the old (`supersedes NNNN`); add each output it makes stale to `STATE.md ▶ STALE` with the number.

## 5. Hand on

Continue with `multi-tenancy`, then `api-contract`, which runs the gate and closes the step.
