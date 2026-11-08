# Pavedline v0.2 (PR 1: steps 4–7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** steps 4–7 of the Pavedline flow (system design, data and API, architecture, Figma) work end to end, are
proven on the private trial project, and land on `next` as one reviewed PR.

**Architecture:** new skills (Markdown, detail in `references/`) and agents under `plugins/pavedline/`, new
product-repo template folders, contract tests in `tests/skills/`, one page per step in `docs/steps/`. Each step is
written, checked statically, then run on the trial in a fresh headless Claude Code session with the plugin loaded
from the working tree; what the run shows is fixed in the plugin, never in the trial's outputs.

**Tech stack:** Markdown skills · Python 3.10+ stdlib (tests, scripts) · Graphviz · Claude Code 2.1.319
(`claude -p --plugin-dir … --resume`) · the Figma plugin (`figma@claude-plugins-official`, 2.2.157 installed) ·
`@redocly/cli` for OpenAPI linting (version pinned in Task 6 after checking npm).

**Spec:** `docs/superpowers/specs/2026-11-08-v0.2-v0.4-build-design.md` (how this is built) and
`docs/superpowers/specs/2026-11-07-pavedline-design.md` (what is built: read §5, §6 table, §6.3, §6.4, §6.5, §6.8,
§6.9, §7, §8, §9.1, §10, §11.2–§11.4, §11.10, §12.1–§12.4, §12.6, §16).

## Global Constraints

- Work on local branch `v0.2`; push only per Task 1 and Task 9. Merge into `next` by fast-forward only
  (`git push origin v0.2:next`), never with GitHub's merge button. No tag, no release, no version change:
  `VERSION`, `plugin.json` and `marketplace.json` stay `0.1.0`.
- **Nothing about the trial enters this repo:** no product name, domain, outputs, screenshots, Figma links or local
  paths, in files, commit messages or the PR. `python3 scripts/sanitize_scan.py` passes on every commit.
- Commits: short subject only, ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Author and
  committer stay `17962237+Marwan-G@users.noreply.github.com` (check `git log --format='%ae %ce'`).
- Skills: kebab-case, `name` = directory, `SKILL.md` ≤ 500 lines, description ≤ 1024 characters, detail in
  `references/`. `python3 scripts/lint_skills.py plugins/pavedline/skills` exits 0.
- Agent `model:` lines come from `config/models.yaml` via `python3 scripts/gen_agent_models.py`; `--check` passes.
  Never `haiku`.
- Every step skill reads the records in the `state` skill's order, asks only what is undecided (spec §6.5), records
  each answer as a decision (`decisions/0000-template.md` format, number after the highest existing), ends with
  `STATE.md` pointing at the next step (time from `date "+%Y-%m-%d %H:%M"`) and "go?".
- Ask-before-adding (spec §12.6) wording appears in every step skill that can introduce a service: state what it is,
  what it will do, why nothing already in use does it, and its verified cost; wait for the founder.
- Vendor and version facts are checked on the web at writing time and recorded with URL and date in the skill's
  `references/sources.md`. Nothing from memory.
- Full test suite: `python3 -m unittest discover -s tests -t .` passes before every commit.
- **Trial runs prove the workflow only** (founder, 2026-11-08): a step passes when it runs as a user would, asks
  its questions, writes each output with its expected structure, and moves `STATE.md` on. No quality iteration, no
  completeness beyond that; effort goes into fixing plugin defects.

## Rulings (made while planning; each changes the design doc's PR lists)

1. **`reviewer` agent moves into PR 1.** Step 5's gate is a blind reviewer `APPROVE`; PR 2 extends the same agent
   to code diffs.
2. **Step 6 copies no stack templates in PR 1.** The stack pack, `helm-base-chart` and `gitops` are PR 2; step 6
   here records the chosen pack and writes the Helm and environment layout as a document. PR 2 adds the copy.
3. **README status line and roadmap change only in the final `next → main` PR.** On `next`, the step pages,
   `docs/architecture.md`, `ARCHITECTURE.dot` and `CHANGELOG.md ▶ Unreleased` describe what works.
