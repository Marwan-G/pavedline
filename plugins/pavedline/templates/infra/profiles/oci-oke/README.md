# OCI / OKE profile

Plain HCL for Oracle Cloud: a Kubernetes cluster on arm64 Ampere nodes, its network, IAM, a versioned backup bucket, a
budget alarm and a vault whose secrets feed Kubernetes. Both `tofu` (OpenTofu, MPL-2.0) and `terraform` accept it;
Pavedline's CI validates it with OpenTofu. Terraform is under the Business Source License (not open source): see
`SOURCES.md` for the licence file URL and date.

**Nothing here is applied by the agent.** Every command below that touches the cloud is the founder's, from the
founder's own machine.

## What it creates

- VCN with a public API subnet (API reachable only from `api_allowed_cidrs`) and a private workers subnet behind a NAT
  gateway plus a service gateway. No load balancer and no public worker address: ingress is a Cloudflare Tunnel that
  dials out. Pods use the Flannel overlay, so no pod subnet.
- OKE cluster, `BASIC_CLUSTER` by default (no per-cluster charge; the design needs none of the enhanced features).
  Switch with `cluster_type`.
- One node pool per `node_pools` entry on `VM.Standard.A1.Flex` (arm64). Labels use the pool's own
  `initial_node_labels`. The node pool resource has no taint argument, so taints are applied by the `kubernetes`
  provider (`kubernetes_node_taint`) in a second phase. No cloud-init, user data or node metadata scripts anywhere.
- IAM, only what has a consumer: a service policy for the backup bucket (lifecycle and key use), and a backup user,
  group and policy limited to that one bucket (CNPG's S3-compatible access). Workers get no vault access: the
  Kubernetes secrets are written by Tofu on your machine, not by pods.
- Object Storage backup bucket: versioning on, no public access, a lifecycle rule that deletes old versions after
  `backup_retention_days` and aborts stale multipart uploads.
- Budget with two alert rules: a forecast warning (80% by default) and an actual-spend alert at 100%.
- Vault, a software master key and secret shells. Each shell holds a placeholder and has
  `ignore_changes = [secret_content]`, so Terraform never overwrites what you place in the console. A
  `kubernetes_secret_v1` is fed from the secret's current version, so the vault stays authoritative.

## Founder steps, in order

1. **Authenticate.** `oci session authenticate --region <region> --profile-name <profile> --auth security_token`
   (a session lasts about an hour; `oci session refresh --profile <profile>` extends it).
2. **Initialise.** Copy `terraform.tfvars.example` to `terraform.tfvars`, fill it in, then `tofu init`
   (CI uses `-lockfile=readonly`). The committed `.terraform.lock.hcl` holds provider hashes from the OpenTofu registry
   for linux_amd64, linux_arm64 and darwin_arm64; Terraform users regenerate it for registry.terraform.io with
   `terraform providers lock -platform=...` and commit that instead.
3. **Plan.** `tofu plan -out=plan.out`
4. **Check the plan.** `tofu show -json plan.out | python3 plan_check.py` must print `0 to destroy, 0 replaced`.
   It is an allow-list: only create, update, read and no-op pass; anything else (delete, replace, forget, unknown) exits 1
   and a file that is not a plan exits 2. One exception, always printed as `allowed: taint of a removed node ...`: a
   lone delete of a `kubernetes_node_taint`. Taints are keyed by node, so when OKE removes or replaces a node its
   taint object goes with it; nothing else is touched. A replace of a taint still fails.
5. **Apply.** `tofu apply plan.out`, only after step 4 passes.

Second phase, after the nodes are Ready: set `enable_node_taints = true` (and `enable_cluster_resources = true` with
`k8s_secret_bindings` once the real vault values exist), then repeat steps 3 to 5. A node replaced later is untainted
until the next apply, so re-run the plan after any node cycle.

## State rules

- An applied plan shows `0 to destroy` and nothing replaced. Replacement counts, in either order.
- No `state rm`, `state mv`, `import` or hand edit of the state file.
- A removal is calculated item by item first (what disappears, what depends on it), never a blind destroy.
- Back up the state file before any targeted apply, and run targeted applies only when the plan shows exactly what
  you expect.
- `plan.out` and `*.tfstate*` can both hold secret values (the vault bundle once bindings are on). Both are
  git-ignored here; keep them off shared disks and delete `plan.out` after the apply.
- The backend is local on purpose. The state holds the vault bundle read for the Kubernetes secrets, so treat it as a
  secret: keep it off shared disks and out of git.

## Where each secret lives

- Real values: the OCI vault, placed by the founder in the console. Terraform only creates the shells.
- The backup user's S3 customer secret key: created by the founder in the console (shown once), then placed in the
  vault.
- The Kubernetes secrets: two ways, your choice per Secret.
  - **Bound through Terraform** (`k8s_secret_bindings`, one Secret may take several keys): the value is read from the
    vault and written to the cluster, so **a bound value passes through the Terraform state and `plan.out`** in
    plain text. Protect them: local backend only, state and plan files `chmod 600`, kept on an encrypted disk and
    off shared folders, backed up the same way, never committed, and `plan.out` deleted after the apply.
  - **By hand, outside Terraform**: leave the Secret out of the bindings and create it yourself, e.g.
    `kubectl create secret generic db-backup-s3 --namespace <ns> --from-literal=access-key-id=... --from-literal=secret-access-key=...`
    typed in your own terminal. The value then never touches the state.
  Deleting a bound Secret in the cluster is safe: the next apply recreates it.
- Nothing is in this repository: `terraform.tfvars` is git-ignored, only the example ships.

## Where the database runs

The `data` pool is labelled `workload=data` and tainted `workload=data:NoSchedule`. The database chart schedules
nowhere in particular by default, so set its `cluster.nodeSelector` and `cluster.tolerations` values (in
`values-<environment>.yaml`) to the pool:

```yaml
cluster:
  nodeSelector: {workload: data}
  tolerations: [{key: workload, operator: Equal, value: data, effect: NoSchedule}]
```

Without them the third instance of a three-instance cluster cannot start on the untainted app nodes (the required
anti-affinity leaves no room) and stays Pending.

## Budget alarm

`budget_amount` and `budget_alert_recipients` are required variables. The forecast rule warns at
`budget_forecast_threshold_percent` and the actual rule fires at 100% of the month. Alerts go to the recipients by
e-mail; set the amount to your own ceiling.
