---
name: fastapi-service
description: Build and change the FastAPI service of a Pavedline product (services/api from the nextjs-fastapi stack pack) - layers, the three database roles, SET LOCAL tenant scoping, the verified-token tenant, Idempotency-Key, the error envelope, money without float, and the three checks (rls_check, contract_check, the cross-tenant leak registry). Use at step 6 (the pack is copied in) and in every step 9 slice that touches the API.
---

# fastapi-service

The API lives in `services/api` (a uv project, Python 3.14, FastAPI, Pydantic v2, SQLAlchemy async over psycopg 3, Alembic). The pack ships the mechanisms; a slice adds resources on top of them and never weakens them. Contract first: `docs/api/openapi.yaml` (step 5) is the source of truth; code follows it. Pinned versions and their sources: `${CLAUDE_SKILL_DIR}/references/sources.md`.

## Layout and layers (import-linter enforces it)

`app/main.py` (factory `create_app`, request id, error handlers) > `app/routes/` (HTTP: parse, auth, call a service, shape the reply) > `app/services/` (rules and SQL, no HTTP) > `app/db/` (engine, `tenant_transaction`). `app/auth.py`, `app/settings.py`, `app/errors.py` sit beside the layers; `app/auth.py` imports none of them. A new slice: `routes/v1/<name>.py`, `services/<name>.py`, one migration, one line in `routes/v1/__init__.py:build_router`. Run the checks from `services/api` (commands below).

## Rules (each is tested by the pack; do not remove a test to pass)

1. **Three roles, created by the platform** (`db/roles.sql`, idempotent; never by a migration). `app_owner` owns every table and runs migrations (`DATABASE_OWNER_URL`); `app_runtime` is what the service connects as (`DATABASE_URL`): owns nothing, no BYPASSRLS, cannot `SET ROLE app_owner`; `app_admin` is for audited reporting and has no grants until a decision gives it some.
2. **Every tenant table**: `tenant_id uuid NOT NULL REFERENCES tenants(id)`, `ENABLE` and `FORCE ROW LEVEL SECURITY`, a `tenant_isolation` policy with `USING` and `WITH CHECK` on `NULLIF(current_setting('app.tenant_id', true), '')::uuid`, an index led by `tenant_id`, and an explicit `GRANT` to `app_runtime`. Migrations are Alembic with explicit SQL (`op.execute`), never autogenerate, each with a working `downgrade`. A table with no tenant goes in `db/global_tables.txt` with a reason.
3. **SET LOCAL per unit of work.** Every request and every job runs in one `tenant_transaction(engine, tenant_id)` (it issues `set_config('app.tenant_id', $1, true)`). A cross-tenant job lists tenants with `list_tenant_ids` and runs one transaction per tenant. Never a session `SET`, never a session advisory lock (the pooler is in transaction mode), never a BYPASSRLS runtime role.
4. **The tenant comes from the verified token** (`CurrentPrincipal`): PyJWT and JWKS, RS256 or ES256 only; the tenant claim (`AUTH_TENANT_CLAIM`, default `o.id`: Clerk session token v2 nests the organisation under `o`; `org_id` is the v1 flat claim; a dotted path reaches nested claims) is mapped to our tenant id through `tenants.external_id`. No header, query or body field names a tenant. No token or a bad one is 401; a token without a known tenant is 403; another tenant's id is 404, like a missing one. In production the service refuses to start without `AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_JWKS_URL`. If the JWKS cannot be fetched the answer is 503 `auth_unavailable`, not 401. At the first auth slice, decode a real development token and confirm the claim path. Bodies over `MAX_BODY_BYTES` (1 MiB) are 413 before auth.
5. **Idempotency-Key** on every operation that creates or changes state: add `IdempotencyKey` (400 when missing) and wrap the work in `run_idempotent`. Same key and same fingerprint (method, path, body sha256) returns the stored response; same key with another fingerprint is 422 `idempotency_key_reuse`; keys live 24 hours under `(tenant_id, principal, key)`; the table is a tenant table under FORCE RLS. The fingerprint leaves out the query string on purpose. A scheduled job MUST call `purge_expired_idempotency_keys(engine)` (one SET LOCAL transaction per tenant), or the table grows without bound.
6. **One envelope.** Success `{"data": ...}` (lists add `next_cursor`); errors `{"error": {"code", "message", "request_id", "details"?}}`. Raise `ApiError(status, code, message)`; a database data error becomes 422 `invalid_value`, so also bound client numbers (`le=2**63-1` for bigint) and reject NUL in strings; never return ad-hoc error bodies, never leak internals (unhandled errors are a plain 500).
7. **Money is `int` minor units plus a currency code, or `Decimal`; never `float`.** No `float` in a model, a column or an annotation of a money field. Check: `rg -n '\bfloat\b|\bFloat\b|double precision|\breal\b' services/api/app services/api/migrations` must find nothing (a hit needs a written reason). Read large sums as text (`SUM(x)::text`).
8. **Fail closed.** `/healthz` (process only) and `/readyz` (database as `app_runtime`) are the only unauthenticated routes and are outside `/v1`; everything under `/v1` needs a token, and `security: []` is a decision.
9. The image runs non-root with a read-only root filesystem (only `/tmp` writable): write no files at runtime. The build runs `python -m app.boot_check` (no database), so a broken image fails the build.
10. **`X-Min-App-Version` on every response** (mobile minimum supported app version, spec 11.4): the pure-ASGI `MinAppVersionMiddleware` adds it from the setting `MIN_APP_VERSION` (plain `MAJOR.MINOR.PATCH`, default `0.0.0`, validated at start), errors and 413 included; tested in `tests/test_min_app_version.py`. Raise it only after the new app build is live in the stores.