4. **Code Connect.** Figma's help centre (2026-11-08) lists Code Connect on Professional, Organization and
   Enterprise with a Dev or Full seat; Professional allows one active framework (React is enough). If the founder's
   account cannot use it, step 7 writes a Figma-name → code-name table in `DESIGN.md` instead and says so.

## Review Focus

1. **A project started with v0.1** (no `docs/architecture/`, `docs/data/` … folders): each step creates the folders
   it writes, and never fails on their absence. → Task 4 test.
2. **Step re-entry** (spec §6, "Re-entry"): a changed step-4 answer recorded as a superseding decision lists the stale
   outputs and adds them to `STATE.md ▶ STALE`. → Task 4 test.
3. **Single-tenant project:** `TENANCY-LIFECYCLE.md`, RLS and the leak test do not apply; the skills say "not
   applicable (decision 0002)" instead of inventing tenancy. → Tasks 4, 5 tests.
4. **A surface dropped in decision 0005** (for example no mobile): no mobile screens, offline questions or store
   lead times are asked for it. → Tasks 4, 7 tests.
5. **A missing dependency or login** (Figma not logged in, Redocly not installable): the step stops, adds a
   `WAITING.md` item, and does not mark itself done. → Tasks 5, 7 tests.

---

### Task 1: Integration branch and trial bootstrap

**Files:** Modify `.github/workflows/ci.yml` (`push.branches`), `docs/superpowers/specs/2026-11-08-v0.2-v0.4-build-design.md` (§5 rows for PR 1/2 per Rulings 1–2).

- [ ] **Step 1:** `ci.yml` `on.push.branches: [main, next]`. Add the four rulings to the design doc's §5 (one line each).
- [ ] **Step 2:** Full suite passes; commit `CI on next; PR 1 rulings`.
- [ ] **Step 3:** Create `next` on the remote from `origin/main`: `git push origin origin/main:refs/heads/next`.
      Set `v0.2`'s upstream to `origin/next`. Tell the founder (one line) a ruleset blocking force-push and deletion
      on `next` is recommended; add it to the closing summary, do not wait for it.
- [ ] **Step 4: Trial dependencies.** In the founder's Claude Code config, install what Pavedline needs and is
      missing (`claude plugin list --json`; today `mattpocock-skills` and `product-management` are absent). Announce
      what, why, and the exact command first (doctor rule, spec §12.2); the permission prompt is the approval.
- [ ] **Step 5: Trial steps 0–3.** Create the trial folder (path from the private trial note, outside this repo,
      `git init`, no remote). Run `/pavedline:start`, step 1, step 2 and step 3 there in a headless session
      (`claude -p --plugin-dir <repo>/plugins/pavedline --output-format json`, continued with `--resume <id>`),
      answering as the trial's founder with the recommended defaults. Pass: `PRODUCT.md`, decisions 0001–0007,
      `docs/business/BRIEF.md`, `SEO-STRATEGY.md`, `docs/spec/SPEC.md` exist and `STATE.md` says `STEP: 4`.
      Any v0.1 defect found is fixed in this repo first (own commit, with a test).

### Task 2: Agents — architect, designer, design-verifier, reviewer

**Files:** Create `plugins/pavedline/agents/{architect,designer,design-verifier,reviewer}.md`; Test
`tests/test_agents.py`.

**Produces:** agent names `architect`, `designer`, `design-verifier`, `reviewer` used by Tasks 4–7.

- [ ] **Step 1: Write the failing test** `tests/test_agents.py`:
  - every file in `agents/` has frontmatter `name` = file stem and a `model:` line equal to `models.yaml`;
  - `design-verifier` and `reviewer` `disallowedTools` contain `Write`, `Edit`, `MultiEdit`, `NotebookEdit`;
  - `design-verifier` also disallows `mcp__plugin_figma_figma__use_figma`,
    `mcp__plugin_figma_figma__generate_figma_design`, `mcp__plugin_figma_figma__create_new_file`,
    `mcp__plugin_figma_figma__upload_assets`;
  - `architect` disallows `Bash` and `NotebookEdit`;
  - body texts: reviewer contains `VERDICT: APPROVE` and `VERDICT: REJECT` and "reads the diff, never the summary";
    design-verifier contains `DESIGN VERDICT: APPROVE`, `DESIGN VERDICT: REJECT` and "never approves a visual";
    every agent body says its first report line records the model that ran.
