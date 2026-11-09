# Pavedline v0.3 (PR 2: steps 8–11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** steps 8–11 (plan, build, deploy to local, learn) work end to end, the `nextjs-fastapi` stack pack builds,
boots and deploys to kind in Pavedline's own CI, step 6 copies the pack, and all of it lands on `next` as one
reviewed PR.

**Architecture:** new skills and agents under `plugins/pavedline/`; the stack pack under
`plugins/pavedline/stacks/nextjs-fastapi/` and the infra and CI templates under `plugins/pavedline/templates/`, both
copied into a product repo by scripts; a Pavedline CI job generates a neutral starter project from them and builds,
tests, boots and deploys it to kind through Argo CD. Each step skill is then run on the private trial.

**Tech stack:** Markdown skills · Python 3.10+ stdlib (Pavedline scripts and tests) · the starter: Next.js ≥ 16.3,
pnpm, Biome, Expo, FastAPI, uv, ruff, pyright, Alembic, Postgres 16+ · Helm 4 (library chart) · Argo CD
ApplicationSets · kind + CloudNativePG (existing `local-cluster`) · a Gateway API controller · GitHub Actions on
arm64 runners. Every version is checked on the web when the task runs (see Global Constraints).

**Spec:** `docs/superpowers/specs/2026-11-08-v0.2-v0.4-build-design.md` (how) and
`docs/superpowers/specs/2026-11-07-pavedline-design.md` (what: read §6 table rows 6 and 8–11, §6.7, §6.9, §8, §9,
§10, §11.1–§11.7, §11.9–§11.11, §12.1–§12.4, §12.6, §14, §15, §16).

## Global Constraints

- Work on local branch `v0.3` cut from `origin/next`; push only in Task 16. Merge into `next` by fast-forward only
  (`git push origin v0.3:next`). No tag, no release, no version change: `VERSION`, `plugin.json` and
  `marketplace.json` stay `0.1.0`; new work goes under `CHANGELOG.md ▶ Unreleased`. README only where a fact it
  states changes (Task 1); its status line and roadmap wait for the final `next → main` PR.
- **Nothing about the trial enters this repo:** no product name, domain, wording, outputs, paths or Figma links, in
  files, commits or the PR. `python3 scripts/sanitize_scan.py` (with the git-ignored local deny-list) passes on every
  commit. Starter and example names are neutral (`example`, `items`, `acme`).
- Commits: short subject only, ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Author and
  committer stay `17962237+Marwan-G@users.noreply.github.com`.
- Skills: kebab-case, `name` = directory, `SKILL.md` ≤ 500 lines, description ≤ 1024 characters, detail in
  `references/`, vendor facts in `references/sources.md` with URL and date. `lint_skills.py` exits 0.
- Agents: an explicit `tools:` allowlist each; `model:` lines generated from `config/models.yaml`
  (`gen_agent_models.py --check` passes); never `haiku`.
- **Pins:** every version in a template is exact and at least two weeks old today (npm `time`, PyPI, GitHub
  releases); container images by digest; GitHub Actions by full SHA with the tag in a comment; charts by version and
  digest where OCI. Each pin's URL and date go in the owning skill's `references/sources.md`. Images are linux/arm64
  (and amd64 where the base image offers it).
- Step skills follow the shared step rules (Task 1 moves them into `skills/state/references/step-rules.md`); each
  ends with `STATE.md` pointing at the next step (time from `date "+%Y-%m-%d %H:%M"`) and "go?".
- Ask-before-adding (spec §12.6) wherever a skill can introduce a service. Local tools on doctor's list are not
  services.
- Full suite `python3 -m unittest discover -s tests -t .` passes before every commit; starter checks (Task 11's
  `scripts/starter_check.sh`) pass before every commit that touches `stacks/` or `templates/infra`/`.github`.
