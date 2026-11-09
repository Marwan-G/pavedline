# Environments and vocabulary

Pavedline uses these words with one meaning each.

| Term | Meaning |
|---|---|
| **local** | the kind cluster on your machine. Every wave deploys and is verified here, through Argo CD |
| **staging** | the cloud staging environment, created at step 12 with an infra profile (bring your own Kubernetes, or OCI/OKE) before production. Generated data only; never indexable |
| **production** | the live cloud environment, promoted by pull request from a verified staging SHA (`promote.py`) |
| **verified (local)** | migrations applied, Argo CD synced, pods running the release SHA with 0 restarts, health endpoints OK, the slice's acceptance tests passing against the cluster |
| **verified (cloud)** | verified (local) plus what local cannot prove: real DNS and TLS, the tunnel or ingress, cloud IAM and vault, a backup and a real restore, the three alerts fired in a test, email deliverability |
| **wave** | a planned group of slices that ends with deploy and learn |
| **slice** | the smallest change with its own tests, review gates and pull request |
| **feature-complete** | every acceptance test in `docs/spec/SPEC.md` mapped to a merged slice and passing on local. An integration wave follows it, before step 12 |

**Local** runs on your machine from step 6 on. **Staging** and **production** are created once, at step 12, from an
infra profile (bring your own Kubernetes, or OCI/OKE); production is promoted from the verified staging SHA by pull request.

## The local cluster

The scripts create a kind cluster named `pavedline-<project>` (kube context `kind-pavedline-<project>`), a local image
registry, Argo CD and the CloudNativePG operator, at pinned versions. `verify.sh` checks the add-ons are running and
that a one-instance Postgres comes up. `down.sh` removes everything. They are run by you or by Claude with your
go; a hook blocks mutating `kubectl`, `helm` and `argocd` commands whose context is not `kind-pavedline-*`.

Apple Silicon is arm64, like common cloud arm64 nodes, so images built locally run unchanged there. You need a
container runtime, 16 GB of memory at minimum (32 GB recommended), `kind`, `kubectl` and `helm`;
`/pavedline:doctor` checks them.

## What local cannot prove

- real DNS and TLS, and the tunnel or ingress in front of the cluster
- cloud IAM and the secret vault
- multi-node failure and real load
- real webhooks from outside your machine
- email deliverability

Those are proven in the cloud, at the end of the flow, before anything is called verified (cloud).
