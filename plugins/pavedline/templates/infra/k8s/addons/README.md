# Cluster add-ons

Every folder here is one add-on. The `addons` ApplicationSet creates an Argo CD Application per folder, and add-ons
**sync automatically** (prune and self-heal). Put in a folder plain manifests, a Kustomization or a small Helm chart (Argo CD renders it with the chart's own `values.yaml`); the folder name
is the Application name (`addon-<folder>`) and the namespace objects land in.

| Folder | What it is |
|---|---|
| `priority-classes/` | `app-critical` and `app-default`; the base chart requires a `priorityClassName`. Never `globalDefault`. |
| `gateway/` | GatewayClass `envoy`, the `shared` Gateway (namespace `gateway`, listener `http`) and its EnvoyProxy settings. The controller (Envoy Gateway) and the Gateway API CRDs are installed before Argo CD syncs this: by `local-cluster/up.sh` locally, by Terraform or the cluster bootstrap in the cloud. |
| `alerts/` | The three alerts (spec §11.11) as one CronJob checker (Helm chart, **ships `enabled: false`**): (1) every public endpoint in `checks.endpoints` answers 2xx; (2) the named ScheduledBackup's newest completed Backup is younger than `checks.backupMaxAge` and none newer failed; (3) every CronJob in `checks.jobs` succeeded within its `maxLate` and its last Job did not fail. A failing check posts one JSON message to the notify URL (again only after `checks.repeatEvery`); all green pings the heartbeat URL, an external dead-man's switch. Both URLs live in the Secret named by `secretName` (`alerts-targets`, keys `NOTIFY_URL`, `HEARTBEAT_URL`), never in Git. Step 12 (`go-to-production`) chooses the targets with the founder, creates the Secret and sets `enabled: true`. |

Namespaces that may attach routes to the shared Gateway carry the label `gateway-access: shared`.

## Reserved: observability (spec §12.5)

The folder `observability/` is **reserved** for a future observability agent (metrics, logs, traces, alerts). Nothing
is installed there today and nothing may depend on it. When an agent adds it, it follows the same rules as any other
service: ask first (spec §12.6), pin by version and digest, one folder, auto-synced, and documented in `docs/extending.md`.
