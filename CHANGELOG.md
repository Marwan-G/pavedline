# Changelog

All notable changes to Pavedline are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Records hooks: `PreCompact` keeps the key `STATE.md` lines and open waiting items in the compaction summary; `Stop` reminds Claude to commit uncommitted record files (never blocks).
- Step skills pre-approve the scripts they run (`apply_stack.py`, `plan_graph.py`, `doctor.py`, `start_project.py`) and nothing else; the `builder` agent preloads `quality-gates`.
- Starter check: `scripts/starter_check.sh` generates a neutral product from the stack pack and builds, tests, boots and deploys it to kind; CI jobs `starter` (every PR) and `starter-mobile` (Android and iOS native builds, path-filtered and weekly).
- Steps 4-7: system design (with backend evaluation), data and API (domain model, schema, multi-tenancy, OpenAPI
  contract), architecture (system architecture, threat model) and design (Figma, design-system contract); four new
  agents (`architect`, `reviewer`, `designer`, `design-verifier`) and optional doctor checks for Redocly and impeccable.
- Reviewers approve only when every required check ran; otherwise `REJECT — incomplete`.
- `/pavedline:doctor` no longer reports Pavedline missing when it is loaded with `--plugin-dir`.
- CI templates: stack-neutral records and Renovate workflows, the scanner scripts and deny-list copied at step 0; per-surface CI, security, end-to-end (kind, ZAP, axe, Lighthouse), OpenAPI breaking-change and image-build workflows in the `nextjs-fastapi` pack. Every action by SHA, every image by digest; actionlint runs over both trees in Pavedline's CI.
- Step 6 copies the stack pack: `apply_stack.py` copies the `nextjs-fastapi` pack for the chosen surfaces only (apps, Helm charts, CI jobs, Argo CD apps), drops the tenant-isolation checks for a single-tenant product, never overwrites, and prints what is left to fill in. Step 7 now continues to step 8.
- Step 8, plan: `plan-graph` turns the spec's acceptance tests into a wave of slices, checks the mapping with `plan_graph.py`, and asks for approval as its own question.
- Step 9, build: `quality-gates` runs each slice through five gates in its own worktree, with an adversarial review on risky slices.
- Step 10, deploy to local: `deploy` and `deploy_local.sh` sync through Argo CD and report `verified (local)` only after the running pods and the pull request's post-deploy checks pass.
- Step 11, learn: `lessons` turns a wave's retro into one rule, one intent or a dropped note per lesson.
- Stack pack `nextjs-fastapi`: API, web, website, mobile, shared charts and the database chart, with the `fastapi-service`, `mobile-build`, `helm-base-chart` and `gitops` skills.
- GitOps templates (Helm library chart, Argo CD ApplicationSets) and local cluster additions: a Gateway API controller and a local git server (`kind-git`) that Argo CD syncs from.
- Intent capture: `docs/intent/` holds proposed changes, and accepted ones are specced before they are planned.
- Agents `builder`, `adversary` (read-only) and `deployer`; warn hooks for a pull request body without the gates line and for code changed without its `ARCHITECTURE.dot`.

### Changed
- `ui-ux-pro-max` is now optional: removed from the plugin dependencies, and `doctor` lists it as optional.

### Fixed
- The local cluster needs helm 4.2.2 or newer. helm 4.2.1 waits the full timeout on every hook deletion
  ([helm#32214](https://github.com/helm/helm/issues/32214)), which made the Argo CD install take 40 minutes on the
  test Mac. `up.sh` refuses an older helm before doing anything; `/pavedline:doctor` reports it with the upgrade
  command. With helm 4.3.1 the same Mac brings the stack up in 56 s.

## 0.1.0 — 2026-11-08

### What works
- Guided steps 0-3: start, market and SEO research, grill, spec.
- Memory files in the user's repository: PRODUCT.md, STATE.md, WAITING.md, GLOSSARY.md and decision records.
- Six hooks: secret guard, cluster guard, no-verify and force-push guard, STATE.md length block, CLAUDE.md length
  warning, session-start state.
- Missing tools and Claude Code plugins: the agent tells you what it will install, why and the exact command, then installs it (Claude Code asks permission for each command; never `sudo`; a refusal goes to WAITING.md).
- `/pavedline:doctor`, local cluster scripts, CI workflows and Renovate configuration.
- Clean-profile install test (`scripts/install_test.sh`): dependencies install automatically once their marketplaces
  are added.

- Local cluster charts (Argo CD, CloudNativePG) are pulled as OCI artifacts from ghcr.io, pinned by version and
  digest; chart downloads are retried, and re-running `up.sh` reuses what is already done.
- README section "What it sets up on your machine".

### Verified
- Local cluster: a full up, verify, down run passed on macOS 26 (Apple silicon, Colima) on 2026-11-08, and runs on
  Linux arm64 (Ubuntu 24.04) in CI on every pull request.

### Known limits
- Linux x86_64 is not yet tested; Windows is not supported.
- Steps 4-12 arrive in later releases.
