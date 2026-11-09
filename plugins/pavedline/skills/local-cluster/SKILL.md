---
name: local-cluster
description: Create, verify and destroy the local kind Kubernetes cluster (Argo CD, CloudNativePG, Envoy Gateway, a local image registry, a local git server) where every wave is deployed and verified before any cloud exists. Use at step 10 (deploy to local), when a wave needs a cluster, and when a cluster must be torn down.
---

# local-cluster

Every product built with Pavedline is deployed and verified on a local kind cluster through Argo CD before any cloud exists. Apple Silicon is arm64, like the production nodes, so images run unchanged.

## When to use

- Step 10 of the flow (deploy to local), and any wave that must be verified (local).
- Trying a chart, a migration or an Argo CD sync without touching a real cluster.

## Prerequisites

- A container runtime that answers `docker info`. On macOS, Colima works: `colima start --cpu 4 --memory 10`.
- The machine needs 16 GB of memory at minimum; 32 GB is recommended.
- `kind`, `kubectl`, `helm` and `docker` on the PATH. If any is missing, run `/pavedline:doctor` and follow its install rule: tell the user what it will install, why and the exact command, then install it (permission prompt, no `sudo`; a refusal goes to `WAITING.md`).

## The three commands

Run from the plugin's `scripts/local-cluster/` directory. `<project>` is a lowercase DNS label.

| Command | What it does |
|---|---|
| `up.sh <project>` | Starts the `kind-registry` container on `127.0.0.1:5001`, creates cluster `pavedline-<project>` (host port 8080 reaches the Envoy Gateway proxy through NodePort 30080), installs Argo CD, the CloudNativePG operator, the Gateway API CRDs and Envoy Gateway at the pinned versions in `versions.env`, then builds and starts the `kind-git` container with a bare repo for the project; it refuses a reused cluster made by an older Pavedline. |
| `push.sh <project> [<branch>\|<commit-sha>]` | Run inside the product repo: pushes the branch, or a commit given by its sha (the deploy script's deploy commit), to `kind-git` as `main` (see the `gitops` skill). The only way to write to the server. |
| `verify.sh <project>` | Checks `argocd-server`, the CloudNativePG controller and Envoy Gateway are Available; a 1-instance Postgres `Cluster/smoke` becomes Ready; the shared `Gateway` (from the template add-ons) is `Programmed` and an `HTTPRoute` answers on `http://127.0.0.1:8080/`; an Argo CD Application syncs a ConfigMap from `kind-git`. Cleans up after itself. Exit 0 only if all pass. |
| `down.sh <project> [--all]` | Deletes `pavedline-<project>` only. `--all` also removes the `kind-registry` and `kind-git` containers. |

Push images to `localhost:5001/<name>:<unique-tag>`; the cluster pulls them from the same address. Never reuse a tag.

## Gateway and git server

- **Routing:** Envoy Gateway (Apache-2.0) is the Gateway API controller. The `gateway` add-on in `templates/infra/k8s/addons/gateway/` defines GatewayClass `envoy` and Gateway `shared` (namespace `gateway`, listener `http`); its proxy Service is a NodePort, so `curl http://127.0.0.1:8080/` reaches an `HTTPRoute`. A namespace attaches routes only with the label `gateway-access: shared`. No port-forward is needed.
- **Git:** the `kind-git` container (alpine, `git daemon`, port 9418) serves `git://kind-git:9418/<project>.git` to the cluster, **read-only**. Argo CD syncs add-ons from that repo with prune and self-heal, so a push there is control of the cluster: a writable daemon would let any pod on the kind network take it over. The daemon therefore has no receive-pack and publishes no host port; `push.sh` writes to it from this machine only, through `docker exec` (git's `ext::` transport, enabled for that one command). The `gitops` skill has the loop.
- **Local only, by design.** The registry (`kind-registry`, no authentication) and the read-only git daemon (`kind-git`) are reachable from every pod in the local cluster. That is fine for a disposable cluster on `127.0.0.1`; never reuse them outside kind, and never put a secret in an image or a repo they serve.
- A cluster made before this layout (host port 8080 mapped to 80) is refused by `up.sh`: run `down.sh <project>` then `up.sh <project>`.

## Safety

The kube context is `kind-pavedline-<project>`. On `kind-pavedline-*` contexts and only there, you may apply, change and destroy freely. Pass `--context` (kubectl) or `--kube-context` (helm) on every command. A hook blocks every mutating `kubectl`, `helm` or `argocd` command on any other context. Never touch another cluster.

## Teardown

Run `down.sh <project>` at the end of a wave unless the user wants the cluster kept; add `--all` when no other project needs the registry and the git server.

## What local cannot prove

Local cannot prove real DNS and TLS, the tunnel, cloud IAM and vault, multi-node failure, real load and real webhooks. The integration wave covers webhooks; step 12 (go to production) covers the rest. Never claim "verified (cloud)" from a local run.
