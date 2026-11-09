---
name: gitops
description: How anything reaches a cluster in a Pavedline product - Git is the only path, Argo CD ApplicationSets reconcile (add-ons auto-sync, apps are synced manually), CI commits image tag bumps and never syncs, the deployer syncs the local cluster only, and the local loop uses the kind-git server. Use at step 6 (copying the infra templates), step 9 and 10 (a slice changes infra or deploys) and whenever someone asks who syncs what.
---

# gitops

Git is the only path to a cluster: Terraform, add-ons, apps, Helm values and image tags all change by a commit that a person reviews and merges. Argo CD reconciles the cluster to Git. Nobody runs `kubectl apply` or `helm upgrade` against a cloud cluster (spec §11.1).

## The layout (copied at step 6 from `templates/infra/k8s/`)

| Path in the product repo | What it holds |
|---|---|
| `infra/k8s/applicationsets/addons.yaml` | One Application per folder of `infra/k8s/addons/*`. Automated sync with prune and self-heal. |
| `infra/k8s/applicationsets/apps.yaml` | One Application per folder of `infra/k8s/apps/*`. **No `automated` block** and `preserveResourcesOnDeletion: true`. |
| `infra/k8s/addons/priority-classes/` | `app-critical` and `app-default` (never `globalDefault`); the base chart requires a `priorityClassName`. |
| `infra/k8s/addons/gateway/` | GatewayClass `envoy`, Gateway `shared` in namespace `gateway` (listener `http`), the EnvoyProxy settings. |
| `infra/k8s/addons/alerts/` | The three alerts (spec §11.11), a CronJob checker; ships `enabled: false`. (1) every URL in `checks.endpoints` answers 2xx; (2) the named ScheduledBackup's newest completed Backup is younger than `checks.backupMaxAge` and no newer one failed; (3) every CronJob in `checks.jobs` succeeded within its `maxLate` and its last Job did not fail. A failing check posts one JSON message to the notify URL, repeated only after `checks.repeatEvery`; all green pings the heartbeat URL (an external dead-man's switch). Both URLs live in the Secret `alerts-targets` (keys `NOTIFY_URL`, `HEARTBEAT_URL`), never in Git; `go-to-production` chooses the targets with the founder, asks before adding any monitoring service (spec §12.6), creates the Secret and sets `enabled: true`. Read-only RBAC on exactly the namespaces the checks name. |
| `infra/k8s/addons/README.md` | What an add-on folder is, and the reserved `observability/` slot (spec §12.5). |

`{{REPO_URL}}` and `{{REVISION}}` in both ApplicationSets, and `{{ENVIRONMENT}}` (`local`, `staging` or `production`) in the apps one, are placeholders that stay in Git: step 6 does not fill them, and you never commit filled values. `deploy_local.sh` renders them when it applies the ApplicationSets to the local cluster (the local git server, `main`, `local`); the cloud bootstrap (step 12) renders them for staging and production. `{{path}}` and `{{path.basename}}` are Argo CD's own and stay too.

An app folder under `infra/k8s/apps/<name>/` is a Helm chart (the API's depends on the base chart, see `helm-base-chart`; the database's is plain CloudNativePG manifests) with `values.yaml` plus `values-local.yaml`, `values-staging.yaml` and `values-production.yaml`. The apps ApplicationSet gives each Application `helm.valueFiles: values-{{ENVIRONMENT}}.yaml` (missing files ignored), so the Application for an environment reads its own file; never put an environment's hostname, replicas or image tag in the shared `values.yaml`. Production and staging use an image `digest`.

## Who syncs what

| Thing | Who changes Git | Who syncs |
|---|---|---|
| Add-ons (`addons/*`) | A pull request | Argo CD, automatically on merge; drift is healed |
| Apps (`apps/*`) | CI commits the tag bump to the environment's values file; a pull request for anything else | A person: a manual sync of that Application after the pull request merged, then the checks in `docs/production/`. Locally, `deploy_local.sh` makes the deploy commit and syncs, run by the deployer |
| Terraform | A pull request | A person runs `terraform apply` (the founder; an agent never does) |

CI builds images and commits the tag bump; it never syncs. The `deployer` agent deploys to the local cluster only and reports; for a cloud change it opens nothing and syncs nothing, and it never runs `kubectl apply` or `helm upgrade` against a cloud cluster. `preserveResourcesOnDeletion: true` means renaming or removing an app folder leaves the workloads and the database in place; deleting them is a separate, deliberate step.

## The local loop (kind-git, Ruling 4)

Local runs the same ApplicationSets against a local git server, so a deploy is rehearsed the way production runs it.

1. `scripts/local-cluster/up.sh <project>` (see `local-cluster`) starts the container `kind-git` (alpine, `git daemon`) and creates the bare repo `git://kind-git:9418/<project>.git`, readable from the cluster by that name.
2. Push the branch from the product repo: `scripts/local-cluster/push.sh <project> [<branch>]`. It force-pushes the branch to the server as `main`. The ApplicationSets' `{{REPO_URL}}` is `git://kind-git:9418/<project>.git` and `{{REVISION}}` is `main` on local.
3. Add-ons sync on their own; sync each app by hand: `kubectl --context kind-pavedline-<project> -n argocd patch application app-<name> --type merge -p '{"operation":{"sync":{"revision":"main"}}}'`.
4. Verify the running pods, never the `Synced` label.
5. On a first sync of a new product the API's migration Job can fail because the database Cluster is not Ready yet (the Job retries about six times). If it does, wait for the Cluster to be Ready, then sync again: the failed Job is recreated by the hook.

**Why push is host-only.** Argo CD auto-syncs add-ons from this repo with prune and self-heal, so whoever can push to it controls the cluster. The daemon is therefore read-only (no receive-pack) and publishes no host port, so a pod on the kind network can read the repo but never write it; `push.sh` writes through `docker exec` into the container, which only this machine can do. The server is a local tool, not a service, and is removed by `down.sh <project> --all`. Argo CD synced over `git://` on 2026-11-09, so no HTTP server is needed.

## CI that writes to main

The image workflow's tag-bump job pushes the new digest to `main` as the GitHub Actions bot (spec §11.1). With a protected `main` this needs a **ruleset bypass for GitHub Actions** on `main`: a founder step, so add it to `WAITING.md` at step 6 (GitHub, Settings, Rules, the `main` ruleset, Bypass list). The bump uses `GITHUB_TOKEN`, which triggers no workflow, so the bump commit has no CI run of its own by design (no loop; the digest it records was built and scanned by the run that made it, and is deployed by the sync, not by CI). Required status checks: use only checks that run on every pull request (records, security, `ci-api`, `ci-web`, `ci-site`); never mark `ci-mobile` as a required check, because it is path-filtered and a pull request that touches no mobile file would wait for it forever.

## Rules

- A change to what runs in a cluster is a commit. If you catch yourself about to run a mutating `kubectl` or `helm` command, the answer is a pull request; only `kind-pavedline-*` contexts are free to change by hand (a hook blocks the rest).
- Never add an `automated` block to `apps.yaml`, and never remove `preserveResourcesOnDeletion`.
- Pin every version exactly (images by digest, charts by version and digest); the facts and dates are in `references/sources.md`.
- A new add-on is a service: ask before adding it (spec §12.6).
