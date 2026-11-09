# Infra

What binds the portable decisions to real infrastructure. Written at step 12 from the intake; one ADR per answer
(`decisions/NNNN`). Placeholders only: never a secret, an account id or a key.

| Area | Answer | ADR |
|---|---|---|
| Cloud account and provider | | |
| Cluster (existing or new) | | |
| Regions | | |
| Domain and DNS | | |
| Container registry | | |
| Secrets store | | |
| Object storage | | |
| Managed database | | |
| Email domain | | |
| Budget ceiling | | |

## Profile

`byo-kubernetes` | `oci-oke`, and where its filled variables live.

## Where each secret lives

Name · vault path · owner · rotation (never the value). The full list is in `SERVICES.md`.
