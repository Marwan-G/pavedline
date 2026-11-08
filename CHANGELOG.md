# Changelog

All notable changes to Pavedline are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Steps 4-7: system design (with backend evaluation), data and API (domain model, schema, multi-tenancy, OpenAPI
  contract), architecture (system architecture, threat model) and design (Figma, design-system contract); four new
  agents (`architect`, `reviewer`, `designer`, `design-verifier`) and optional doctor checks for Redocly and impeccable.
- Reviewers approve only when every required check ran; otherwise `REJECT — incomplete`.
- `/pavedline:doctor` no longer reports Pavedline missing when it is loaded with `--plugin-dir`.

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
