# Tenant-isolation rules in SQL

Replace `<table>` and `<role>`; names follow `SCHEMA.md`.

```sql
-- roles: owner runs migrations; app is the runtime role; admin is audited
CREATE ROLE app_runtime LOGIN NOBYPASSRLS;       -- owns nothing, no BYPASSRLS
-- the table owner is the migration role, never app_runtime

ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <table>
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
-- the cast follows the decided tenant id type (uuid shown)
```

Per request, job, webhook handler and scheduled task, inside the transaction:

```sql
BEGIN;
SELECT set_config('app.tenant_id', $1, true);   -- $1 = the verified tenant id, a bound value
-- every query of this unit of work
COMMIT;
```

`SET LOCAL` lasts to the end of the transaction, so a pooled connection never carries a tenant to the next client. Use the parameterised `set_config(..., true)` form from code (the tenant id is a value, not SQL). If `app.tenant_id` is unset, the policy must fail closed (an error or no rows), never see all rows.

## Why FORCE and non-owner

Table owners normally bypass row security unless `FORCE ROW LEVEL SECURITY` is set, and roles with `BYPASSRLS` always bypass it. The runtime role therefore must not own tables and must not have `BYPASSRLS`; the owner role is used only by migrations.

## Global tables

An explicit allow-list in `SCHEMA.md`: table, why it has no tenant, who may write it. The CI schema check fails on any table that is neither tenant-safe nor listed.

## Storage

Keys: `<tenant id>/<kind>/<object id>`. A signed URL is issued only after the same tenant check as a read of the owning row.

## Leak test (designed here, built in step 9)

Fixture: tenants A and B, each with one of every entity. For every operation in `docs/api/openapi.yaml`, every job type and every file path: call as A with B's ids; expect not-found or forbidden and no side effect. A registry lists every endpoint, job type and file path; a new one without a case fails CI. Also assert with the runtime role that `SELECT` without the setting errors or returns no rows.
