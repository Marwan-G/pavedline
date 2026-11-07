# Changelog

All notable changes to Pavedline are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Known limits
- The local cluster scripts have not yet been run live (tools not installed on the build machine).
- CI has not yet run on GitHub.
- Steps 4-12 arrive in later releases.
