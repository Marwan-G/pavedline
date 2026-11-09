# Sources and pins for fastapi-service

Checked 2026-11-09. Every pin is exact and at least two weeks old (published on or before 2026-10-26). `uv.lock` is resolved with `exclude-newer = "2026-10-26T00:00:00Z"`, so the transitive packages obey the same cutoff (checked: none of the 48 locked packages is newer). Re-check before bumping; these are facts at a date.

## Python packages (pyproject.toml, exact `==`)

| Pin | Published | URL |
|---|---|---|
| `fastapi==0.162.0` | 2026-10-23 | https://pypi.org/project/fastapi/0.162.0/ |
| `uvicorn==0.54.0` | 2026-09-25 | https://pypi.org/project/uvicorn/0.54.0/ |
| `pydantic==2.14.1` | 2026-10-11 | https://pypi.org/project/pydantic/2.14.1/ |
| `pydantic-settings==2.16.1` | 2026-10-20 | https://pypi.org/project/pydantic-settings/2.16.1/ |
| `sqlalchemy[asyncio]==2.1.6` (pulls `greenlet` 3.5.6, 2026-09-14, from the lock) | 2026-10-21 | https://pypi.org/project/SQLAlchemy/2.1.6/ |
| `alembic==1.20.1` | 2026-10-22 | https://pypi.org/project/alembic/1.20.1/ |
| `psycopg[binary]==3.3.6` (psycopg-binary 3.3.6) | 2026-09-18 | https://pypi.org/project/psycopg/3.3.6/ |
| `pyjwt[crypto]==2.15.1` (cryptography 50.0.2, 2026-09-30, from the lock) | 2026-09-28 | https://pypi.org/project/PyJWT/2.15.1/ |
| `pytest==9.1.1` (9.2.0 followed on 2026-10-27) | 2026-06-19 | https://pypi.org/project/pytest/9.1.1/ |
| `pytest-asyncio==1.4.1` | 2026-10-25 | https://pypi.org/project/pytest-asyncio/1.4.1/ |
| `httpx==0.28.1` (latest release) | 2024-12-06 | https://pypi.org/project/httpx/0.28.1/ |
| `ruff==0.17.2` | 2026-10-22 | https://pypi.org/project/ruff/0.17.2/ |
| `pyright==1.1.414` (the PyPI wrapper downloads the matching Node package on first run, so it needs network and Node access) | 2026-09-10 | https://pypi.org/project/pyright/1.1.414/ |
| `import-linter==2.15` | 2026-09-04 | https://pypi.org/project/import-linter/2.15/ |
| `pyyaml==6.0.3` (latest release; used by contract_check) | 2025-09-25 | https://pypi.org/project/PyYAML/6.0.3/ |

## Tool and images

| Pin | Value | URL / date |
|---|---|---|
| uv | `0.13.5` (PyPI 2026-10-22; 0.13.6 followed 2026-10-27); image `ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff` (OCI index digest) | https://pypi.org/project/uv/0.13.5/ , https://github.com/astral-sh/uv/releases (2026-11-09) |
| Python | `3.14.9`; image `python:3.14.9-slim@sha256:35caba83af2fe6da9a5d922f9b0156f21d1246a48278c58a08bd253303ba42e8` (Docker Hub index digest, tag pushed 2026-10-24; 3.14.10 was pushed 2026-11-08, under two weeks). `.python-version` holds `3.14`; the image digest fixes the patch. | https://hub.docker.com/_/python (2026-11-09) |
| PostgreSQL for the pack tests | `postgres:16.14@sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b` (Hub tag pushed 2026-08-05; 16.15 was pushed 2026-11-07, under two weeks). Run it locally and throw it away; never a cluster database. | https://hub.docker.com/_/postgres (2026-11-09) |

Run the throwaway server: `docker run -d --rm --name pg-test -p 127.0.0.1:55432:5432 -e POSTGRES_PASSWORD=<local-only> postgres:16.14@sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b`, then `DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:55432/postgres`.

## Facts relied on

| Fact | Source | Date |
|---|---|---|
| FastAPI 0.162 includes routers lazily (`_IncludedRouter`); the flat route list for coverage comes from `fastapi.routing.iter_route_contexts` | read from the installed 0.162.0 source | 2026-11-09 |
| `set_config(name, value, true)` is `SET LOCAL`: lasts to the end of the transaction | https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-ADMIN-SET | 2026-11-09 |
| `FORCE ROW LEVEL SECURITY` makes the owner subject to policies; BYPASSRLS roles and superusers always bypass | https://www.postgresql.org/docs/16/ddl-rowsecurity.html | 2026-11-09 |
| Clerk session token v2 (default since 2025-04-14) nests the organisation under `o` (`o.id`); v1 used a flat `org_id`. The default `AUTH_TENANT_CLAIM` is `o.id` | https://clerk.com/changelog/2025-04-14-session-token-jwt-v2 , https://clerk.com/docs/guides/sessions/session-tokens | 2026-11-09 (controller, on the web) |
| PyJWKClient caches the key set: 20 tokens with unknown `kid`s caused 2 fetches (the pack pins this with a counting fetcher: at most 2); a failed fetch raises `PyJWKClientConnectionError`, answered 503 | tested in `tests/test_auth.py` against PyJWT 2.15.1 | 2026-11-09 |
| Idempotency-Key semantics (same key and payload: original result; different payload: 422) | https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ (draft-08) | 2026-11-08 |

Still to confirm: the claim names on a decoded development token at the first auth slice (the claim path is configuration).

