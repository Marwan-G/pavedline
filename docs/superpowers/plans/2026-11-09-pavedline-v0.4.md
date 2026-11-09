# Pavedline v0.4 (PR 3: the integration wave and step 12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the database is production-ready (three instances, backups, a restore drill proven on kind), the integration
wave runs before step 12, step 12 (`go-to-production`, the two infra profiles, `LAUNCH.md`) works up to the founder's
first `apply`, the Grow loop (`seo-foundation`, `content-ops`, the `growth` agent) exists, the optional cockpit mod
ships, and all of it lands on `next` as one reviewed PR.

**Architecture:** new skills, agent and templates under `plugins/pavedline/`; the infra profiles under
`plugins/pavedline/templates/infra/profiles/{byo-kubernetes,oci-oke}`; the cockpit as a second plugin
`plugins/pavedline-cockpit/` listed in the marketplace. Database readiness and the alerts are proven in Pavedline's
own CI by the starter check's new `full` stage on kind; the BYO profile is proven by bootstrapping a second kind
cluster; the OCI profile by static checks only (no cloud run, build design §3). Each step skill is then run on the
private trial.

**Tech stack:** Markdown skills · Python 3.10+ stdlib (scripts, tests) · CloudNativePG + the Barman Cloud CNPG-I
plugin · a local S3-compatible store (Task 3) · Mailpit and a local SMS sink · a webhook tunnel (Task 5) · OpenTofu /
Terraform HCL with the `oracle/oci` provider · Argo CD · kind · GitHub Actions on arm64. Every version is checked on
the web when the task runs.

**Spec:** `docs/superpowers/specs/2026-11-08-v0.2-v0.4-build-design.md` (how) and
`docs/superpowers/specs/2026-11-07-pavedline-design.md` (what: §6 table row 12, §6.6 Grow, §6.7, §6.8, §6.10, §11.6,
§11.8, §11.10, §11.11, §12.1, §12.4, §12.5, §12.6, §13, §15, §17).

**Carry list:** `.superpowers/sdd/2026-11-09-pavedline-v0.3/pr3-carry.md` (private). Every item there is either done by
a task below or listed in Task 15's left-behind list with a reason.

## Global Constraints

- Work on local branch `v0.4` cut from `origin/next` (69331c6); push only in Task 15. Merge into `next` by
  fast-forward only (`git push origin v0.4:next`). No tag, no release, no version change: `VERSION`, `plugin.json`
  and `marketplace.json` stay `0.1.0` (the cockpit plugin entry starts at `0.1.0` too); new work goes under
  `CHANGELOG.md ▶ Unreleased`. README only where a stated fact changes; its status line, roadmap and release table
  wait for the final `next → main` PR.
- **Nothing about the trial enters this repo:** no product name, domain, wording, outputs, paths or Figma links, in
  files, commits or the PR. `python3 scripts/sanitize_scan.py` (with the git-ignored local deny-list) passes on every
  commit. Example names are neutral (`example`, `items`, `acme`). Never put the trial's words in a test.
- Commits: short subject only, ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Author and
  committer stay `17962237+Marwan-G@users.noreply.github.com`.
- Skills: kebab-case, `name` = directory, `SKILL.md` ≤ 500 lines, description ≤ 1024 characters, detail in
  `references/`, vendor facts in `references/sources.md` with URL and date; step skills read
  `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md` first and end with `STATE.md` pointing at the next
  step (time from `date "+%Y-%m-%d %H:%M"`) and "go?". `lint_skills.py` exits 0.
- Agents: an explicit `tools:` allowlist each; `model:` lines generated from `config/models.yaml`
  (`gen_agent_models.py --check` passes); never `haiku`.
- **Pins:** exact, at least two weeks old today; images by digest; Actions by full SHA with the tag in a comment;
  charts by version and digest where OCI. Each pin's URL and date in the owning skill's `references/sources.md`.
  linux/arm64 (and amd64 where offered).
- **Ask-before-adding** (spec §12.6) wherever a skill can introduce a service; the agent never creates an account.
  Local tools on doctor's list are not services.
