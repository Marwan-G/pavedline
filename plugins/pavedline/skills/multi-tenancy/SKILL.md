---
name: multi-tenancy
description: Step 5 of Pavedline, part 3. Applies the non-negotiable tenant-isolation rules to the schema - database roles, tenant_id NOT NULL, forced row-level security, SET LOCAL per request and job, tenant-prefixed storage keys, and the cross-tenant leak test design. Adapted from the saas-multi-tenant skill (MIT). Use after db-schema, while STATE.md says STEP 5.
---

# multi-tenancy

Third skill of step 5 (`domain-model` → `db-schema` → `multi-tenancy` → `api-contract`). It is enforced, not advised. Output: the tenant sections of `docs/data/SCHEMA.md` (roles, policy per table, global allow-list), a "Tenant isolation" section in `docs/data/MIGRATIONS.md`, and the leak-test design in `docs/data/SCHEMA.md ▶ Leak test`. Create `docs/data/` when missing (a project started with v0.1 has none).

**Single-tenant** (decision 0002): write `not applicable (decision 0002)` in those sections and change nothing else; do not invent tenancy. Then go straight to `api-contract`.

Adapted with credit from sickn33's `saas-multi-tenant` skill (MIT) with Supabase's Postgres practices (MIT) as a reference; see `CREDITS.md` and `THIRD_PARTY_NOTICES.md`. Design work goes to the `architect` agent (subagent type `pavedline:architect`) with a self-contained prompt. Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## 1. Read first, in order

`CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/` (0002 tenancy model, 0006 database), `GLOSSARY.md`, `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md`, `TENANCY-LIFECYCLE.md`, `docs/data/DOMAIN.md`, `docs/data/SCHEMA.md`. Ask only what is undecided; the tenancy model (shared schema with `tenant_id` and RLS is the default; schema-per-tenant or database-per-tenant if decided in step 0) is not re-asked. If the decision is not shared-schema, say which rules below change and record a decision before continuing.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. The rules (naming first) (all are required; detail in `${CLAUDE_SKILL_DIR}/references/rules.md`)

The tenant column is always named `tenant_id` and the setting `app.tenant_id`, even when the glossary calls the tenant something else (an organisation, a workspace, an account): the glossary records the mapping, and Pavedline's CI schema check looks for these names.

1. **Roles.** The runtime role **does not own** any table and has no `BYPASSRLS`. Migrations run as a separate owner role. Admin and reporting use a third, audited role. Three roles, written in `SCHEMA.md`.
2. **Every tenant table** has `tenant_id NOT NULL`, **`ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`**, and a policy on `current_setting('app.tenant_id')` (both `USING` and `WITH CHECK`). **CI reads the real schema and fails** if a tenant table lacks any of them. Global tables are listed explicitly in an allow-list, each with a reason.
3. **The tenant is set with `SET LOCAL` inside the transaction** (or `set_config(..., true)`), for every request **and every job, webhook handler and scheduled task**. Session `SET` and session advisory locks are forbidden: the pooler runs in transaction mode and they leak or break across clients.
4. **Storage keys start with the tenant id**; signed URLs are issued only after the same tenant check.
5. **The cross-tenant leak test is a fixture:** two tenants; every endpoint, every job type and every file path is exercised as tenant A with tenant B's ids and must fail. A new endpoint or job without coverage fails CI. Design it now (the fixture, how coverage is counted from the OpenAPI file and the job registry); it is built in step 9. Every exemption from the test (a public route, a global table, a webhook ingress) is listed with its own reason: a reason per exemption, never one reason shared by several.
6. **Reversible, expand/contract migrations**; tenant creation in one transaction (see `TENANCY-LIFECYCLE.md` stage 1).
7. The tenant id comes from the verified token on the server, never from a client-supplied field or header.
8. **A cross-tenant job** (a scheduled task over all tenants) enumerates tenants from a global table the runtime role may read, then runs one transaction per tenant with `SET LOCAL`; never a `BYPASSRLS` runtime role. The migration owner is the only role with `BYPASSRLS` (the audited admin role does not have it unless a decision says so).

## 3. Questions

One area at a time with options, a recommended default and what it changes; wait; "default" is valid; "not needed" only with a recorded reason: role names and who holds the admin role · global tables allow-list · where the tenant is set (middleware or dependency; the tenant id type comes from domain-model's Identifiers decision, not re-asked) · storage prefix layout · how jobs receive the tenant id. None skipped or merged; before closing compare the areas with the decisions written. Record each as a decision (`decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record. A new service (a policy-management tool, a hosted auth add-on): what it is, what it will do, why nothing in use does it, verified cost; wait for the founder.

## 4. Write the outputs

**One fill-in turn.** Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

For each tenant table in `SCHEMA.md`, write the exact RLS statements (copy the pattern from `${CLAUDE_SKILL_DIR}/references/rules.md`). Check: every tenant table has `tenant_id NOT NULL` and a policy; every global table is in the allow-list with a reason; no table is in both; storage prefix and leak-test design are written. Machine checks run from step 9; the design is reviewed at the step gate.

## 5. Re-entry

A changed tenancy answer is a new decision that supersedes the old (`supersedes NNNN`); stale outputs go to `STATE.md ▶ STALE` with the number.

## 6. Hand on

Continue with `api-contract`, which runs the gate and closes the step.