- [ ] **Step 2:** run, expect FAIL (files missing).
- [ ] **Step 3:** write the four agents (jobs and access from spec §8), then `python3 scripts/gen_agent_models.py`.
- [ ] **Step 4:** test passes; `gen_agent_models.py --check` exits 0; commit `Agents for steps 4–7`.

### Task 3: Templates for steps 4–7

**Files:** Create `plugins/pavedline/templates/docs/{architecture,data,api,design,production}/README.md`; Modify
`templates/docs/rules-index.md`; Test `tests/test_start_project.py`.

- [ ] **Step 1: Failing test** `test_step_4_7_folders_copied`: after `start_project.py` into an empty dir, each of the
      five `docs/<folder>/README.md` exists; `rules-index.md` has rows whose Home cells are `docs/architecture/`,
      `docs/data/`, `docs/api/`, `docs/design/`, `docs/production/LEAD-TIME.md`.
- [ ] **Step 2:** FAIL. **Step 3:** each README is ≤ 10 lines: what the folder holds and which step writes it.
- [ ] **Step 4:** PASS; `test_template_sizes` still passes; commit `Templates for steps 4–7`.

### Task 4: Step 4 — `system-design` and `backend-evaluate`

**Files:** Create `skills/system-design/SKILL.md` + `references/{questions.md,tenancy-lifecycle.md,auth-contract.md,sources.md}`,
`skills/backend-evaluate/SKILL.md` + `references/sources.md`, `docs/steps/04-system-design.md`; Modify
`skills/spec/SKILL.md` (§6 close); Test `tests/skills/test_steps_4_7.py`.

**Consumes:** agents `architect`, `researcher`; decisions 0002 (tenancy), 0003 (compliance), 0005 (surfaces).

- [ ] **Step 1: Failing tests** in `test_steps_4_7.py` (`read(name)` reads `SKILL.md` + all its `references/*.md`):
  - `system-design` has `## Round 1: platform`, `## Round 2: behaviour`, `## Round 3: reach` in that order;
  - every area of spec §6.3 appears as a heading in `references/questions.md`: Backend · Auth · Security and
    compliance · Concurrency · Time and scheduling · Scheduled jobs · Performance · Images and files · Real-time ·
    Notifications · Payments taken by tenants · Billing · Accessibility · Mobile offline · Multi-region · Service
    mesh · Website, blog and SEO · Search · Availability and recovery;
  - exact strings: `Clerk (default), or do you need something else?` · `"Not needed" is valid only with a recorded
    reason` · `Next.js is frontend only` · `WCAG 2.2 AA` · `never designed to a free tier`;
  - outputs named: `docs/architecture/SYSTEM-DESIGN.md`, `docs/architecture/AUTH.md`,
    `docs/architecture/TENANCY-LIFECYCLE.md`, `docs/production/LEAD-TIME.md`, `WAITING.md`;
  - `tenancy-lifecycle.md` has the eight stages of spec §6.4 and the line `not applicable (decision 0002)`;
  - re-entry: `system-design` contains `STALE` and `supersedes`;
  - v0.1 projects: every step-4–7 skill says it creates its output folder when missing;
  - surfaces: `system-design` contains `decision 0005` and says questions for a dropped surface are skipped;
  - `backend-evaluate` contains `FastAPI is the preferred default`, the three pass criteria of §6.3 and
    `the founder decides`;
  - `spec` no longer says step 4 ships later and ends pointing at `system-design`;
  - `docs/steps/04-system-design.md` exists and is linked from `docs/steps/03-spec.md`.
- [ ] **Step 2:** FAIL. **Step 3:** write the skills and page from spec §6.3, §6.4 and the auth contract row;
      `architecture-intake` style: one question at a time, default stated, then wait. Lead-time register items go to
      both `LEAD-TIME.md` and `WAITING.md`.
