---
name: local-cluster
description: Create, verify and destroy the local kind Kubernetes cluster (Argo CD, CloudNativePG, a local image registry) where every wave is deployed and verified before any cloud exists. Use at step 10 (deploy to local), when a wave needs a cluster, and when a cluster must be torn down.
---

# local-cluster

Every product built with Pavedline is deployed and verified on a local kind cluster through Argo CD before any cloud exists. Apple Silicon is arm64, like the production nodes, so images run unchanged.

## When to use

- Step 10 of the flow (deploy to local), and any wave that must be verified (local).
- Trying a chart, a migration or an Argo CD sync without touching a real cluster.

## Prerequisites

- A container runtime that answers `docker info`. On macOS, Colima works: `colima start --cpu 4 --memory 10`.
- The machine needs 16 GB of memory at minimum; 32 GB is recommended.
- `kind`, `kubectl`, `helm` and `docker` on the PATH. If any is missing, run `/pavedline:doctor` and tell the user what is missing. Never install software without the user's go.

## The three commands

Run from the plugin's `scripts/local-cluster/` directory. `<project>` is a lowercase DNS label.

| Command | What it does |
|---|---|
| `up.sh <project>` | Starts the `kind-registry` container on `127.0.0.1:5001`, creates cluster `pavedline-<project>` (host ports 8080 to 80 and 8443 to 443), installs Argo CD and the CloudNativePG operator at the pinned versions in `versions.env`. |
| `verify.sh <project>` | Checks `argocd-server` and the CloudNativePG controller are Available, applies a 1-instance Postgres `Cluster/smoke`, waits for it to be Ready, deletes it. Exit 0 only if all pass. |
| `down.sh <project> [--all]` | Deletes `pavedline-<project>` only. `--all` also removes the `kind-registry` container. |

Push images to `localhost:5001/<name>:<unique-tag>`; the cluster pulls them from the same address. Never reuse a tag.

## Safety

The kube context is `kind-pavedline-<project>`. On `kind-pavedline-*` contexts and only there, you may apply, change and destroy freely. Pass `--context` (kubectl) or `--kube-context` (helm) on every command. A hook blocks every mutating `kubectl`, `helm` or `argocd` command on any other context. Never touch another cluster.

## Teardown

Run `down.sh <project>` at the end of a wave unless the user wants the cluster kept; add `--all` when no other project needs the registry.

## What local cannot prove

Local cannot prove real DNS and TLS, the tunnel, cloud IAM and vault, multi-node failure, real load and real webhooks. The integration wave covers webhooks; step 12 (go to production) covers the rest. Never claim "verified (cloud)" from a local run.
