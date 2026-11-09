# Cluster add-ons

Every folder here is one add-on. The `addons` ApplicationSet creates an Argo CD Application per folder, and add-ons
**sync automatically** (prune and self-heal). Put in a folder only plain manifests or a Kustomization; the folder name
is the Application name (`addon-<folder>`) and the namespace objects land in.

| Folder | What it is |
|---|---|
| `priority-classes/` | `app-critical` and `app-default`; the base chart requires a `priorityClassName`. Never `globalDefault`. |
| `gateway/` | GatewayClass `envoy`, the `shared` Gateway (namespace `gateway`, listener `http`) and its EnvoyProxy settings. The controller (Envoy Gateway) and the Gateway API CRDs are installed before Argo CD syncs this: by `local-cluster/up.sh` locally, by Terraform or the cluster bootstrap in the cloud. |

Namespaces that may attach routes to the shared Gateway carry the label `gateway-access: shared`.

## Reserved: observability (spec §12.5)

The folder `observability/` is **reserved** for a future observability agent (metrics, logs, traces, alerts). Nothing
is installed there today and nothing may depend on it. When an agent adds it, it follows the same rules as any other
service: ask first (spec §12.6), pin by version and digest, one folder, auto-synced, and documented in `docs/extending.md`.
