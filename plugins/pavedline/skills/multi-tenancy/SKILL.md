---
name: multi-tenancy
description: Step 5 of Pavedline, part 3. Applies the non-negotiable tenant-isolation rules to the schema - database roles, tenant_id NOT NULL, forced row-level security, SET LOCAL per request and job, tenant-prefixed storage keys, and the cross-tenant leak test design. Adapted from the saas-multi-tenant skill (MIT). Use after db-schema, while STATE.md says STEP 5.
---

# multi-tenancy

Third skill of step 5 (`domain-model` → `db-schema` → `multi-tenancy` → `api-contract`). It is enforced, not advised. Output: the tenant sections of `docs/data/SCHEMA.md` (roles, policy per table, global allow-list), a "Tenant isolation" section in `docs/data/MIGRATIONS.md`, and the leak-test design in `docs/data/SCHEMA.md ▶ Leak test`. Create `docs/data/` when missing (a project started with v0.1 has none).

**Single-tenant** (decision 0002): write `not applicable (decision 0002)` in those sections and change nothing else; do not invent tenancy. Then go straight to `api-contract`.

Adapted with credit from sickn33's `saas-multi-tenant` skill (MIT) with Supabase's Postgres practices (MIT) as a reference; see `CREDITS.md` and `THIRD_PARTY_NOTICES.md`.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 1. Read first, in order

After the records of the shared rules (0002 is the tenancy model, 0006 the database): `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md`, `TENANCY-LIFECYCLE.md`, `docs/data/DOMAIN.md`, `docs/data/SCHEMA.md`. The tenancy model (shared schema with `tenant_id` and RLS is the default; schema-per-tenant or database-per-tenant if decided in step 0) is not re-asked. If the decision is not shared-schema, say which rules below change and record a decision before continuing.

## 2. The rules (all are required; tenant naming is in the shared rules; detail in `${CLAUDE_SKILL_DIR}/references/rules.md`)

1. **Roles.** The runtime role **does not own** any table and has no `BYPASSRLS`. Migrations run as a separate owner role. Admin and reporting use a third, audited role. Three roles, written in `SCHEMA.md`.
2. **Every tenant table** has `tenant_id NOT NULL`, **`ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`**, and a policy on `current_setting('app.tenant_id')` (both `USING` and `WITH CHECK`). **CI reads the real schema and fails** if a tenant table lacks any of them. Global tables are listed explicitly in an allow-list, each with a reason.
3. **The tenant is set with `SET LOCAL` inside the transaction** (or `set_config(..., true)`), for every request **and every job, webhook handler and scheduled task**. Session `SET` and session advisory locks are forbidden: the pooler runs in transaction mode and they leak or break across clients.
4. **Storage keys start with the tenant id**; signed URLs are issued only after the same tenant check.
5. **The cross-tenant leak test is a fixture:** two tenants; every endpoint, every job type and every file path is exercised as tenant A with tenant B's ids and must fail. A new endpoint or job without coverage fails CI. Design it now (the fixture, how coverage is counted from the OpenAPI file and the job registry); it is built in step 9. Every exemption from the test (a public route, a global table, a webhook ingress) is listed with its own reason: a reason per exemption, never one reason shared by several.
6. **Reversible, expand/contract migrations**; tenant creation in one transaction (see `TENANCY-LIFECYCLE.md` stage 1).
7. The tenant id comes from the verified token on the server, never from a client-supplied field or header.
8. **A cross-tenant job** (a scheduled task over all tenants) enumerates tenants from a global table the runtime role may read, then runs one transaction per tenant with `SET LOCAL`; never a `BYPASSRLS` runtime role. The migration owner is the only role with `BYPASSRLS` (the audited admin role does not have it unless a decision says so).

## 3. Questions

Asked per area as the shared rules say: role names and who holds the admin role · global tables allow-list · where the tenant is set (middleware or dependency; the tenant id type comes from domain-model's Identifiers decision, not re-asked) · storage prefix layout · how jobs receive the tenant id. A new service (a policy-management tool, a hosted auth add-on) follows ask-before-adding.

## 4. Write the outputs

Before writing outputs, do the one fill-in turn of the shared rules.

For each tenant table in `SCHEMA.md`, write the exact RLS statements (copy the pattern from `${CLAUDE_SKILL_DIR}/references/rules.md`). Check: every tenant table has `tenant_id NOT NULL` and a policy; every global table is in the allow-list with a reason; no table is in both; storage prefix and leak-test design are written. Machine checks run from step 9; the design is reviewed at the step gate.

## 5. Hand on

Continue with `api-contract`, which runs the gate and closes the step.
