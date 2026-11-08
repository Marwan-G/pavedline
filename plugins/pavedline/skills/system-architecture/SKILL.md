---
name: system-architecture
description: Step 6 of Pavedline, part 1. Draws the whole system as ARCHITECTURE.dot and ARCHITECTURE.svg (every service decided in step 4 appears) and writes DEPLOYMENT.md - the chosen stack pack, the Helm and environment layout (local, staging, production), namespaces and which apps run where. It copies no stack templates. Use after step 5, while STATE.md says STEP 6.
---

# system-architecture

First skill of step 6 (`system-architecture` → `threat-model`). Output: `docs/architecture/ARCHITECTURE.dot` and its rendered `ARCHITECTURE.svg`, `docs/architecture/DEPLOYMENT.md`, and one decision per answered area. Create `docs/architecture/` when missing. The `threat-model` skill then writes `THREATS.md` and runs the step's gate.

**Ruling 2: this step copies no stack templates.** It records the chosen pack (`nextjs-fastapi`, the only v1 pack) and writes the Helm and environment layout as a document. Say plainly to the founder: the pack's templates (Dockerfiles, Helm values, CI jobs, configs) are copied in a later release; until then step 9 builds from this document.

Design work goes to the `architect` agent (subagent type `pavedline:architect`) with a self-contained prompt (files to read, document to write, report format); vendor and version facts to the `researcher` agent (subagent type `pavedline:researcher`). Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## 1. Read first, in order

`CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `SERVICES.md`, `docs/spec/SPEC.md`, then `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md`, `TENANCY-LIFECYCLE.md`, `docs/production/LEAD-TIME.md`, `docs/data/SCHEMA.md` and `docs/api/openapi.yaml`. If `STATE.md` says `STEP: 6 — Architecture`, continue; if it says an earlier step, say so and ask. Take surfaces from decision 0005 (a dropped surface has no app and no node in the diagram), tenancy from 0002, the database from 0006. Ask only what is undecided; never re-ask a step-4 or step-5 question.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. Questions (one area at a time; options, recommended default, what it changes; wait)

"Default" is valid; "not needed" only with a recorded reason. None is skipped or merged; before closing compare the areas with the decisions written. Areas, in order, details in `${CLAUDE_SKILL_DIR}/references/questions.md`: stack pack · apps and services (which run, which are separate deployments) · environments and namespaces · ingress and edge (Gateway API) · database placement · secrets path · observability seam · release and rollback (from the migration rules of step 5). Record each answer as a decision (`decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record.

Any new service or billable resource (a registry, a managed database, a CDN, an observability vendor), even a free one, follows the ask-before-adding rule: what it is, what it will do, why nothing already in use does it, its verified cost; wait for the founder. Costs are checked on the web at expected usage, never designed to a free tier. Add each approved service to `SERVICES.md`.

**One fill-in turn.** Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

## 3. Write the outputs

- `ARCHITECTURE.dot`: **the file is `docs/architecture/ARCHITECTURE.dot` with `docs/architecture/ARCHITECTURE.svg` beside it, exactly that path**; a repository-root `ARCHITECTURE.dot` from step 0 is a different, shorter overview and is not this output (step 6 updates the root overview to agree with the system diagram, but never write the system diagram there instead). Follow the `diagram` skill (style, one colour per area, notes for cross-cutting rails, at most about 25 nodes, a comment saying what it is the source of). Clients, edge, apps, API, data, queues and background workers, and every third-party service. **Check: every service named in `SYSTEM-DESIGN.md` and `SERVICES.md` appears in the diagram**, each with its decision number or an `SERVICES.md` row; a service in the diagram that no record names is a defect. Validate and render exactly as the `diagram` skill says (`dot -Tcanon -o /dev/null docs/architecture/ARCHITECTURE.dot`, then `dot -Tsvg docs/architecture/ARCHITECTURE.dot -o docs/architecture/ARCHITECTURE.svg`); if `dot` is missing, say so and ask for Graphviz, never hand-write the SVG.
- `DEPLOYMENT.md`: the pack (`nextjs-fastapi`) and which of its parts this product uses; the three environments **local · staging · production**, each with its values file (`values-local.yaml`, `values-staging.yaml`, `values-production.yaml`), namespaces, which apps run in each, replica and resource intent with numbers carried from `SYSTEM-DESIGN.md`, the database placement, the ingress path through the Gateway API, secrets from the secret store into a Kubernetes Secret, the migration job that runs before a release, and how rollback works when a migration has already run; when mobile is a surface (decision 0005), a release rule: the API keeps serving every app version at or above the minimum supported app version. Facts are decisions; unknown numbers are labelled assumptions with the way to measure them. End with the sentence: "The stack templates are copied in a later release; until then step 9 builds from this document."

Check: the diagram renders; every service is in it; every environment has its values file named; every number has a unit; every new service is in `SERVICES.md`; every name is in `GLOSSARY.md`.

## 4. Re-entry

Any of steps 1–7 can be reopened. A changed answer is a new decision superseding the old (`supersedes NNNN`); stale outputs go to `STATE.md ▶ STALE` with the number.

## 5. Hand on

Continue with `threat-model`, which writes `THREATS.md`, runs the gate and closes the step.
