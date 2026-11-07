---
name: architecture-intake
description: Asks the platform questions of step 0 - tenancy, solo or team, surfaces, database in Kubernetes or managed, and local runtime - with options, defaults and consequences, and records one decision per answer. Used by the start skill; also use it when one of these answers must be revisited.
---

# architecture-intake

Questions 2, 4, 5, 6 and 7 of step 0. Ask them one at a time. For each: say what the question is, list the options, state the default and what it changes, then wait. "Default" is a valid answer. Record each answer as a decision in `decisions/` (format of `decisions/0000-template.md`).

Do not ask a question already answered in `decisions/` or `PRODUCT.md`.

## Question 2: multi-tenant?

Options: single-tenant, multi-tenant for businesses (organisations), or multi-tenant for consumers (B2C).

If multi-tenant, ask the isolation model:

- **Shared schema with a `tenant_id` column and row-level security** (default). One database, cheapest to run; isolation is enforced by the database and proved by a leak test.
- **Schema per tenant.** Stronger separation, harder migrations.
- **Database per tenant.** Strongest separation, highest cost and operations burden.

Consequence to record: the answer shapes authentication (step 4), the data model (5), the architecture (6), the tenant screens (7), the cross-tenant leak test (9) and the API.

## Question 4: solo or team?

Default: **solo**. One main session writes the records; approvals happen in the chat.
**Team**: parallel lanes, each in its own worktree with its own hand-off, approvals move to pull requests, branch protection and `CODEOWNERS`. Switching later is a new decision that updates `MODE` and `OWNER` in `STATE.md`.

## Question 5: surfaces

Default: **all four**: web app, marketing website with blog, mobile app, API. The user may drop any. Each surface gets its own features in the spec and its own Figma frames.

## Question 6: database

- **In Kubernetes with CloudNativePG (CNPG)** (default).
- **A managed database service.**

Either way, the local cluster always runs CNPG, so every wave is verified against a real Postgres. A managed choice is bound to a real service at step 12, together with the cloud provider. Record: "local runs CNPG; the managed service is chosen at step 12".

## Question 7: local runtime

Default: **Colima with kind**. Alternatives if already installed: Docker Desktop or OrbStack. Check `doctor` output before recommending a change. The local cluster is named `pavedline-<project>`.

## Not asked here

The **cloud provider** is not asked at step 0. It is chosen at step 12, with the production accounts. Cost per tenant is not a required question at all. Domain and email provider come at step 4 or just in time.

Any new service or billable resource, even a free one, follows the ask-before-adding rule: say what it is, what it does, why nothing already in use does it, and its verified cost, then wait for approval.
