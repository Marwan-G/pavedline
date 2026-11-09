# Bring-your-own-Kubernetes profile (the default)

Install Pavedline's platform layer onto **any conformant Kubernetes cluster with Gateway API support** that you already
have: a kubeconfig context, the Argo CD bootstrap and the add-ons. Ingress is a Cloudflare Tunnel (no load balancer, no
inbound port) in front of an Envoy Gateway `Gateway`. Teleport is optional and is not installed here.

**The agent never runs this with `--yes` against your cluster.** The cluster guard hook blocks every mutating
command outside `kind-pavedline-*`; the agent runs `bootstrap.sh` only in its printing form and shows you the plan.
Everything below that changes your cluster, your Cloudflare account or your vault is **yours**, from your own terminal.

## Prerequisites

- A conformant cluster (a currently supported Kubernetes version, inside the range Envoy Gateway's compatibility matrix lists; arm64 and
  amd64 nodes both work, every image is a multi-arch index), reachable through a kubeconfig **context** you name explicitly.
- **cluster-admin for the bootstrap only.** It installs CRDs, cluster roles and operators. Afterwards day-to-day work
  needs no cluster-admin; the product syncs through Argo CD.
- On your machine: `kubectl`, `helm` at or above `HELM_MIN_VERSION` in `versions.env`, `curl`, `sed`, and `sha256sum` or `shasum`.
- A Git repository for the product that Argo CD can read (an HTTPS URL; add a read-only credential in Argo CD if it is
  private). Add-ons live in `infra/k8s/addons/`, apps in `infra/k8s/apps/`.
- A Cloudflare account with the domain, for the tunnel (founder step; a new account or plan is ask-before-adding at
  step 12).

## What `bootstrap.sh` installs

Every version and digest comes from `scripts/local-cluster/versions.env`, the single pins file (nothing is pinned a
second time here): the Gateway API standard CRDs (sha256-checked), Envoy Gateway, cert-manager (with its CRDs), the
CloudNativePG operator, the Barman Cloud plugin in `cnpg-system` (manifest sha256-checked, images moved to digests)
and Argo CD; then the two ApplicationSets with the repository URL, the revision and the environment filled in from the
flags. After that Argo CD syncs the add-ons itself (the shared Gateway, the priority classes, the alerts checker).

## The founder steps, in order

1. **Look at the plan.** It prints every command and runs nothing:
   `bootstrap.sh --context <your-context> --repo-url <https-url> --revision <branch-or-sha> --environment staging`
2. **Run it** in your own terminal: the same command plus `--yes`. Staging first; then `--environment production` on the
   production cluster (a `kind-*` context is refused for production unless `--allow-kind`, which only the CI proof uses).
3. **Put the secrets in your vault, then create the Secrets** (never in Git, never in chat):

   | Secret (namespace) | Keys | Used by |
   |---|---|---|
   | `db-backup-s3` (the product namespace) | `access-key-id`, `secret-access-key` | the Barman Cloud plugin: backups of the database |
   | `alerts-targets` (`alerts`) | `NOTIFY_URL`, `HEARTBEAT_URL` | the three-alerts checker |
   | `cloudflared-token` (`cloudflared`) | `token` | the tunnel connector |
   | provider keys (email, payments, push, ...) | per `INFRA.md` | the product's own charts |

   Example: `kubectl --context <ctx> -n cloudflared create secret generic cloudflared-token --from-file=token=<(vault read ...)`
   so the value never appears in your shell history.
4. **The tunnel.** In the Cloudflare dashboard (Zero Trust, Networks, Tunnels) create a **named tunnel**, copy its token
   into the vault, and add a **public hostname** per environment hostname whose service is the Envoy Gateway proxy
   Service: find it with
   `kubectl --context <ctx> -n envoy-gateway-system get svc -l gateway.envoyproxy.io/owning-gateway-name=shared`
   and use `http://<that service>.envoy-gateway-system.svc.cluster.local:80`. Cloudflare creates the DNS record for the
   hostname. Then run the connector: `bootstrap.sh ... --tunnel --yes`, or
   `kubectl --context <ctx> apply -f cloudflared/namespace.yaml` and the rendered `cloudflared/deployment.yaml`
   (replace `@CLOUDFLARED_IMAGE@` with the pin in `versions.env`).
5. **Enable the alerts** (`alerts` add-on ships `enabled: false`) by setting `enabled: true` in `infra/k8s/addons/alerts/values.yaml` once `alerts-targets`
   exists, and run the restore drill (`restore_drill.sh --cloud-context <ctx> --yes-i-am-the-founder` prints it).

`cloudflared/` has no Service at all: the connector only dials out. No manifest in this profile creates a
`LoadBalancer`.

## Rotation and break-glass

Where each secret rotates and the break-glass path (how to reach the cluster and the database if Argo CD or the
tunnel is down) are written in the product's `RUN.md`, sections "Secret rotation" and "Break-glass"; this profile adds no second copy. A rotated value is changed in the vault first, then the Kubernetes Secret is
re-created from it; pods pick it up on restart.

## Teleport (optional)

Teleport is an optional way to reach the cluster and database without a public API address. It is not installed by this
profile and nothing here depends on it; if you use it, name its kube context in `--context` like any other.

## Proof

`scripts/profile_check.sh` in the Pavedline repository bootstraps a second kind cluster (`kind-pavedline-byo`) with this
script (`--allow-kind`) and waits until Argo CD reports the add-ons Healthy and the ApplicationSets have generated
their Applications. CI runs it weekly and on every change to this profile.