- [ ] **Step 4:** PASS, lint, full suite, sanitize; commit `Step 4: system design`.
- [ ] **Step 5: Trial run.** Run step 4 on the trial (Task 1 method). Pass: one decision per answered area, the five
      output files filled with numbers (no "TBD"), backend-evaluate report with URLs and dates, lead-time items in
      `WAITING.md`, `STATE.md` at `STEP: 5`. Fix the plugin for anything missing, re-run, commit fixes separately.

### Task 5: Step 5 — `domain-model`, `db-schema`, `multi-tenancy`, `api-contract`

**Files:** Create the four skills (+ `references/`), `docs/steps/05-data-and-api.md`; Modify `CREDITS.md`,
`THIRD_PARTY_NOTICES.md` (the adapted `saas-multi-tenant` skill and the Supabase Postgres practices, after checking
their licences on GitHub); Test `tests/skills/test_steps_4_7.py`.

**Consumes:** `docs/architecture/*` from step 4; `GLOSSARY.md`; agent `reviewer`; skill `diagram`.

- [ ] **Step 1: Failing tests:**
  - outputs: `docs/data/DOMAIN.md`, `docs/data/erd.dot`, `docs/data/SCHEMA.md`, `docs/data/MIGRATIONS.md`,
    `docs/api/openapi.yaml`;
  - `multi-tenancy` exact strings from §12.3: `does not own` · `BYPASSRLS` · `FORCE ROW LEVEL SECURITY` ·
    `current_setting('app.tenant_id')` · `SET LOCAL` · `session advisory locks` · `Storage keys start with the
    tenant id` · `cross-tenant leak test` · `not applicable (decision 0002)`;
  - `db-schema`: `expand/contract` · `down` · `never float` · `read as text`;
  - `api-contract`: `/v1` · `Idempotency-Key` · `the tenant comes from the verified token` · the pinned
    `@redocly/cli@<version> lint` command · on lint failure the step is not done;
  - the step's gate text: blind `reviewer` returns `VERDICT: APPROVE` before the founder's go; a `REJECT` means
    rework, never arguing past it;
  - domain names must exist in `GLOSSARY.md` (the skill says it adds missing terms first);
  - credits test (existing `test_credits_cover_dependencies` pattern): `saas-multi-tenant` appears in `CREDITS.md`.
- [ ] **Step 2:** FAIL. **Step 3:** write skills and page; pin `@redocly/cli` to the npm version that is at least
      two weeks old today (check `npm view @redocly/cli time`), record in `references/sources.md`; add Redocly to
      `doctor.py`'s tool list as optional-for-step-5 with its install line, plus a `test_doctor.py` case.
- [ ] **Step 4:** PASS, lint, full suite, sanitize; commit `Step 5: data and API`.
- [ ] **Step 5: Trial run.** Pass: five outputs, `erd.dot` renders and passes `dot -Tcanon`, `openapi.yaml` lints
      clean, every tenant table in `SCHEMA.md` has `tenant_id NOT NULL` and an RLS policy, reviewer `APPROVE`
      recorded, `STATE.md` at `STEP: 6`.

### Task 6: Step 6 — `system-architecture` and `threat-model`

**Files:** Create both skills (+ `references/`), `docs/steps/06-architecture.md`; Test `tests/skills/test_steps_4_7.py`.

- [ ] **Step 1: Failing tests:** outputs `docs/architecture/ARCHITECTURE.dot` (+ `.svg` via `diagram`),
      `docs/architecture/DEPLOYMENT.md` (environments local · staging · production, `values-local.yaml`,
      `values-staging.yaml`, `values-production.yaml`, namespaces, which apps), `docs/architecture/THREATS.md`;
      `system-architecture` contains `nextjs-fastapi` and `Gateway API` and says the stack templates are copied in a
      later release (Ruling 2); `threat-model` covers tenancy, auth, secrets, uploads, webhooks, and compliance when
      decision 0003 is yes, each threat with a mitigation and where it is enforced.