## The three checks

| Check | Command (CI runs them) | Fails when |
|---|---|---|
| `rls_check.py` | `uv run --project services/api python scripts/rls_check.py --database-url "$DATABASE_OWNER_URL"` (after migrating a throwaway database) | a table lacks `tenant_id NOT NULL`, ENABLE or FORCE RLS, or any permissive policy differs from the canonical `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::<type>` on USING and WITH CHECK (custom ones need a `policy:<table>.<name>  # reason` line); a view lacks `security_invoker=true` (a matview fails unless listed); a table in any schema the runtime role can use is unsafe; the runtime role owns anything, belongs to the owner role or has BYPASSRLS; an allow-list line has no reason |
| `contract_check.py` | `uv run --project services/api python scripts/contract_check.py --app app.main:app --contract docs/api/openapi.yaml` (`--feature-complete` once `plan-graph` reports it) | the app serves an operation, or a 2xx response field or JSON type (integer, number, string, nullable), the contract lacks; with the flag, a contract operation is unbuilt |
| leak fixture | `tests/test_tenant_leak.py` with `tests/leak_registry.py` (part of `pytest`) | a `/v1` route or job type is not in the registry, an exemption has no reason of its own, or tenant A with tenant B's ids gets anything but 403 or 404 (or any of B's ids, or changes B's rows) |

For `contract_check` to see response fields, a route needs a Pydantic `response_model` (a bare `dict` return has no field names).

## Add a route (in this order)

1. Write or change the operation in `docs/api/openapi.yaml` (a decision first for a breaking change), with every error it can return.
2. Add the leak-registry case (`RouteCase`: tenant A calling with tenant B's ids, `expect="denied"` for by-id routes, `"no_leak"` for lists and creates) or an `Exempt` with its own reason; extend `seed` so B has data of the new kind.
3. Write failing tests: success, 401, 403, 404 for another tenant's id, 422, and for writes the `Idempotency-Key` replay, a different body (422) and a missing key (400).
4. Implement: model, service, route, migration (`op.execute`, RLS, grant, `downgrade`).
5. Run all checks below; a red check means the slice is not done.

## Commands (from `services/api`; `DATABASE_URL` is an administrator URL of a THROWAWAY Postgres, never a real database)

```
uv sync --frozen
uv run ruff check . ../../scripts && uv run ruff format --check . ../../scripts
uv run pyright && uv run lint-imports
uv run pytest -q
docker build -t api:dev .
```

Environment the service reads: `APP_ENV` (`development`, `test`, `production`), `DATABASE_URL`, `AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_JWKS_URL`, `AUTH_TENANT_CLAIM`, `LOG_LEVEL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `MAX_BODY_BYTES`; migrations also read `DATABASE_OWNER_URL` (`alembic upgrade head`). The service listens on port 8000. A new service (a queue, a cache, a flag service) follows ask-before-adding.

## Deploying

The API and its database are two Helm charts that Argo CD turns into Applications (see the `gitops` skill): `infra/k8s/apps/api` (the base chart with the API's values: port 8000, probes `/healthz` and `/readyz`, a route on the shared Gateway, a PreSync `alembic upgrade head` Job as the owner role, a NetworkPolicy to the database and, in the cloud, to the auth provider on 443) and `infra/k8s/apps/postgres` (CloudNativePG `Cluster` with the three roles, `db/roles.sql` run once in the application database, a PgBouncer `Pooler` in transaction mode). The service uses the pooler (`DATABASE_URL`, runtime role); migrations use the direct service (`DATABASE_OWNER_URL`, owner role). Never put a credential in either chart.

- **Locally:** run `scripts/local_secrets.sh <project>` once the cluster is up (`local-cluster` skill). It creates the role Secrets, `api-db` and `api-auth` with random passwords and never prints them; run it again any time (it keeps existing passwords). Auth keys go in the gitignored `.env.local` (copy `.env.local.example`); without them `api-auth` is empty and the API runs with `APP_ENV=development`, so every `/v1` route answers 401. Then build the image, push `localhost:5001/api:<unique-tag>`, set that tag in `values-local.yaml`, push the branch with `push.sh` and sync `app-postgres` (wait for the Cluster to be Ready), then `app-api` (the local loop in the `gitops` skill). The route answers at `http://api.localtest.me:8080/` (`*.localtest.me` is 127.0.0.1).
- **Staging and production:** values files pin an image digest that CI writes; their Secrets come from the vault (production readiness, step 12). The database chart is not production-ready until backups and the restore drill land there.
- A failed first sync is expected when the database is not Ready yet: the migration Job gives up after its retries. Wait for the Cluster to be Ready and sync again (the hook recreates the Job); never edit the Job by hand.
- The auth egress rule allows HTTPS to any public address (private, link-local and shared ranges are excepted); tighten to the provider's CIDRs before production.
- If the owner or runtime password Secret changes, the migration Job and pods need a new sync; a changed `roles.sql` only takes effect on a new cluster, so a role change ships as a reviewed manual step, not a values edit.
