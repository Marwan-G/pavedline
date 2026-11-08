# Threat areas

For each area: the threats to consider, the mitigation to choose, and where it can be enforced. Options with a recommended default; the founder decides.

## Assets and trust boundaries
List assets (tenant data, credentials, files, payment or personal data, signing keys) and boundaries (browser, edge, API, worker, database, third parties). Enforced: the diagram.

## Tenancy
Cross-tenant read or write; tenant id taken from a client field; a job or webhook running without a tenant; a storage key without the tenant prefix; support access beyond its grant. Enforced: forced row-level security and policies in `SCHEMA.md`, the verified-token rule in `openapi.yaml`, `SET LOCAL` per request and job, the leak-test fixture (step 9), `TENANCY-LIFECYCLE.md` support-access stage.

## Auth
Credential stuffing and sign-up abuse; session theft and fixation; privilege escalation between roles and scopes; the web app proxy acting beyond a pass-through; account takeover through recovery. Enforced: `AUTH.md`, scopes per operation, edge limits, the frontend boundary check.

## Secrets
Secrets in Git, images or logs; over-broad service accounts; unrotated keys; signing material for mobile builds. Enforced: secret store to Kubernetes Secret path in `DEPLOYMENT.md`, secret scanning in CI, a dedicated least-privilege service account per workload, rotation owners in `SERVICES.md`.

## Uploads
Malware, oversized files, wrong content types, path traversal, one tenant reading another's file, hostile image processing. Enforced: size and type allow-list in `openapi.yaml`, scanning step, tenant-prefixed keys, signed URLs issued after the tenant check, processing in a restricted worker.

## Webhooks
Forged or replayed inbound events; outbound events to internal addresses (server-side request forgery); duplicate delivery; payload leaking another tenant's data. Enforced: signature verification before any work, event-id idempotency, replay window, outbound destination allow-list and egress NetworkPolicy, per-tenant payloads.

## Compliance (only when decision 0003 is yes)
Sensitive records read without a trace; data kept past retention; data leaving the allowed region; a vendor without a processor agreement. Enforced: field-level encryption and access logging from step 4, retention jobs, residency in `DEPLOYMENT.md`, the vendor list in `SERVICES.md`. When decision 0003 is no, write "not applicable (decision 0003)".

## Abuse and availability
Request floods, expensive queries, queue backlog, noisy tenants. Enforced: edge limits, per-tenant quotas, pagination maxima, Pod disruption budgets and resource limits in `DEPLOYMENT.md`.

## Supply chain and CI
Poisoned dependency, compromised CI token, unpinned actions or images. Enforced: pinned versions, dependency update review, least-privilege CI tokens, image scanning (a new tool: ask before adding).