- [ ] **Step 2–4:** FAIL → write → PASS, lint, suite, sanitize; commit `Step 6: architecture`.
- [ ] **Step 5: Trial run.** Pass: three outputs, diagram renders, every step-4 service appears in the diagram,
      `STATE.md` at `STEP: 7`.

### Task 7: Step 7 — `design-system-contract` and the Figma dependency

**Files:** Create `skills/design-system-contract/SKILL.md` (+ `references/`), `docs/steps/07-figma.md`; Modify
`plugin.json` (`dependencies` + `figma@claude-plugins-official`), `doctor.py` (`PLUGINS`), `CREDITS.md`,
`tests/test_manifests.py`, `tests/test_doctor.py`, README install note only if the install command changes.

- [ ] **Step 1: Check `ui-ux-pro-max`:** if it installs as a Claude Code plugin from a marketplace, it becomes a
      dependency (marketplace added to `allowCrossMarketplaceDependenciesOn` and the README's marketplace list);
      otherwise it is an optional reference in `doctor` and the skill. Record the evidence in `references/sources.md`.
- [ ] **Step 2: Failing tests:** manifest dependencies include `figma@claude-plugins-official`; doctor lists it;
      `design-system-contract` names `docs/design/DESIGN.md`, tokens light and dark, `Figma name = code name`,
      every screen in every state (empty · loading · error · success · no permission · offline on mobile), the
      §6.4 screens (suspended tenant, export, delete, impersonation banner, legal pages) and the §11.4 "please
      update" screen, accessibility annotations, the skills `figma-use`, `figma-generate-library`,
      `figma-generate-design`, `figma-use-figjam`, `figma-code-connect` (and `impeccable` as optional critique), the Code Connect fallback (Ruling 4), the
      gate `DESIGN VERDICT: APPROVE` then the founder approves the visual, and "if the Figma login is missing, stop
      and add it to `WAITING.md`"; it ends saying step 8 ships in a later release.
- [ ] **Step 3–4:** FAIL → write → PASS, lint, suite, sanitize; commit `Step 7: Figma`.
- [ ] **Step 5: Trial run in Figma** (the founder's account, private file). Pass (workflow only): the Figma process runs
      end to end on a small sample — variables with light/dark, a few components, one frame per selected surface,
      one FigJam flow; `DESIGN.md` with node links, `docs/design/tokens.json`, Code Connect or the name table,
      design-verifier verdict recorded, `STATE.md` at `STEP: 8`.

### Task 8: Docs and diagram

**Files:** Modify `docs/architecture.md` (skills, agents, step count), `ARCHITECTURE.dot`/`.svg` (Skills and Agents
counts), `CHANGELOG.md ▶ Unreleased` (Added: steps 4–7), `docs/flow.dot` only if its step 4–7 labels disagree with
the skills.

- [ ] **Step 1:** update; `python3 scripts/dot_check.py` and the diagram CI check pass; README untouched (Ruling 3).
- [ ] **Step 2:** full suite, sanitize; commit `Docs for steps 4–7`.

### Task 9: Whole-branch review, PR, merge into `next`

- [ ] **Step 1: Blind review.** A fresh `reviewer` subagent (gates 2–3) reads `git diff origin/next...v0.2`, not any
      summary. A fresh adversarial subagent too (3b applies: CI and the manifest change). Fix every finding through
      the same test cycle or record it `accepted — <reason>`; one narrow re-check per fix round.
- [ ] **Step 2:** `git log --format='%ae %ce' origin/next..v0.2` shows only the noreply address; sanitize passes.
- [ ] **Step 3:** push `v0.2`; `gh pr create --base next --title "Steps 4–7"` with a one-line body, the gates line,
      and a short evidence list (step · trial run date · checks passed; no trial content).
- [ ] **Step 4:** wait for every CI check green (`gh pr checks --watch`).
- [ ] **Step 5:** merge by fast-forward: `git push origin v0.2:next`; confirm GitHub shows the PR merged and
      `git log --format='%ae %ce' -n <count> origin/next` is noreply only. Delete the remote `v0.2` branch.
- [ ] **Step 6:** tell the founder in a short summary: what landed, the trial evidence, the recommended `next`
      ruleset, and that PR 2 (steps 8–11) is next.
