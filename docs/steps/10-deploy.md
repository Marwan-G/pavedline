# Step 10: Deploy to local

Starts when `STATE.md` says `STEP: 10` and you say go. Skill: `deploy`. Agent: `deployer`, run in the foreground.

## What it is for

Putting a merged change on the local Kubernetes cluster the way production will run it (Argo CD syncing from Git), then proving it from what actually runs, not from a status label.

## Before you start

A merged slice with a pull request that names its `Post-deploy check:` (one check per line in a small read-only language: `http <host> <path> <status>` or `kubectl-get <namespace> <kind>[/<name>] [--jsonpath=... --equals=...]`; the deployer shows you the lines and runs them only after your go, and pull request text is never executed as a command), a clean working tree on the merged commit, and a local cluster (`scripts/local-cluster/up.sh <project>`, about a minute; the deployer starts it if missing). Docker or Colima must be running.

## What you will be asked

Nothing about the design. The deployer asks only if the pull request has no `Post-deploy check:`, or before adding anything that would be a new service.

## Output files

The running pods; a deploy commit on the local git server (your branch is never touched); the evidence lines in the report (tag, commit, what was checked); on a failure, the failing check in `STATE.md ▶ LEFT BEHIND` and the slice's hand-off file.

## Checks and gate

`scripts/deploy_local.sh <project>` builds each selected app (all by default) with a unique tag, syncs the apps in order (database first; the API's migration runs first as an Argo CD PreSync job), then checks that every pod runs the new tag, is Ready and has not restarted, that `/healthz` and `/readyz` answer through the Gateway, and that the pull request's post-deploy check lines pass. Only then does the deployer report `verified (local)`. Anything else is `NOT verified`, with the rollback command (`--revision <earlier commit> --no-build`).

## Staging and production

After step 12 a cloud promotion is a pull request that bumps the image digest. Before it merges, `scripts/release_check.py --sha <merge sha>` proves a green CI run exists for the commit, the squash message has no skip-CI marker, and the digest bump was written. A person merges and syncs; the deployer never touches a cloud cluster.

## What local cannot prove

Real DNS and TLS, the tunnel, cloud IAM and vault, multi-node failure, real load, real webhooks. `verified (local)` never means `verified (cloud)`.

## Who approves

The checks decide `verified (local)`; you approve moving on to the retro.

## Hand-off

`STATE.md` is set to `STEP: 11 — Learn`.

Next: [step 11](11-learn.md), learn (what to keep, what to change, one place per new rule).
