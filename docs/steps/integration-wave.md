# Integration wave (once, before step 12)

Starts when `plan_graph.py status` prints `feature-complete` and `integration wave: due`, and you say go. Skills: `plan-graph` (how the wave is planned), `local-cluster` (the local fakes and the tunnel), `fastapi-service` (webhook signature checks), `mobile-build` (simulator builds). There is no separate skill; this is one more wave, planned once.

## What it is for

Local verification cannot prove a real provider. This wave runs the product against the providers' test modes and real webhooks, still on your machine, so step 12 does not find the first surprise.

## Before you start

Every slice of every earlier wave merged and verified (local). Only the providers your product uses are in it; each is a service already listed in `SERVICES.md`, and each account is yours to open (a line in `WAITING.md`).

## What you will be asked

To approve the wave plan (`docs/plans/<date>-integration.md`, header line `Wave: integration`, slices `int.<n>` with `Tests: none`) as you approve any wave, and to approve the Cloudflare quick tunnel in `SERVICES.md` if a provider needs a public URL. Pavedline never creates an account.

## What it uses

- **Local fakes:** `up.sh <project> --fakes` adds Mailpit (email inbox and API) and a small SMS sink to the cluster, in a `fakes` namespace. No account, nothing leaves the cluster. The product points at them in its local values only.
- **Cloudflare quick tunnel:** `scripts/local-cluster/tunnel.sh <project>` gives a temporary public URL for a provider's webhook. Free, no account, testing only, the URL changes at each start, so it needs your approval row in `SERVICES.md` first. Stop it when the check is done.
- **Stripe:** `stripe listen --forward-to` forwards test events to the local API; no tunnel.
- **Webhook signatures:** the API checks the raw body against the provider's signature, accepts a signed event once and refuses a replay or a bad signature. One slice sends a real event through and shows all three.
- **Mobile:** simulator and emulator builds only. TestFlight and the Play internal track are your steps, with store accounts you open (lead times are in `docs/production/LEAD-TIME.md`); they are not proven here.

## Output files

`docs/plans/<date>-integration.md`, the slices' pull requests, and a line `Verified: local — <date>, <what was seen>` in the plan's header block.

## Checks and gate

Every slice merged and the header line present; then `plan_graph.py status` prints exactly `integration wave: done`. Step 12 refuses to start before that. The wave never claims `verified (cloud)`; real DNS and TLS, cloud IAM, multi-node failure and real load stay unproven until step 12.

## Who approves

You approve the plan, the tunnel row and each merge.

## Hand-off

Step 11 closes the wave and `STATE.md` then says `STEP: 12 — Go to production`.

Next: [step 12](12-go-to-production.md), go to production.
