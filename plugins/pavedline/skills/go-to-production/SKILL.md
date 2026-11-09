---
name: go-to-production
description: Step 12 of Pavedline, run once at the end. Asks first whether it is time to go to production and refuses until plan_graph.py reports feature-complete and the integration wave is merged and verified (local); then runs the infra intake (what do you already have?), writes docs/production/INFRA.md with an ADR per answer, lists what the founder must do in NEEDS.md and WAITING.md, chooses the infra profile (bring your own Kubernetes, or OCI/OKE), fills its variables, and prints every plan, apply and bootstrap for the founder to run. Then cloud staging verified (cloud), one buffer wave, production promoted from the verified staging SHA by PR, store and sitemap submissions, the blocking LAUNCH.md checklist (launch_check.py) and the founder's "go live". Use while STATE.md says STEP 12.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py *) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/launch_check.py *)
---

# go-to-production

Step 12, run once. The `deployer` and the `architect` agents (subagent types `pavedline:deployer`, `pavedline:architect`) run it in the foreground with self-contained prompts. Steps 0 to 11 made only portable decisions; this step binds them to real infrastructure. Outputs: `docs/production/INFRA.md`, `NEEDS.md`, `LAUNCH.md`, `deployments.md`, one ADR per intake answer, the filled infra profile.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

**Nothing here touches a cloud on its own.** Every `plan`, `apply`, bootstrap, secret placement, sync and account step is **the founder's**: print the exact command, record it in `NEEDS.md` and `WAITING.md`, wait. The agents never run kubectl, helm, tofu or terraform against a cloud context (the cluster hook blocks it as well). Secrets go straight into the vault by the founder, never into chat, a file or a log.

## 1. The first question, and the refusal

Continue when `STATE.md` says `STEP: 12 — Go to production`. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_graph.py status`. Read its output generically: **refuse** unless it prints `feature-complete` (exit 0) **and** the exact line `integration wave: done` (its slices merged and its `Verified: local` line in the plan's header; any other state — `not due`, `due`, `planned` — means not yet). If it does not, say what is missing and what to run (the open slices or tests it names; the integration wave section of `plan-graph`, `local-cluster` and `fastapi-service`), do not ask the intake, and leave `STATE.md` at the step before.

Then ask, and wait: **"Everything works on local Kubernetes and the integration wave passed. Is it time to go to production?"** Anything but a clear yes ends the step with `STATE.md` unchanged.

## 2. Infra intake: "what do you already have?"

Ask one area at a time, in this order, each with its options and a recommended default (`${CLAUDE_SKILL_DIR}/references/intake.md` has them): cloud account and provider; an existing cluster or a new one; regions; domain and DNS; container registry; secrets store; object storage; managed database (if chosen); email domain; budget ceiling. A new service or billable resource follows ask-before-adding (shared rules), with a verified cost; the agent never creates an account. From the 5th area on, also offer `default for the rest of this round` (shared rules). When the founder approves the filled-in profile values (the one fill-in turn), proceed straight to filling the values and printing the bootstrap and plan commands (section 4) with no extra wait. Write `docs/production/INFRA.md` (from `templates/docs/production/INFRA.md`) and **one ADR per answer** (`decisions/`). Cloudflare Tunnel ingress with a Gateway behind it is the default; the external uptime monitor for alert 1 is a service and is proposed under ask-before-adding.

## 3. "What I need from you"

Write `docs/production/NEEDS.md` (from the template): accounts, logins, approvals, every `apply` and bootstrap, and secrets placed directly in the vault. **Every item is also a line in `WAITING.md`** (`- Fn · what · where/how · what it unblocks`); the two lists must match. An item leaves only when the founder says it is done.

## 4. Provision

Choose the profile (bring your own Kubernetes is the default; OCI/OKE when the intake says so): `${CLAUDE_PLUGIN_ROOT}/templates/infra/profiles/byo-kubernetes` and `.../oci-oke` (vendor facts: `oci-oke/SOURCES.md`, linked from `${CLAUDE_SKILL_DIR}/references/sources.md`). The agent **fills the profile's variables** from INFRA.md with placeholders only, never a secret. The founder runs, in this order:

1. OCI only: `plan` saved to a file, then `plan_check.py` on it (an applied plan shows `0 to destroy` and nothing replaced); **the founder applies only after `plan_check.py` exits 0.** No state surgery, no `state rm/mv/import`; a removal is calculated item by item.
2. The apply (OCI) or the bootstrap script (bring your own): the agent prints `${CLAUDE_PLUGIN_ROOT}/templates/infra/profiles/byo-kubernetes/bootstrap.sh --context <ctx> --repo-url <url> --revision <sha> --environment staging` (the default prints and runs nothing) and the founder runs the same command with `--yes` in their own terminal; it installs the Argo CD bootstrap and the add-ons. Then the Cloudflare tunnel and secrets (`byo-kubernetes/README.md`).
3. Secrets into the vault, by the founder.

The agent prints each command and stops. It reads results the founder pastes (never secrets).

## 5. Staging, then production

1. **Cloud staging first**: deployed through GitOps, then **verified (cloud)** by the person who synced it (`deploy` skill, section "staging and production"), using the same checks against the cloud cluster. They record `staging · <sha> · verified (cloud) · <date>` in `docs/production/deployments.md`.
2. **One buffer wave** (`plan-graph`) for whatever real infrastructure reveals.
3. **Production** is promoted from the verified staging SHA **by pull request**: `python3 scripts/promote.py --sha <sha>` refuses a SHA without that record, rewrites the production image digests to staging's and prints the commands; a person merges and syncs, then records `production · <sha> · verified (cloud) · <date>`.
4. **Store and sitemap submissions** are the founder's (`mobile-build`, the SEO plan): recorded in `NEEDS.md`.

## 6. `LAUNCH.md`, a blocking checklist

Copy `templates/docs/production/LAUNCH.md` (items in `${CLAUDE_SKILL_DIR}/references/launch.md`). Tick an item only with evidence; an item may end with `exception: decisions/NNNN-<slug>.md` (an accepted ADR). `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/launch_check.py` exits 0 only when every item is ticked or excepted; items a product added later count. **"Go live" is refused unless it exits 0.**

## 7. The founder's "go live", and close

Ask **"Go live?"** only after `launch_check.py` exits 0 and production is verified (cloud). On a clear yes, edit `STATE.md` (time from `date "+%Y-%m-%d %H:%M"`):

```
STEP: Grow — after launch
LAST: <timestamp> — step 12 done: live at <production sha>
NEXT: the Grow loop (SEO and content, the three alerts); every wave goes local, then staging, then production, each promotion by PR
```

Commit and close as in the shared rules, then ask: **go?**
