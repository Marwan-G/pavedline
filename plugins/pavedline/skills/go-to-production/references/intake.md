# Infra intake (step 12), in order

Each area: what it decides, the options, the recommended default. One ADR per answer. Never re-ask what a decision already answers.

1. **Cloud account and provider.** Default: bring your own Kubernetes (any conformant cluster with Gateway API); OCI/OKE when the founder has or wants an OCI account (the agent never creates one).
2. **Existing cluster or a new one.** Default: existing if there is one (a kubeconfig context); a new one through the OCI profile otherwise.
3. **Regions.** One region plus a backup copy elsewhere.
4. **Domain and DNS.** Who holds the zone; Cloudflare Tunnel as ingress by default (no load balancer, no inbound ports).
5. **Container registry.** Default: the registry the CI already pushes to.
6. **Secrets store.** The vault is authoritative; secrets are placed by the founder.
7. **Object storage.** S3-compatible, with versioning and lifecycle rules; the backup bucket.
8. **Managed database (if chosen).** Default: CloudNativePG in the cluster with the Barman Cloud backup plugin.
9. **Email domain.** SPF, DKIM and DMARC, bounce and complaint handling.
10. **Budget ceiling.** A cloud budget alarm ships with the profile. Never design to a vendor's free tier.

Ask before adding any service (a monitor, a registry, a vault, an email provider): what it is, what it does, why nothing in use does it, its verified cost.
