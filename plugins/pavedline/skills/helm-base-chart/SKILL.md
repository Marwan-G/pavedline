---
name: helm-base-chart
description: Use the Pavedline Helm base chart (a library chart) to deploy any workload with the same hardening - probes, requests and limits, a PodDisruptionBudget, topology spread, non-root read-only containers, a ServiceAccount per workload, default-deny NetworkPolicy, a priority class, a Gateway API route and a PreSync migration Job. Use at step 6 (the chart is copied into the product repo) and step 9 (a slice adds or changes an app chart), and when testing a chart.
---

# helm-base-chart

Every workload in a product is deployed by one library chart, `infra/helm/base-chart/`, so safe defaults live in one place and an app chart is only values. The chart enforces the rules of spec §11.2; a slice never weakens them in an app chart.

## What the chart enforces, and why

| Rule | Why |
|---|---|
| Liveness and readiness probes (required) | Traffic only reaches ready pods; stuck pods restart. |
| Resource requests and limits (required) | The scheduler can place pods; one pod cannot starve the node. |
| PodDisruptionBudget (default: one pod may be down) | A node drain cannot take every replica at once. |
| HorizontalPodAutoscaler only when `autoscaling.enabled` | Scaling is a choice, and replicas are then left to the HPA. |
| Topology spread over nodes and zones (`ScheduleAnyway`, a soft rule) | One node or zone failing does not take the service down; soft, so a small or single-zone cluster still schedules. |
| Non-root, read-only root filesystem, no privilege escalation, all capabilities dropped, seccomp RuntimeDefault, a writable `/tmp` emptyDir | A compromised container has almost nothing to work with. |
| One ServiceAccount per workload, token not mounted | Least privilege; a workload gets API access only if you add it. |
| NetworkPolicy deny-all (ingress and egress), DNS egress always allowed, other allows from values | Traffic exists only where someone wrote it down. |
| `priorityClassName` (required) | Under pressure the cluster evicts the least important pods first. |
| Image: repository plus `tag` or `digest` (required, `latest` refused); staging and production use `digest` | A deploy is always a known build. CI writes the digest in the tag-bump commit. |
| Secrets by name only (`envFromSecrets`, `secretEnv`) | The chart never creates a Secret and values files never hold one. |

## How an app chart uses it

1. Copy `infra/helm/example-app` shape: `Chart.yaml` with a `file://` dependency on the base chart, one template file containing `{{ include "base.render" . }}`, and `values.schema.json`.
2. `values.schema.json` is a copy of `base-chart/app-values.schema.json`. A library chart cannot validate its parent's values, so the schema lives in each app chart; never edit the copy, edit the original and recopy.
3. Describe each workload under `workloads.<name>` in `values.yaml`; the keys are listed in `references/values.md`.
4. Per-environment files `values-local.yaml`, `values-staging.yaml`, `values-production.yaml` override the shared `values.yaml` (replicas, resources, hostnames, autoscaling, image tag). CI bumps `image.tag` in them; never use `latest`.
5. Routing: set `gateway.name` once and `route.enabled` plus `route.hostnames` per workload. The chart emits a Gateway API `HTTPRoute` (ingress-nginx is retired, so there is no Ingress). Allow the gateway in through `networkPolicy.ingress`; the allow must name the namespace the Gateway's data-plane pods run in, and an HTTPRoute in another namespace than the Gateway needs the Gateway's `allowedRoutes` to permit it.
7. The root filesystem is read-only and only `/tmp` is writable. For anything else (Next.js `.next/cache`, tool caches) add `extraEmptyDirs: [{name, mountPath, sizeLimit}]`; for Python set `PYTHONDONTWRITEBYTECODE=1` and `HOME`/`XDG_CACHE_HOME=/tmp`.
8. `kubectl` and `helm` writes only ever target a `kind-pavedline-*` context; production changes go through Git and Argo CD.

## Migrations and the expand/contract rule (spec §11.4)

With `migrations.enabled`, the chart renders a Job that Argo CD runs as a PreSync hook, before the new pods start. It uses the same image, its own ServiceAccount and NetworkPolicy, and reads the database owner URL from a Secret (`databaseUrlSecret`). The runtime role never owns tables, so the migration uses the owner role's Secret and the app uses the runtime one.

Because a Git revert does not undo a migration, every release must run against the previous image too: a release only adds (expand); removals ship in a later release once nothing uses the old shape (contract). Every migration has a tested down path, rehearsed on local.

## How to test a chart

Run these from the app chart's directory after `helm dependency update`:

- `helm lint . -f values-<env>.yaml` for each of the three environments.
- `helm template rel . --namespace <ns> -f values-<env>.yaml` for each environment (every object carries the release namespace); read the output, it is the truth.
- The schema test: render without `image.tag` and expect a failure.
- Checkov on the rendered output: `helm template rel . -f values-production.yaml | checkov -f - --framework kubernetes` with `--config-file infra/helm/.checkov.yaml` (pinned version in `references/sources.md`; CI runs it).
- The deploy is only proven by step 10 on the local cluster; see the `local-cluster` skill.

Do not commit the generated `charts/` directory.

## Rules

- A finding from Checkov is fixed in the base chart, or skipped in `infra/helm/.checkov.yaml` with a one-line reason; every skip is listed to the reviewer, never suppressed silently.
- Asking before adding a service (spec §12.6) applies to anything an app chart would pull in, such as a database operator or a message broker.
- Vendor facts and pinned versions: `references/sources.md`.