- **Trial runs prove the workflow only** (founder, 2026-11-08): a step passes when it runs, asks its questions,
  writes its outputs with the expected structure and moves `STATE.md` on. Build steps stop once the build starts
  correctly. Cap 30 minutes per run; stop at the first gate verdict. After every run, write lessons to the
  git-ignored `workflow-lessons.md` and fix the plugin (never the trial's outputs).

## Rulings (made while planning)

1. **The stack pack lives in the plugin:** `plugins/pavedline/stacks/nextjs-fastapi/`, not the repo root shown in
   spec §14, because only the plugin directory is installed. Same for infra and CI templates
   (`plugins/pavedline/templates/{infra,.github}`).
2. **PR 1's Ruling 2 ends:** step 6 now copies the pack and the infra templates (Task 10).
3. **CI weight:** PR 2's smoke job deploys the starter with a 1-instance CNPG, Argo CD and the Gateway API. The full
   run (3 instances, Barman Cloud backup to a local S3 store, restore drill) belongs to production readiness and
   lands in PR 3 with step 12.
4. **Argo CD syncs from a local git server** in kind: a `kind-git` container on the kind network, built from a
   pinned `alpine` digest with `git-daemon`, serving bare mirrors; `deploy` pushes the branch there. If Argo CD does
   not accept `git://`, the same image serves smart HTTP via `git http-backend`. It is a local tool, not a service.
5. **`ui-ux-pro-max` is optional** (founder, 2026-11-09), like `impeccable`: removed from `plugin.json`
   dependencies and the marketplace allow-list; doctor lists it as optional.
6. **The adversary is read-only** (Read, Grep, Glob): it returns concrete failing inputs; the builder turns each into
   a red test.
7. **Contract checks (lesson L5.9),** run in the product's CI: (a) every operation the FastAPI app serves exists in
   `docs/api/openapi.yaml` with the same method, path and response field names, and contract operations not built
   yet are listed (failure only once `plan-graph` reports feature-complete); (b) every table in the migrated
   database is in `docs/data/SCHEMA.md` and passes the RLS check.
8. **Mobile CI:** Android debug build on Linux; an unsigned iOS simulator build on macOS runners only if they are
   free for public repos (checked on the web, recorded); the mobile job runs on PRs touching the mobile template,
   and weekly.

## Review Focus

1. **A surface dropped in decision 0005** (no mobile or no site): `apply_stack.py` copies no app, Helm chart, CI job
   or Argo CD app for it, and nothing references it. → Task 10 test.
2. **Single-tenant product (decision 0002):** no RLS check, no leak fixture; the skills and CI say
   `not applicable (decision 0002)`. → Tasks 5, 10 tests.
3. **Copying into a repo that already has files:** `apply_stack.py` never overwrites; it prints each clash as
   `conflict: <path>` and exits 1 (same contract as `start_project.py`). → Task 10 test.
4. **Deploy pointed at a non-kind context:** the deploy script refuses before any command, and the cluster hook
   blocks it too. → Task 9 test.
5. **A merged change that never built** (a skip-CI marker in the squash message, or a tag that is not the merge
   SHA): `deploy` never reports "verified". → Task 9 test.

---

### Task 1: Branch and carry-ins

**Files:** Modify `plugins/pavedline/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`scripts/doctor.py`, `README.md` (the ui-ux-pro-max install lines only), `CREDITS.md`, `docs/architecture.md`,
`skills/design-system-contract/{SKILL.md,references/sources.md}`, the nine step-4–7 skills; Create
`skills/state/references/step-rules.md`; Test `tests/test_manifests.py`, `tests/test_doctor.py`, `tests/test_docs.py`,
`tests/skills/test_steps_4_7.py`.

- [ ] **Step 1:** `git switch -c v0.3 origin/next`.
- [ ] **Step 2: Failing tests:** dependencies no longer contain `ui-ux-pro-max@ui-ux-pro-max-skill`; the allow-list
      is `["claude-plugins-official", "knowledge-work-plugins"]`; doctor puts `ui-ux-pro-max` in `OPTIONAL_PLUGINS`
      (never fails the doctor); README and `docs/architecture.md` call it optional; CREDITS row says optional.
      Shared rules: `step-rules.md` holds the paragraphs now repeated in the step skills (read order, ask only what
      is undecided, `decided in NNNN`, one decision per answer, `one approval turn`,
      `default for the rest of this round`, foreground agents, ask-before-adding, re-entry with `supersedes` and
      `STALE`); each of the nine skills names `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md` in its
      first section and no longer repeats those paragraphs. Change `test_steps_4_7.py`'s `read(name)` to include
      `step-rules.md`, so the existing needles still hold.
- [ ] **Step 3:** FAIL. **Step 4:** make the changes (`${CLAUDE_PLUGIN_ROOT}` is substituted in plugin skill content:
      code.claude.com/docs/en/skills.md, checked 2026-11-09). **Step 5:** PASS, lint, suite, sanitize; commit
      `Optional ui-ux-pro-max; shared step rules`.
- [ ] **Step 6: Trial check (≤ 10 min):** resume a step-6 or step-7 session on the trial with "what are the shared
      step rules you follow here?". Pass: the answer quotes `step-rules.md` (proves it is read).

### Task 2: Agents — builder, adversary, deployer; reviewer for code

**Files:** Create `agents/{builder,adversary,deployer}.md`; Modify `agents/reviewer.md`; Test `tests/test_agents.py`.

**Produces:** `pavedline:builder`, `pavedline:adversary`, `pavedline:deployer`, used by Tasks 9, 13, 14.

- [ ] **Step 1: Failing tests:** every agent has `tools:`; adversary and reviewer have no Write, Edit, Bash or
      NotebookEdit; builder has Read, Write, Edit, Bash, Grep, Glob, WebFetch, WebSearch and no Figma tools;
      deployer has Read, Write, Edit, Bash, Grep, Glob. Body needles: builder `own worktree`, `red first`,
      `approval quoted in the prompt`, `handoff/<branch>.md`; adversary `ADVERSARIAL: APPROVE`,
      `ADVERSARIAL: REJECT`, `concrete input`, `stop rule`; deployer `kind-pavedline-`,
      `never the Synced label`, `never runs kubectl apply or helm upgrade against a cloud cluster`; reviewer adds
      `scanner output` and `code diff` beside its document mode. Every agent's first report line records the model.
- [ ] **Step 2–4:** FAIL → write (jobs from spec §8, gates from §9.1) → `gen_agent_models.py`, PASS; commit
      `Agents for steps 8–11`.

### Task 3: Helm base chart

**Files:** Create `templates/infra/helm/base-chart/` (`Chart.yaml` `type: library`, `templates/_*.tpl`,
`values.schema.json`), `templates/infra/helm/example-app/` (a tiny application chart using it, for tests),
`skills/helm-base-chart/SKILL.md` + `references/sources.md`; Test `tests/test_helm_base_chart.py`.

- [ ] **Step 1: Failing tests** (skipped with a printed reason when `helm` is absent; CI has it): `helm lint` and
      `helm template` of `example-app` pass with each of `values-local.yaml`, `values-staging.yaml`,
      `values-production.yaml`; the rendered manifests contain: liveness and readiness probes, requests and limits, a
      PodDisruptionBudget, an HPA only when enabled, topology spread, `runAsNonRoot: true`,
      `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`, one
      ServiceAccount per workload with `automountServiceAccountToken: false`, a default-deny NetworkPolicy plus the
      allows from values, a priorityClassName, an HTTPRoute (Gateway API) when routed, and a migration Job annotated
      `argocd.argoproj.io/hook: PreSync`; a values file missing `image.tag` fails `helm template` (schema).
- [ ] **Step 2–4:** FAIL → write → PASS. Checkov on the rendered output runs in CI (Task 8 adds it to the template
      workflows and Task 11 to Pavedline's job); pin it now in `sources.md`. Commit `Helm base chart`.

### Task 4: GitOps templates and local-cluster additions

**Files:** Create `templates/infra/k8s/applicationsets/{addons,apps}.yaml`, `templates/infra/k8s/addons/README.md`
(the reserved observability slot, spec §12.5), `skills/gitops/SKILL.md` + `references/sources.md`; Modify
`scripts/local-cluster/{up.sh,down.sh,verify.sh,versions.env}`, `skills/local-cluster/SKILL.md`; Create
`scripts/local-cluster/git-server/Dockerfile`; Test `tests/test_gitops_templates.py`,
`tests/test_local_cluster_static.py`.

- [ ] **Step 1: Failing tests:** the addons ApplicationSet has `automated` with `selfHeal: true`; the apps one has no
      `automated` block and `preserveResourcesOnDeletion: true`; both use a git directory generator over
      `infra/k8s/{addons,apps}/*`; `versions.env` pins the Gateway API CRDs, the controller chart (Envoy Gateway by
      default, Apache-2.0, unless the web check shows a better-maintained conformant option; record why) and the
      git-server base image digest; `up.sh` installs both and starts `kind-git`; `down.sh --all` removes `kind-git`;
      `verify.sh` checks a `Gateway` is `Programmed`; `gitops` names "CI builds images and commits the tag bump; it
      never syncs" and Ruling 4.
- [ ] **Step 2–4:** FAIL → write → PASS; `up.sh ci && verify.sh ci && down.sh ci --all` passes locally on Colima
      and in CI's existing `local-cluster` job. Commit `GitOps templates; Gateway API and git server on local`.

### Task 5: `fastapi-service` and the API

**Files:** Create `stacks/nextjs-fastapi/pack.yaml` (surfaces → paths, skills enabled, tools), 
`stacks/nextjs-fastapi/files/services/api/` (uv project, `pyproject.toml`, `uv.lock`, ruff and pyright strict
config, `.importlinter`, `app/` with settings (Pydantic v2), a token verifier (JWKS), `SET LOCAL app.tenant_id` per
transaction, `/healthz`, `/readyz` (database), Alembic with explicit SQL creating the owner/runtime roles' grants and a global `tenants` table; `tests/`; `Dockerfile` with an in-image boot check),
`stacks/nextjs-fastapi/files/scripts/{rls_check.py,contract_check.py}`, `stacks/nextjs-fastapi/example/` (a neutral
`docs/api/openapi.yaml`, a tenant-scoped `/v1/items` route with `Idempotency-Key`, its migration (an `items` table
with `FORCE ROW LEVEL SECURITY`) and tests; copied only by Pavedline's starter check, never into a product, whose
own step-5 contract and first slices replace it), `skills/fastapi-service/SKILL.md` +
`references/sources.md`; Test `tests/test_stack_api.py` (static), and the pack's own pytest suite.

- [ ] **Step 1: Failing tests** (static, in Pavedline's suite): files exist; `pyproject.toml` pins exact versions;
      no `float` in money-typed fields (grep rule in `fastapi-service`); `rls_check.py` and `contract_check.py` have
      `--help`. **Pack tests** (pytest, against a throwaway Postgres given by `DATABASE_URL`): migrations up and
      down; `rls_check.py` fails on a table without FORCE RLS and passes on the starter; the cross-tenant leak
      fixture (two tenants; every route and every job type as tenant A with tenant B's ids must fail) passes, and a
      route not in the fixture's registry fails it; the runtime role cannot `SET ROLE` to the owner; a request
      without a verified token is 401; an `Idempotency-Key` replay with a different body is 422;
      `contract_check.py` passes against a starter `openapi.yaml` and fails when a route is added to the app only.
- [ ] **Step 2–4:** FAIL → write → PASS (`uv run ruff check`, `ruff format --check`, `pyright`, `lint-imports`,
      `pytest`; `docker build` boots). Commit `Stack pack: API`.

### Task 6: Web, site and packages

**Files:** Create under `stacks/nextjs-fastapi/files/`: root `package.json`, `pnpm-workspace.yaml`,
`pnpm-lock.yaml`, `biome.json`, `tsconfig.base.json`; `apps/web` (Next.js ≥ 16.3, App Router, standalone output, a
home page that calls the API's `/healthz` through the generated client (the example adds an items list), `/healthz`, vitest, an axe check in Playwright,
Dockerfile + boot check); `apps/site` (Next.js + MDX, one post, `sitemap.xml`, `robots.txt`; non-public origins send
`X-Robots-Tag: noindex`); `packages/api-client` (generated from `docs/api/openapi.yaml` by a pinned generator, a
check that it is current), `packages/tokens` (from `docs/design/tokens.json`), `packages/glossary`; the `RUN.md`
fragment; Test `tests/test_stack_web.py` (static).

- [ ] **Step 1: Failing tests:** files exist; exact pins (no `^`/`~`) in every `package.json`; Next.js version
      ≥ 16.3.0; `biome.json` present; the skills list in `pack.yaml` names the Next.js and Vercel skills of spec
      §6.9 (deploy-to-Vercel excluded).
- [ ] **Step 2–4:** FAIL → write → PASS (`pnpm install --frozen-lockfile`, `biome ci`, `tsc --noEmit`, vitest,
      `next build` for both apps, both images boot). Commit `Stack pack: web, site, packages`.

### Task 7: Mobile and `mobile-build`

**Files:** Create `stacks/nextjs-fastapi/files/apps/mobile/` (Expo, one screen calling `/healthz`, jest, the
accessibility lint rule set, a minimum-version check that shows the blocking update screen), `skills/mobile-build/`
(`expo prebuild`; Xcode on macOS runners; Gradle on Linux; signing material in GitHub encrypted secrets imported
into a temporary keychain per job and deleted after; EAS only through ask-before-adding; store submission is a
founder step) + `references/sources.md`; Test `tests/test_stack_mobile.py`.

- [ ] **Step 1: Failing tests:** files exist; exact pins; the skill contains `temporary keychain`, `deleted`,
      `founder step`, `ask-before-adding`, and Ruling 8 with its web evidence.
- [ ] **Step 2–4:** FAIL → write → PASS (typecheck, lint with the a11y rules, jest; `expo prebuild` and an Android
      debug Gradle build once locally or in CI). Commit `Stack pack: mobile`.

### Task 8: CI templates and scanners

**Files:** Create `templates/.github/{workflows/*.yml,CODEOWNERS,pull_request_template.md}`,
`templates/renovate.json`, `templates/scripts/{pr_checks.py,sanitize_scan.py,dot_check.py,dot_drift.py}` (copies of
Pavedline's, made generic), `templates/.sanitize-denylist`; Test `tests/test_ci_templates.py`.

- [ ] **Step 1: Failing tests:** every `uses:` is a 40-char SHA; jobs exist for: arm64 image build + boot + tag bump
      (on main only, never a sync), unit/typecheck/lint per app, DB tests on a throwaway Postgres at the merge gate
      (label `ci:db`), `rls_check` + leak fixture + `contract_check`, the local-cluster end-to-end job, `.dot`
      validate/render/drift, Semgrep, Trivy, Checkov (Helm output), gitleaks, OWASP ZAP baseline against the local
      cluster, axe and Lighthouse, Helm lint/template, the OpenAPI breaking-change diff (pinned tool), the gates-line
      check, the deny-list scan, Renovate (weekly, grouped, patch auto-merge for dev tooling only; never cluster
      add-ons, CNPG, Argo CD, base images or Terraform providers); every workflow sets `permissions:` minimal;
      `pull_request_template.md` has the gates line and `Post-deploy check:`; jobs for a surface are marked so
      `apply_stack.py` can drop them.
- [ ] **Step 2–4:** FAIL → write → PASS; `actionlint` (pinned) on the templates in Pavedline's CI. Commit
      `CI templates and scanners`.

### Task 9: `deploy` (step 10)

**Files:** Create `skills/deploy/SKILL.md` + `references/sources.md`, `stacks/nextjs-fastapi/files/scripts/deploy_local.sh`,
`docs/steps/10-deploy.md`; Test `tests/test_deploy.py`.

**Consumes:** Task 4 (`kind-git`, Gateway), Tasks 5–7 (images, charts).

- [ ] **Step 1: Failing tests:** `deploy_local.sh` refuses any context that is not `kind-pavedline-*` before running
      anything (exit 2, message); it builds each changed image with a unique tag (`git rev-parse --short HEAD` plus a
      counter), pushes to `localhost:5001`, commits the tag bump to `values-local.yaml`, pushes the branch to
      `kind-git`, syncs each changed app with an Argo CD operation, then verifies the running state: pods run the new
      tag with 0 restarts, `/healthz` and `/readyz` answer through the Gateway, the PR's `Post-deploy check:` passes.
      The skill: migrations first (PreSync); a CI run must exist for the merge SHA and the tag bump must equal it; a
      skip-CI marker means not verified; on failure revert and record (spec §11.4, §11.5); report "verified (local)"
      only after all checks.
- [ ] **Step 2–4:** FAIL → write → PASS (shell tests with stubbed `kubectl`/`docker`/`git` on `PATH`). Commit
      `Step 10: deploy`.

### Task 10: Step 6 copies the pack

**Files:** Create `scripts/apply_stack.py`; Modify `skills/system-architecture/SKILL.md` (Ruling 2 text replaced),
`skills/design-system-contract/SKILL.md` (§7 close: continue to step 8, no "later release"),
`docs/steps/06-architecture.md`, `docs/steps/07-figma.md`; Test `tests/test_apply_stack.py`,
`tests/skills/test_steps_4_7.py`.

- [ ] **Step 1: Failing tests:** `apply_stack.py --target DIR --pack nextjs-fastapi --surfaces web,api [--tenancy
      single|multi] [--dry-run]` copies only the chosen surfaces' apps, charts, CI jobs and Argo CD apps (Review
      Focus 1); single-tenant drops the RLS check and leak fixture and writes `not applicable (decision 0002)` in
      `RUN.md` (Review Focus 2); a clash prints `conflict: <path>` and writes nothing, exit 1 (Review Focus 3);
      `system-architecture` calls it with surfaces from decision 0005 and tenancy from 0002, and no longer says
      "copied in a later release"; `design-system-contract` ends with `STEP: 8 — Plan` and points at `plan-graph`.
- [ ] **Step 2–4:** FAIL → write → PASS; commit `Step 6 copies the stack pack`.
- [ ] **Step 5: Trial run (≤ 20 min):** on the trial, ask step 6 to copy the pack for its decided surfaces. Pass:
      the files land, nothing for a dropped surface, `scripts/starter_check.sh`'s static and unit checks run green on the trial repo (run after Task 11 lands).

### Task 11: The starter job in Pavedline's CI

**Files:** Create `scripts/starter_check.sh`, `tests/fixtures/starter-answers.json` (neutral: multi-tenant, all
four surfaces); Modify `.github/workflows/ci.yml` (jobs `starter` and `starter-mobile`), `CONTRIBUTING.md`.

- [ ] **Step 1:** `starter_check.sh` generates a product repo in a temp dir with `start_project.py` then
      `apply_stack.py` (Task 10), and runs every check of Tasks 5–8 on it, then
      `local-cluster/up.sh`, `deploy_local.sh`, `verify`, `down.sh`. Exit 0 only if all pass.
- [ ] **Step 2:** `starter` job on `ubuntu-24.04-arm` on every PR and push to `next`/`main`; `starter-mobile` per
      Ruling 8 (paths filter + weekly `schedule`). Pins per Global Constraints.
- [ ] **Step 3:** run `starter_check.sh` locally green; commit `Starter job`; the CI run is proved in Task 16.

### Task 12: Intent capture and `plan-graph` (step 8)

**Files:** Create `templates/docs/intent/{README.md,0000-template.md}`, `templates/docs/plans/README.md`,
`skills/plan-graph/SKILL.md` + `references/`, `scripts/plan_graph.py`, `docs/steps/08-plan.md`; Modify
`skills/spec/SKILL.md` (a "change" mode), `templates/docs/rules-index.md`; Test `tests/test_plan_graph.py`,
`tests/skills/test_steps_8_11.py`.

- [ ] **Step 1: Failing tests:** the intent template has `Status: proposed | accepted | rejected` and the headings
      Problem · Proposed outcome · Affected users and systems · Constraints · Open questions; `spec` change mode turns
      an accepted intent into a `SPEC.md` change, a decision and new `AT-` tests; `plan_graph.py` reads
      `docs/spec/SPEC.md` (`AT-001` …) and `docs/plans/*.md` (slices list `AT-` ids), and prints unmapped tests
      (exit 1), duplicate slice ids, and `feature-complete` only when every test maps to a merged slice (from
      `git log`); it writes `docs/plans/<date>-<wave>.dot` and validates with `dot -Tcanon`; `plan-graph` names
      `superpowers:writing-plans`, the first wave as a thin vertical slice (spec §6.7), accepted intents as input,
      the founder's wave approval, and closes with `STEP: 9 — Build`.
- [ ] **Step 2–4:** FAIL → write → PASS; commit `Step 8: plan; intent capture`.
- [ ] **Step 5: Trial run (≤ 30 min):** step 8 on the trial. Pass: a plan file and `.dot`, every `AT-` mapped or
      listed, the approval question asked, `STATE.md` at `STEP: 9`.

### Task 13: `quality-gates` (step 9) and the remaining hooks

**Files:** Create `skills/quality-gates/SKILL.md` + `references/`, `scripts/hooks/{warn_dot_drift.py,warn_pr_gates.py}`,
`docs/steps/09-build.md`; Modify `hooks/hooks.json`; Test `tests/hooks/test_warn_hooks.py`,
`tests/skills/test_steps_8_11.py`.

- [ ] **Step 1: Failing tests:** the five gates in order with the PR line `Gates: TDD ✓ · review ✓ (n found, m fixed)
      · security ✓ · adversarial ✓|n/a · verification ✓`; 3b triggers (auth, tenancy, IAM, infra, CI, secrets, input
      parsing, payments, migrations); one narrow re-check per fix round, a full new review only after a high fix;
      reviewers get scanner output with the diff; builder in its own worktree; rebase and re-prove before each merge;
      `handoff/<branch>.md`; the full suite once at the merge gate. Hooks: `gh pr create` without the gates line
      warns; an edit under a folder with `ARCHITECTURE.dot` and no `.dot` change warns; both exit 0 on bad input.
- [ ] **Step 2–4:** FAIL → write → PASS; commit `Step 9: quality gates`.
- [ ] **Step 5: Trial run (≤ 30 min, stop once the build starts):** step 9 on the first slice of the trial's wave.
      Pass: a worktree and branch exist, a red test is written by `pavedline:builder`, then stop.

### Task 14: Step 10 on the trial, and `lessons` (step 11)

**Files:** Create `skills/lessons/SKILL.md` + `references/`, `templates/docs/retros/README.md`,
`docs/steps/11-learn.md`; Test `tests/skills/test_steps_8_11.py`.

- [ ] **Step 1: Failing tests:** `lessons` writes `docs/retros/<date>.md`, uses `retro` (mattpocock-skills), puts each
      new rule in the one place `docs/rules-index.md` names, may write `docs/intent/` items, and closes with
      `STEP: 8 — Plan` for the next wave or the integration wave when `plan_graph.py` says feature-complete (ships in
      a later release).
- [ ] **Step 2–4:** FAIL → write → PASS; commit `Step 11: lessons`.
- [ ] **Step 5: Trial runs (≤ 30 min each):** step 10 deploys the trial's starter to its kind cluster and reports
      "verified (local)"; step 11 writes a retro. Pass as the tests say.

### Task 15: Docs and diagram

**Files:** Modify `docs/architecture.md` (skill and agent counts, the stack pack), `ARCHITECTURE.dot`/`.svg`,
`docs/flow.dot` only if its labels disagree, `CHANGELOG.md ▶ Unreleased`, `docs/steps/07-figma.md` "Next:" line,
`CONTRIBUTING.md` (starter check).

- [ ] **Step 1:** update; `dot_check.py`, `test_docs.py`, sanitize pass; commit `Docs for steps 8–11`.

### Task 16: Whole-branch review, PR, merge into `next`

- [ ] **Step 1:** fresh blind `reviewer` (opus, gates 2–3) on `git diff origin/next...v0.3`, and a fresh adversarial
      reviewer (3b applies: CI, infra, auth, tenancy, migrations). One fix dispatch, one scoped re-check; residuals
      `accepted — <reason>`.
- [ ] **Step 2:** committer check (noreply only); sanitize; squash the branch into one commit `Steps 8–11` if any
      earlier commit carries wording the final tree removed.
- [ ] **Step 3:** push `v0.3`; `gh pr create --base next --title "Steps 8–11"`, one line + gates line + short
      evidence list (step · trial date · checks; no trial content).
- [ ] **Step 4:** every check green, including `starter` (`gh pr checks --watch`).
- [ ] **Step 5:** `git push origin v0.3:next`; confirm merged; delete the remote branch.
- [ ] **Step 6:** short summary to the founder: what landed, trial evidence, lessons, and that PR 3 (v0.4) is next.