## Webhook signatures (Task 5, checked 2026-11-09)

| Fact | URL | Date |
|---|---|---|
| Svix (Clerk delivers through it): headers `svix-id` (same on resends), `svix-timestamp` (seconds), `svix-signature` (space-delimited `v1,<base64>` list); signed content `${svix_id}.${svix_timestamp}.${body}` on the raw body; secret `whsec_` + base64, the part after the prefix base64-decoded is the HMAC-SHA256 key; digest base64-encoded; compare in constant time; check the timestamp against the clock within a tolerance (the page names none; Svix's libraries use 5 minutes) | https://docs.svix.com/receiving/verifying-payloads/how-manual | 2026-11-09 |
| Stripe: `Stripe-Signature` has `t=<unix>` and one or more `v1=<hex>` (and `v0` for test; ignore every scheme but `v1`); `signed_payload` = timestamp, `.`, the raw JSON body; HMAC-SHA256 with the endpoint secret as the key; several `v1` while a rolled secret is kept (up to 24 h); libraries default to a 5 minute tolerance, never 0 | https://docs.stripe.com/webhooks#verify-manually | 2026-11-09 |
| Clerk webhooks are delivered and signed by Svix | https://clerk.com/docs/webhooks/overview | 2026-11-09 |
| Stripe CLI: `stripe listen --forward-to <url>` prints the signing secret `whsec_...` it uses; no tunnel needed | https://docs.stripe.com/stripe-cli/use-cli | 2026-11-09 |

## Database and deploy (Task 5b, checked 2026-11-09)

| Pin | Value | URL / date |
|---|---|---|
| PostgreSQL image | `ghcr.io/cloudnative-pg/postgresql:16.15-202610190958-standard-trixie@sha256:f105e137d731f6ac4f69667383f2373345ce8b72dadcc10ab6d385a7a32d6e7f` (multi-arch index: linux/amd64 and linux/arm64; arm64 image created 2026-10-19T10:03Z, 21 days old; newer 16.15 builds of 2026-10-26 and 2026-11-02 are under or near two weeks, and 16.15 is the newest 16.x) | https://github.com/cloudnative-pg/postgres-containers , registry tags list of ghcr.io/cloudnative-pg/postgresql (2026-11-09) |
| CloudNativePG operator | 1.30.1 (chart 0.29.1, pinned in `scripts/local-cluster/versions.env`). CRD fields used (`managed.roles[].passwordSecret/bypassrls/inherit`, `bootstrap.initdb.postInitApplicationSQLRefs`, `postgresql.synchronous.{method,number}`, `Pooler.spec.pgbouncer.poolMode`) were read with `kubectl explain` on the running operator and the staging and production renders pass `kubectl apply --dry-run=server`. | https://cloudnative-pg.io/docs/ , https://github.com/cloudnative-pg/cloudnative-pg/releases (2026-11-09) |
| Role Secrets | `kubernetes.io/basic-auth` (`username`, `password`), one per managed role; the owner Secret is also the initdb `secret`. | https://github.com/cloudnative-pg/cloudnative-pg/blob/main/docs/src/declarative_role_management.md |
| PgBouncer Pooler | `ghcr.io/cloudnative-pg/pgbouncer:1.26.1-202610221428-trixie@sha256:4bc1a2f2310e9ca5b3211e72edab97b1e1c2370c36961c253a279a341d5d2ee6` (multi-arch index: linux/amd64 and linux/arm64; build tag of 2026-10-22, 18 days old; the 1.26.1 builds of 2026-10-26 and later are under or near two weeks). Set as `pooler.image` in the postgres chart's `values.yaml` and rendered as the container named `pgbouncer` under `spec.template.spec.containers` (the operator requires that name). | https://github.com/cloudnative-pg/cloudnative-pg/blob/main/docs/src/connection_pooling.md , registry tags list of ghcr.io/cloudnative-pg/pgbouncer (2026-11-09) |
| PostgreSQL 18 image (pack alternative) | `ghcr.io/cloudnative-pg/postgresql:18.6-202610190957-standard-trixie@sha256:d72ace96f5803b12c341bb5dac48532e8c1f92f69e8a717a59d779bfc038dea9` (multi-arch index: linux/amd64 and linux/arm64; build tag of 2026-10-19, 21 days old; 18.6 is the newest 18.x, newer 18.6 builds of 2026-11-03 and 2026-11-09 are under two weeks). Listed in `pack.yaml` `postgres.majors`; `apply_stack.py --postgres-major 18` writes it. The API test database image follows the major (next row). | https://github.com/cloudnative-pg/postgres-containers , registry tags list of ghcr.io/cloudnative-pg/postgresql (2026-11-09) |
| PostgreSQL 18 test image (pack alternative) | `postgres:18.4@sha256:a02db8cac496f15b094798a38254f14d6e00741f709360e5e00bb6668ea31636` (official image, OCI index digest: linux/amd64 and linux/arm64; Hub tag pushed 2026-08-06, 95 days old; 18.6 was pushed 2026-11-06, under two weeks, so it is not used). Listed as `test` in `pack.yaml` `postgres.majors.18`; `apply_stack.py --postgres-major 18` writes it into `.github/workflows/ci-api.yml`. | https://hub.docker.com/_/postgres , https://hub.docker.com/v2/repositories/library/postgres/tags/18.4 (2026-11-09) |
| `localtest.me` | Resolves every subdomain to 127.0.0.1 (`api.localtest.me` checked 2026-11-09 with DNS). | https://readme.localtest.me/ |
