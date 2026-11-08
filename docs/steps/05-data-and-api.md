# Step 5: Data and API

Starts when `STATE.md` says `STEP: 5` and you say go. Skills, in order: `domain-model`, `db-schema`, `multi-tenancy`, `api-contract`. Agents: `architect` (the documents) and `reviewer` (blind gate).

## What it is for

Turning the spec and the system design into the data and the contract everything else is built against: the domain model, the PostgreSQL schema with tenant isolation, reversible migrations, and the OpenAPI contract.

## What you will be asked

Only what is still undecided, one area at a time with options and a recommended default ("default" is a valid answer; "not needed" needs a reason): identifiers, deletion and history, money, time, audit, lifecycles, global data; naming, constraints, indexes, concurrency columns, retention, migration tooling; roles, the global-table allow-list, where the tenant is set, storage prefixes, how jobs get the tenant; API versioning, resources, scopes, errors, pagination, idempotency, rate limits, webhooks, files, real-time. Words not yet in `GLOSSARY.md` are added first. Any new service is introduced with what it is, what it will do, why nothing in use does it and its verified cost; nothing is added until you say so.

## Output files

`docs/data/DOMAIN.md`, `docs/data/erd.dot` (+ `erd.svg`), `docs/data/SCHEMA.md`, `docs/data/MIGRATIONS.md`, `docs/api/openapi.yaml`, the gate's verdict in `docs/reviews/05-data-and-api-review.md`, one decision per answer. Folders missing from a v0.1 project are created. Single-tenant products (decision 0002) get `not applicable (decision 0002)` in the tenant sections.

## The rules that are enforced

The runtime database role owns no table and has no `BYPASSRLS`; every tenant table has `tenant_id NOT NULL`, forced row-level security and a policy; the tenant is set with `SET LOCAL` per request and per job; storage keys start with the tenant id; a cross-tenant leak test is designed now and built in step 9; migrations are reversible and expand/contract; money is never a float. The API lives under `/v1`, takes the tenant from the verified token and accepts an `Idempotency-Key`.

## Checks and gate

`dot -Tcanon docs/data/erd.dot` and `npx @redocly/cli@2.71.0 lint docs/api/openapi.yaml` must pass; on lint failure the step is not done. Then a blind `reviewer` reads the five outputs and must return `VERDICT: APPROVE`; a `REJECT` means rework and re-review. Only then do you give the go.

## Who approves

The reviewer first, then you.

## Re-entry

A changed answer is a new decision that supersedes the old one and lists the outputs it makes stale; they stay in `STATE.md ▶ STALE` until updated.

## Hand-off

`STATE.md` is set to `STEP: 6 — Architecture`.

Next: [step 6: architecture](06-architecture.md).
