# Architecture

Pavedline is a Claude Code plugin marketplace. This page explains the diagram below: what gets installed, what it
puts in a project, and the gate every change to Pavedline passes.

<p align="center"><img src="../ARCHITECTURE.svg" alt="Pavedline architecture: the marketplace, the plugin and its parts, your project, and the CI that checks every change" width="100%"></p>

## 1. Install

`/plugin marketplace add Marwan-G/pavedline` reads [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json),
which lists one plugin. `/plugin install pavedline@pavedline` reads its
[`plugin.json`](../plugins/pavedline/.claude-plugin/plugin.json) and installs its three dependencies from their own
marketplaces: `superpowers`, `mattpocock-skills` and `product-management`. If a dependency is missing, Claude Code does
not load Pavedline at all.

## 2. Inside the plugin

| Part | What it is |
|---|---|
| **Templates** | the project memory files copied into a new project: `CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, decision records, docs folders |
| **6 hooks** | checks that run on every tool call: block reading `.env` files and writing secrets; block cluster commands outside the local `kind-pavedline-*` cluster; block `--no-verify` and force-pushes to the main branch; cap `STATE.md` at 60 lines; warn when `CLAUDE.md` grows past 150 lines; print the project state when a session starts |
| **Scripts** | `doctor` (checks tools and plugins), `start_project` (copies the templates), and the local cluster's `up`, `verify` and `down` |
| **12 skills, 1 agent, MCP** | the guided steps (start, market research, spec, …), a read-only `researcher` agent, and the Playwright MCP server for reading real web pages |

## 3. In your project

- **Repository:** `/pavedline:start` copies the templates, so any new session resumes from files, not from memory.
- **Claude Code session:** the skills guide each step and the hooks check every command before it runs.
- **Your machine:** `up.sh` builds a local Kubernetes cluster (kind, Argo CD, CloudNativePG, a local registry) bound
  to `127.0.0.1` only. See [environments](environments.md).

## 4. Every change to Pavedline

1. **Pull request.** From a maintainer or a contributor's fork; Renovate opens dependency updates weekly.
2. **8 required checks + CodeQL** on GitHub Actions: `unit`, `lint`, `sanitize` (no private names), `gitleaks` (no
   secrets), `diagrams`, `plugin-validate`, `local-cluster` (the real cluster on a fresh Linux machine) and
   `pr-body`. CodeQL scans the Python code and the workflows.
3. **Maintainer review.** The maintainer reviews and tests the change locally, then approves and merges with rebase.
   Nothing reaches `main` otherwise: force-pushes and branch deletion are blocked.
4. **Release.** A tagged version; users get it with `/plugin marketplace update`.

How to report a problem or propose a change: [CONTRIBUTING.md](../CONTRIBUTING.md).
