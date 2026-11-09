---
name: system-architecture
description: Step 6 of Pavedline, part 1. Draws the whole system as ARCHITECTURE.dot and ARCHITECTURE.svg (every service decided in step 4 appears) and writes DEPLOYMENT.md - the chosen stack pack, the Helm and environment layout (local, staging, production), namespaces and which apps run where. It then copies the stack pack and the infra templates for the chosen surfaces with apply_stack.py. Use after step 5, while STATE.md says STEP 6.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/apply_stack.py) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/apply_stack.py *)
---

# system-architecture

First skill of step 6 (`system-architecture` → `threat-model`). Output: `docs/architecture/ARCHITECTURE.dot` and its rendered `ARCHITECTURE.svg`, `docs/architecture/DEPLOYMENT.md`, the stack pack copied into the repository (section 4), and one decision per answered area. Create `docs/architecture/` when missing. The `threat-model` skill then writes `THREATS.md` and runs the step's gate.

**This step copies the stack pack.** After the documents, `apply_stack.py` (section 4) copies the chosen pack (`nextjs-fastapi`, the only v1 pack: Dockerfiles, Helm charts, CI jobs, configs and the starter apps) for the surfaces of decision 0005 only, plus the infra and CI templates a product started with an older Pavedline may lack. Say so plainly to the founder before running it.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 1. Read first, in order

After the records of the shared rules: `SERVICES.md`, `docs/spec/SPEC.md`, then `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md`, `TENANCY-LIFECYCLE.md`, `docs/production/LEAD-TIME.md`, `docs/data/SCHEMA.md` and `docs/api/openapi.yaml`. Take surfaces from decision 0005 (a dropped surface has no app and no node in the diagram), tenancy from 0002, the database from 0006. Never re-ask a step-4 or step-5 question. Continue when `STATE.md` says `STEP: 6 — Architecture`.

## 2. Questions (one area at a time; options, recommended default, what it changes; wait)

Areas, in order, details in `${CLAUDE_SKILL_DIR}/references/questions.md`: stack pack · apps and services (which run, which are separate deployments) · environments and namespaces · ingress and edge (Gateway API) · database placement · secrets path · observability seam · release and rollback (from the migration rules of step 5).

A new service (a registry, a managed database, a CDN, an observability vendor) follows ask-before-adding.

Before writing outputs, do the one fill-in turn of the shared rules.

## 3. Write the outputs

- `ARCHITECTURE.dot`: **the file is `docs/architecture/ARCHITECTURE.dot` with `docs/architecture/ARCHITECTURE.svg` beside it, exactly that path**; a repository-root `ARCHITECTURE.dot` from step 0 is a different, shorter overview and is not this output (step 6 updates the root overview to agree with the system diagram, but never write the system diagram there instead). Follow the `diagram` skill (style, one colour per area, notes for cross-cutting rails, at most about 25 nodes, a comment saying what it is the source of). Clients, edge, apps, API, data, queues and background workers, and every third-party service. **Check: every service named in `SYSTEM-DESIGN.md` and `SERVICES.md` appears in the diagram**, each with its decision number or an `SERVICES.md` row; a service in the diagram that no record names is a defect. Validate and render exactly as the `diagram` skill says (`dot -Tcanon -o /dev/null docs/architecture/ARCHITECTURE.dot`, then `dot -Tsvg docs/architecture/ARCHITECTURE.dot -o docs/architecture/ARCHITECTURE.svg`); if `dot` is missing, say so and ask for Graphviz, never hand-write the SVG.
- `DEPLOYMENT.md`: the pack (`nextjs-fastapi`) and which of its parts this product uses; the three environments **local · staging · production**, each with its values file (`values-local.yaml`, `values-staging.yaml`, `values-production.yaml`), namespaces, which apps run in each, replica and resource intent with numbers carried from `SYSTEM-DESIGN.md`, the database placement, the ingress path through the Gateway API, secrets from the secret store into a Kubernetes Secret, the migration job that runs before a release, and how rollback works when a migration has already run; when mobile is a surface (decision 0005), a release rule: the API keeps serving every app version at or above the minimum supported app version. Facts are decisions; unknown numbers are labelled assumptions with the way to measure them. End with the sentence: "The stack templates for these surfaces are copied into this repository by `apply_stack.py` at the end of step 6; step 9 builds from them and from this document."

Check: the diagram renders; every service is in it; every environment has its values file named; every number has a unit; every new service is in `SERVICES.md`; every name is in `GLOSSARY.md`.

## 4. Copy the stack pack

After the checks above pass. Inputs, none re-asked: surfaces from decision 0005, tenancy from 0002 (`single` when it says one tenant per deployment, otherwise `multi`), the product slug (a DNS label, lowercase letters, digits and `-`; the name `STATE.md` carries, asked once if unclear), and `OWNER/REPO` of the GitHub repository when `LINKS.md` or a decision names it.

0. **Database major.** Read the product's database decision (`decisions/0006-*`) and `docs/architecture/SYSTEM-DESIGN.md` for the PostgreSQL major, and pass it as `--postgres-major <N>` (the pack pins the majors listed in `pack.yaml` under `postgres:`; without the flag its default major is used). When the two records name different majors, or the major is not pinned (`postgres major N not pinned in this pack`, exit 1), stop: it is a mismatch, so ask the founder which record is right and fix the record; never pass a different major to make the script succeed.
1. Dry run, then show the founder the list (`would create`, `kept`) and ask "go?":
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/apply_stack.py --target . --pack nextjs-fastapi --surfaces <comma list, e.g. api,web> --tenancy <multi|single> --name <slug> [--github-repo OWNER/REPO] --postgres-major <N> --dry-run`
2. Run the same command without `--dry-run`. It never overwrites: any `conflict: <path>` line means nothing was written (exit 1); show the lines and ask, never delete or overwrite a founder file. Exit 2 means a bad argument.
3. A dropped surface gets no app, chart, CI job or Argo CD app. A single-tenant product gets no RLS check or leak fixture, and `RUN.md` says `not applicable (decision 0002)` for both. The pack's source list lands in `docs/architecture/STACK-SOURCES.md`; its run commands are appended to `RUN.md` under `## Stack: nextjs-fastapi`.
4. Add to `WAITING.md` (founder steps, one item each, with where to click): the **ruleset bypass for GitHub Actions on `main`** (the image workflow commits the new image digest to `values-staging.yaml`; without the bypass a protected `main` rejects it); **`RENOVATE_TOKEN`** (ask-before-adding: a personal access token or the founder's own GitHub App; `GITHUB_TOKEN` is not used); and **every `to fill:` line** the script printed (hostnames, owner, mobile identifiers).
5. Commit the copy (short subject), then continue.

## 5. Hand on

Continue with `threat-model`, which writes `THREATS.md`, runs the gate and closes the step.
