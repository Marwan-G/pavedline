# Base chart values (keys an app chart sets)

Top level: `priorityClassName` (required) · `gateway: {name, namespace, sectionName}` (name required when any route is on) · `workloads.<name>`.

Per workload (`workloads.<name>`); `image`, `probes` and `resources` are required:

| Key | Meaning |
|---|---|
| `image.repository`, `image.tag` or `image.digest` (`sha256:<64 hex>`), `image.pullPolicy` | tag or digest required; `latest` refused |
| `port` (default 8000), `servicePort` (default 80) | container port named `http`; Service port |
| `replicas` (default 1) | ignored when `autoscaling.enabled` |
| `command`, `args`, `env` (map), `envFromSecrets` (list of Secret names), `secretEnv` (list of `{name, secretName, key}`), `podAnnotations` | |
| `extraEmptyDirs` (list of `{name, mountPath, sizeLimit}`) | extra writable emptyDir mounts; the root filesystem is read-only |
| `runAsUser` (default 10001), `tmpSizeLimit` (default 64Mi) | |
| `probes.liveness`, `probes.readiness`: `{path, initialDelaySeconds, periodSeconds, timeoutSeconds, failureThreshold}` | HTTP GET on port `http` |
| `resources.requests`, `resources.limits`: `{cpu, memory}` | both required |
| `pdb.minAvailable` or `pdb.maxUnavailable` (default maxUnavailable 1) | |
| `autoscaling: {enabled, minReplicas, maxReplicas, targetCPUUtilizationPercentage}` | HPA only when enabled |
| `networkPolicy.ingress`, `networkPolicy.egress` | raw NetworkPolicy rules appended to deny-all; DNS egress is automatic |
| `route: {enabled, hostnames, pathPrefix}` | HTTPRoute to the gateway |
| `migrations: {enabled, command, args, databaseUrlSecret: {name, key}, databaseUrlEnv, env, backoffLimit, resources}` | PreSync Job; its egress uses `networkPolicy.egress` |

The migration pod carries `app.kubernetes.io/name: <workload>-migrate`, so the workload's Service and PDB never select it.

Resource names are `<release>-<workload>`; the migration Job, ServiceAccount and NetworkPolicy end in `-migrate`.