- **Cloud safety:** nothing in this PR runs against a cloud. Every `apply`, bootstrap or secret placement in a cloud
  is printed for the founder and recorded in `NEEDS.md`/`WAITING.md`. The cluster hook keeps blocking mutating
  commands outside `kind-pavedline-*`. Terraform rules (spec §15): an applied plan shows `0 to destroy` and nothing
  replaced; no state surgery; removals calculated item by item.
- Before every commit the controller re-runs the five checks itself: `python3 -m unittest discover -s tests -t .`,
  `scripts/lint_skills.py`, `gen_agent_models.py --check`, `dot_check.py --check`, `sanitize_scan.py`; plus
  `scripts/starter_check.sh` stages touched by the change; plus the pinned gitleaks image on a `git archive` export
  under `$HOME` before the push.
- **Trial runs prove the workflow only** (founder, 2026-11-08): a step passes when it runs, asks its questions, writes
  its outputs with the expected structure and moves `STATE.md` on. Cap 30 minutes per run. After every run, write
  lessons to the git-ignored `workflow-lessons.md` and fix the plugin (never the trial's outputs).

## Rulings (made while planning)

1. **Where the integration wave lives.** Spec §12.1 adds no skill for it and build design §6.1 says PR lists are
   exhaustive, so it is a section of `plan-graph` (how the wave is planned once feature-complete), `local-cluster`
   (the local fakes and the tunnel) and `fastapi-service` (webhook signature checks). No new skill name.
2. **Mobile in the integration wave** stops at simulator builds (build design §5: no Apple or Google developer
   accounts). TestFlight and the internal track are written as founder steps in `mobile-build` and
   `LAUNCH.md`, not proven.
3. **OpenTofu in CI.** The OCI profile is plain HCL that both `tofu` and `terraform` accept; Pavedline's CI validates
   it with OpenTofu (MPL-2.0) because spec §16 allows only open-source tools inside the factory. The profile README
   says either CLI works. (Licence facts: Task 8 `sources.md`.)
4. **The BYO profile is proven on kind:** CI bootstraps a second cluster `kind-pavedline-byo` with the profile's own
   script, as a stand-in for "your cluster". The OCI profile gets static checks only (`fmt`, `validate`, Checkov).
5. **The three alerts** (spec §11.11) ship as an in-cluster checker (a CronJob: public endpoints, last backup, late
   scheduled jobs) that posts to a notify URL and pings an external dead-man's switch. The external monitor is a
   service: `go-to-production` proposes it under ask-before-adding; locally the notify URL is a sink and the test
   proves each alert fires.
6. **Plugin eval suites** (`claude plugin eval`, v2.1.269+, `evals/<case>/{prompt.md,graders/*.md}`; every run is a
   real model call) ship for the key step skills; they run locally with `--max-cost-usd`; CI runs them only if the
   founder adds an API key (spend → founder).
7. **The cockpit** is a separate plugin, a mod (`hooks/hooks.json` `"modules": ["./register.js"]`, `register(on,
   options)`, a `Pane` render site); nothing in `pavedline` depends on it.
8. **Backups use the Barman Cloud CNPG-I plugin** (v0.15.1, needs cert-manager, installed in `cnpg-system`); the
   in-tree `barmanObjectStore` is deprecated and removed in CNPG 1.32. **The local S3 store is SeaweedFS**
   (Apache-2.0, arm64, active; MinIO community is archived) — a local tool, not a service.
9. **SMS fake** is a tiny stdlib HTTP sink in the stack (no maintained open-source Twilio mock found); email fake is
   Mailpit (MIT).
10. **Facts from the docs check (2026-11-09):** `${CLAUDE_PLUGIN_DATA}` = `~/.claude/plugins/data/<id>/`, kept across
    updates, exported to hooks (not to the Bash tool); agent `maxTurns` returns partial output; `SubagentStop` input
    has `agent_type`, `last_assistant_message`, `stop_hook_active`; skill `disallowed-tools` exists; `userConfig`
    options reach hooks as `CLAUDE_PLUGIN_OPTION_<KEY>`. Sources go in the owning skill's `sources.md`.

## Review Focus

1. **A restore that "passes" without restoring:** the drill must write a marker row before the backup, restore into a
   NEW cluster name, and read that row back from the restored cluster; a drill against the original cluster or with
   no marker fails. → Task 3 test.
2. **Go live with an unticked item:** `launch_check.py` refuses while any `LAUNCH.md` item is unticked and has no
   recorded exception (`exception: decisions/NNNN`), including items added by the product later. → Task 6 test.
3. **A Terraform change that destroys or replaces:** the profile's plan checker fails on any `delete` or
   `replace` action in `tofu show -json` output. → Task 8 test.
4. **A secret leaking through the profile:** no value in git; vault shells never overwrite a value placed by hand
   (`ignore_changes`); hooks still block `.env*` reads. → Tasks 7, 8 tests.
5. **An alert that never fires:** each of the three checks is driven red on kind (endpoint down, backup failed or
   too old, job late) and the sink receives exactly one message per alert. → Task 4 test.

---

### Task 1: Carry-ins from PR 2

**Files:** Modify `scripts/starter_check.sh` (static stage: pinned gitleaks on a `git archive` export),
`plugins/pavedline/skills/quality-gates/SKILL.md` (pre-push gitleaks), `plugins/pavedline/skills/system-architecture`
or the step-6 skill that runs `apply_stack.py` + `scripts/apply_stack.py` (Postgres major as a pack parameter;
compare with the product's database decision and stop on a mismatch), `stacks/nextjs-fastapi/files/infra/k8s/apps/postgres/{values.yaml,templates/pooler.yaml}` (PgBouncer image pinned by digest),
`scripts/start_project.py` + `templates/.gitignore` (ships `.worktrees/`); Test the matching `tests/` files.

- [ ] Failing tests: `apply_stack.py --postgres-major 18` rewrites the image line to the pack's pinned 18 image or
      exits 1 with `postgres major 18 not pinned in this pack` (the pack lists its pinned majors); the step-6 skill
      names the comparison; pooler template sets `spec.template.spec.containers[0].image` from `pooler.image`, a
      digest-pinned value; a new product from `start_project.py` has `.gitignore` with `.worktrees/`; the starter
      static stage calls gitleaks with the pinned image. → FAIL → implement → PASS → commit `PR 2 carry-ins`.

### Task 2: Claude Code features (carried)

**Files:** `plugins/pavedline/hooks/hooks.json`, hook scripts, `agents/builder.md`, read-only skills' frontmatter,
`.claude-plugin/plugin.json` (userConfig), `tests/`. Exact field names come from the Task 2 research notes in the
ledger (official docs, 2026-11-09; see Ruling 10).

- [ ] Hook state moves from `$TMPDIR` to `${CLAUDE_PLUGIN_DATA}` (fallback `$TMPDIR` when unset); builder gets
      `maxTurns`; a SubagentStop hook warns (never blocks) when a builder's last message lacks the report shape;
      read-only review skills get `disallowed-tools`; eval suites for `start` and `plan-graph`
      under the documented location (`go-to-production` gets its case in Task 6). Commit `Claude Code features from PR 2 carry list`.

### Task 3: Database production readiness

**Files:** `scripts/local-cluster/{versions.env,up.sh,verify.sh}` (`--full`: the Barman Cloud plugin, its
prerequisites, the local S3 store), `stacks/nextjs-fastapi/files/infra/k8s/apps/postgres/templates/{objectstore.yaml,scheduledbackup.yaml}`
+ values (backups on when `backup.enabled`; local values point at the local store), `stacks/.../scripts/restore_drill.sh`,
`skills/local-cluster`, `skills/deploy` (drill section), `scripts/starter_check.sh` (`--stage full`),
`.github/workflows/ci.yml` (`starter-full`: PRs touching `stacks/`, `templates/infra`, `scripts/local-cluster`, and
weekly); Test `tests/test_postgres_backup.py`, `tests/test_starter_check.py`.

- [ ] Failing tests (static): rendered postgres chart with production values has 3 instances, anti-affinity, an
      ObjectStore + plugin reference, a ScheduledBackup, WAL archiving; local values with `backup.enabled=false`
      render none of it; the drill script refuses a target cluster name equal to the source and any non-kind
      context. → FAIL → implement → PASS.
- [ ] Kind proof: `starter_check.sh --stage full` on the Mac: 3 instances ready, a backup completes, the drill
      restores into `db-restore` and reads the marker row, then tears down. Commit `Backups and the restore drill`.

### Task 4: The three alerts

**Files:** `templates/infra/k8s/addons/alerts/` (chart: CronJob + ConfigMap of checks + Secret ref for the notify and
heartbeat URLs), `skills/deploy` or `skills/gitops` (where it is documented), `scripts/starter_check.sh` (`full`
stage drives each alert red); Test `tests/test_alerts.py`.

- [ ] Failing tests: the chart renders the three checks; no URL value in git; schedule and lateness thresholds are
      values. Kind proof: endpoint down, backup failed/too old, job late → exactly one sink message each; all green →
      heartbeat only. Commit `The three alerts`.

### Task 5: The integration wave

**Files:** `skills/plan-graph` (integration-wave section: when it is due, what it contains, its exit), 
`skills/local-cluster` + `scripts/local-cluster/` (Mailpit and an SMS sink as local-only apps; `tunnel.sh` starting
the pinned tunnel to the Gateway's host port), `stacks/.../services/api` (webhook signature verification helper for
the two signature schemes the defaults use, with replay window and idempotent handling, plus tests),
`skills/fastapi-service`, `skills/mobile-build` (TestFlight / internal track as founder steps),
`templates/WAITING.md` example lines; Test `tests/test_integration_wave.py`, stack API tests.
Tunnel: the founder's choice (asked 2026-11-09), recorded in the trial's `SERVICES.md`; Stripe webhooks use
`stripe listen --forward-to` (no tunnel).

- [ ] Failing tests: plan-graph `status` reports `integration wave due` once feature-complete and step 12 refuses to
      start until the wave's plan is merged and verified; the webhook helper rejects a bad signature, a stale
      timestamp and a replay, and accepts a valid one; `tunnel.sh` refuses without the founder's approval line in
      `SERVICES.md`. Commit `Integration wave`.

### Task 6: `go-to-production` (step 12) and `LAUNCH.md`

**Files:** `skills/go-to-production/{SKILL.md,references/{intake.md,launch.md,sources.md}}`,
`templates/docs/production/{INFRA.md,NEEDS.md,LAUNCH.md}`, `scripts/launch_check.py`, `skills/deploy` (staging and
production: verified (cloud), promotion by PR from the verified staging SHA, `promote.py`), `agents/deployer.md`,
`agents/architect.md`, `templates/STATE.md` (`GROW DUE`), `templates/RUN.md` (rotation + break-glass);
Test `tests/skills/test_step_12.py`, `tests/test_launch_check.py`, `tests/test_promote.py`.

- [ ] Failing tests: the skill asks the spec §6.10 questions in order ("is it time to go to production?" → infra
      intake → "what I need from you"); every NEEDS item is mirrored in WAITING; every `apply` is the founder's;
      `launch_check.py` (Review Focus 2); `promote.py` writes only a SHA that `deploy` recorded as verified on
      staging and opens a PR, never pushes production directly. Commit `Step 12`.

### Task 7: BYO-Kubernetes profile

**Files:** `templates/infra/profiles/byo-kubernetes/{README.md,bootstrap.sh,values/}` (Argo CD, the add-ons, the
ApplicationSets pointed at the product repo; Cloudflare Tunnel ingress manifests with a token Secret reference),
`.github/workflows/ci.yml` (`profile-byo` job: second kind cluster), `scripts/starter_check.sh` or a new
`scripts/profile_check.sh`; Test `tests/test_profile_byo.py`.

- [ ] Failing tests: `bootstrap.sh` prints every command and needs `--context` + `--yes`; it refuses a context it
      was not given; no secret value in the profile. Kind proof: bootstrap `kind-pavedline-byo`, Argo CD syncs the
      addons. Commit `BYO-Kubernetes profile`.

### Task 8: OCI/OKE profile (Terraform)

**Files:** `templates/infra/profiles/oci-oke/{README.md,*.tf,variables.tf,terraform.tfvars.example,plan_check.py}`
(VCN, subnets, OKE with arm64 node pools — labels and taints in native resources, no cloud-init — IAM, Vault →
Kubernetes Secret with `ignore_changes`, the backup bucket with versioning and lifecycle, a budget alarm; every
identifier a placeholder), `.github/workflows/ci.yml` (`profile-oci`: `tofu fmt -check`, `tofu init -backend=false`,
`tofu validate`, Checkov), `skills/go-to-production/references/sources.md`; Test `tests/test_profile_oci.py`.

- [ ] Failing tests: Review Focus 3 and 4; no real OCID pattern (sanitize already fails on `ocid1`); node pools carry
      labels and taints in Terraform, never `user_data`. Commit `OCI/OKE profile`.

### Task 9: Grow — `seo-foundation`, `content-ops`, the `growth` agent

**Files:** `skills/seo-foundation/`, `skills/content-ops/`, `agents/growth.md` + `config/models.yaml`,
`templates/docs/growth/{README.md,calendar.md}`, `plugin.json` dependency `marketing@knowledge-work-plugins`,
`scripts/doctor.py`; Test `tests/skills/test_grow.py`, `tests/test_agents.py`, `tests/test_manifests.py`.

- [ ] Failing tests: publish loop order (brief → draft → founder approves → SEO checklist → PR → deploy → request
      indexing); the founder approval is required before a PR; weekly/monthly/quarterly cadence; `STATE.md ▶ GROW
      DUE` is written; growth agent tools exclude Bash pushes and deploy; staging stays `noindex`. Commit `Grow loop`.

### Task 10: The cockpit mod

**Files:** `plugins/pavedline-cockpit/` (plugin manifest, the pane, `/pavedline-status`), marketplace entry;
Test `tests/test_cockpit.py`. Mod API: code.claude.com/docs/en/plugins/mods/reference.md (Ruling 7); `claude
plugin validate` and `claude plugin test` must pass.

- [ ] Failing tests: reads `STATE.md`, `WAITING.md` and the open slice's `handoff/` file only; draws nothing and
      exits 0 when they are missing; `pavedline` has no reference to the cockpit. Commit `Cockpit mod`.

### Task 11: Docs and diagram

**Files:** `docs/steps/12-*.md`, `docs/steps` integration-wave and Grow pages, `docs/architecture.md`,
`ARCHITECTURE.dot/.svg` (via `dot_check.py`), `docs/flow.dot` if a node changes, `CHANGELOG.md ▶ Unreleased`,
`CREDITS.md`, `THIRD_PARTY_NOTICES.md`, README (changed facts only: requirements, install line for the cockpit);
Test `tests/test_docs.py`.

### Task 12: Trial — integration wave

On the private trial: plan the integration wave (step 8), run the local fakes and the tunnel, deliver one real
provider test webhook if the founder has created the test account (otherwise record it in the trial's `WAITING.md`).
Lessons → plugin fixes.

### Task 13: Trial — step 12 to the first apply

On the private trial: run `go-to-production` through the infra intake (answering as the trial founder: BYO
Kubernetes), `NEEDS.md`, the filled profile, and `launch_check.py` refusing "go live". Nothing is applied. Lessons →
plugin fixes.

### Task 14: Trial — Grow, once

On the private trial: `content-ops` writes one brief and a draft; it stops at the founder-approval gate. Lessons →
plugin fixes.

### Task 15: Whole-branch review, PR, merge into `next`

- [ ] Blind reviewer (gates 2+3) and blind adversary (3b: hooks, CI, infra, secrets) on `git diff origin/next...v0.4`;
      fix rounds per the narrow re-review rule; findings `fixed` or `accepted — <reason>`.
- [ ] Left-behind list written to the private carry file for the final `next → main` PR.
- [ ] Squash private wording if any commit held it; gitleaks export check; push `v0.4`; PR into `next` (one line +
      gates line); CI green including `starter-full` and the profile jobs; `git push origin v0.4:next`; delete the
      remote branch; memory updated.
