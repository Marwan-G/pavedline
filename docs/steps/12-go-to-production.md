# Step 12: Go to production (once)

Starts when `STATE.md` says `STEP: 12` and you say go. Skill: `go-to-production`. Agents: `deployer` and `architect`, in the foreground.

## What it is for

Binding the portable decisions of steps 0 to 11 to real infrastructure, then getting the product live in the right order: staging, one buffer wave, production, launch.

## Before you start

The skill first runs `plan_graph.py status` and refuses unless it prints `feature-complete` and the exact line `integration wave: done`. If not, it says what is missing and stops without asking anything ([integration wave](integration-wave.md)). Then it asks whether it is time to go to production; anything but a clear yes ends the step.

## What you will be asked

An intake, one area at a time, each with options and a recommended default: cloud account and provider, an existing cluster or a new one, regions, domain and DNS, registry, secrets store, object storage, managed database, email domain, budget ceiling. Anything that would be a new service or cost is asked first, with its cost. Pavedline never creates an account.

## Output files

`docs/production/INFRA.md` and one decision record per answer; `NEEDS.md`, everything only you can do, mirrored line for line in `WAITING.md`; `LAUNCH.md`; `deployments.md`; the filled infra profile.

## The two profiles

- **Bring your own Kubernetes** (default): `bootstrap.sh` installs Argo CD and the add-ons on a cluster you own. CI proves it on a second kind cluster.
- **OCI/OKE:** OpenTofu or Terraform files for the network, cluster, backup bucket, budget and vault. CI checks them statically (format, validate, Checkov); `plan_check.py` must pass on your saved plan (`0 to destroy`, nothing replaced) before you apply.

## What the agents never do

Every `plan`, `apply`, bootstrap and secret placement is yours. The agent prints the exact command, records it in `NEEDS.md` and `WAITING.md`, and waits. The cluster hook blocks cluster commands outside the local cluster. Secrets go into the vault by you, never into chat or a file.

## The order

1. **Staging first**, deployed through GitOps and verified (cloud) by the person who synced it; recorded in `deployments.md`.
2. **One buffer wave** for what real infrastructure reveals.
3. **Production by pull request:** `scripts/promote.py --sha <sha>` refuses a SHA without a verified staging record, rewrites the production image digests to staging's and prints the commands. You merge and sync, then record the production line.
4. Store and sitemap submissions are yours.

## Checks and gate

`LAUNCH.md` is a blocking checklist: every item ticked with evidence, or excepted by an accepted decision record. `scripts/launch_check.py` exits 0 only then, and "go live" is refused until it does. Two items are always there: the **restore drill** passed (a backup restored into a scratch cluster and read back), and the **three alerts** proved to fire (public endpoints down, last backup too old, a scheduled job late; checked in-cluster, with an external dead-man's switch you approve as a service).

## Who approves

You, at each question, each apply and each merge, and the final "Go live?".

## Hand-off

`STATE.md` is set to `STEP: Grow — after launch`.

Next: [Grow](grow.md), the standing loop for search and content.
