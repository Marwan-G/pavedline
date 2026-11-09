---
name: api-contract
description: Step 5 of Pavedline, part 4 and the step's gate. Writes the OpenAPI contract (docs/api/openapi.yaml) under /v1 with errors, pagination, idempotency and webhooks, lints it with a pinned Redocly CLI, dispatches the blind reviewer on all five step-5 outputs, and on APPROVE and the founder's go moves STATE.md to step 6. Use after multi-tenancy, while STATE.md says STEP 5.
---

# api-contract

Fourth and last skill of step 5 (`domain-model` → `db-schema` → `multi-tenancy` → `api-contract`). Output: `docs/api/openapi.yaml` and one decision per answered question; it then runs the step's gate. Create `docs/api/` and `docs/data/` when missing (a project started with v0.1 has neither). The contract is the source of truth: code and SDKs follow it; a later change to it goes to `decisions/` first.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 1. Read first, in order

After the records of the shared rules: `docs/spec/SPEC.md` (features and acceptance tests per surface), `docs/architecture/SYSTEM-DESIGN.md`, `AUTH.md`, then `docs/data/DOMAIN.md` and `SCHEMA.md`. If a decision already says the API is internal only, the contract is still written (the web app and mobile app are clients of it), and the decision's limits (no public docs, no SDK) are noted in the file's `info.description`. Resource and field names are `GLOSSARY.md` terms, identical to the schema.

## 2. Questions (one area at a time; options, recommended default, what it changes; wait)

Areas, in order, details in `${CLAUDE_SKILL_DIR}/references/questions.md`: versioning and paths · resources and operations per surface · authentication on the API (from `AUTH.md`) and the scopes · errors · pagination and filtering · idempotency · rate limits and quotas · webhooks (incoming and outgoing) · files and uploads · real-time or polling endpoints (from the real-time decision). A new service (an API gateway, a docs host, a mock server) follows ask-before-adding.

Before writing outputs, do the one fill-in turn of the shared rules.

## 3. Rules the contract must follow

- The file declares `openapi: 3.1.x` (`webhooks` needs 3.1; Redocly CLI supports 3.x, see `${CLAUDE_SKILL_DIR}/references/sources.md`). Every path starts with `/v1`; a breaking change is a new version, never an edit.
- **the tenant comes from the verified token**, never from a path parameter, query parameter, header or body field a client can set. A tenant-scoped resource id from another tenant answers not-found. A documented exception is allowed: a public route resolves the tenant from a public handle, a support route from an active grant; each exception is a decision with its reason.
- Every operation has `operationId`, a tag, request and response schemas, and every error response it can return. Errors use one schema (`code`, `message`, `request_id`, optional `details`), listed in `components`.
- Every operation that creates or changes state accepts an `Idempotency-Key` header; keys are stored under `(tenant_id, principal, key)` with a request fingerprint (method, path, body hash); a retry with the same key and fingerprint returns the original result; the same key with a different fingerprint returns a 422 error, never the cached body; the key's lifetime is stated; the table is a tenant table under FORCE RLS and in the leak-test registry. Ask only the detail beyond the Concurrency decision of step 4. Reads are safe by definition.
- Collections paginate (cursor by default) with a documented maximum page size and a stable sort.
- Security schemes are declared once and applied per operation; public operations say `security: []` on purpose.
- When mobile is a surface (decision 0005), the contract exposes the minimum supported app version (an endpoint or a response header) and the blocking error the app shows when it is older. The stack's API sends the response header `X-Min-App-Version` (plain `MAJOR.MINOR.PATCH`, setting `MIN_APP_VERSION`) on every response; declare it once as a `components.headers` entry and reference it from the responses the app reads.
- Money, time and ids use the types decided in `domain-model` (integer minor units plus currency; RFC 3339 UTC instants; string ids).
- Webhooks are described with `webhooks` or callbacks: signed, retried, idempotent by event id. Provider webhook event names are checked on the web (URL and date) or written as a `WAITING.md` item.
- Every acceptance test of the spec that crosses the API maps to at least one operation; list the mapping in the file's `info.description` or an `x-acceptance` field.

## 4. Lint (a hard gate)

Run exactly:

```
npx @redocly/cli@2.71.0 lint docs/api/openapi.yaml
```

The version is pinned (newest release at least 14 days old when written; see `${CLAUDE_SKILL_DIR}/references/sources.md`). It needs Node ≥22.12 (or ≥20.19 <21); `npx` runs it without a global install (`doctor` lists it). Fix every error and every warning the project's config does not explicitly accept. "Clean" means zero errors with every ignore (`.redocly.lint-ignore.yaml`) justified; list the ignored problems to the reviewer. **On lint failure the step is not done**: do not dispatch the reviewer, do not ask for the go. If Redocly cannot run (no Node, no network), say so and record it in `WAITING.md`; do not mark the step done.

## 5. The gate

1. Run all checks: every search or list response is checked against the minimised fields the decisions allow (a list or search returns only what the decision permits, never the full record); every decided behaviour maps to an operation (every decided behaviour in the decisions and the spec has an `operationId`, or a recorded reason it has none); every endpoint path is checked against the glossary's forbidden synonyms (a path uses the glossary term, never a word the glossary rules out); every output exists; `dot -Tcanon docs/data/erd.dot` passes; the lint above exits 0; every tenant table in `SCHEMA.md` has `tenant_id NOT NULL` and an RLS policy (or the tenancy sections say `not applicable (decision 0002)`); every `MIGRATIONS.md` entry has a `down`; every name is in `GLOSSARY.md`.
2. Dispatch the `reviewer` agent (subagent type `pavedline:reviewer`), **blind**, once, on the five outputs: `docs/data/DOMAIN.md`, `docs/data/erd.dot`, `docs/data/SCHEMA.md`, `docs/data/MIGRATIONS.md`, `docs/api/openapi.yaml`. Give it the file paths, `GLOSSARY.md`, `docs/spec/SPEC.md`, `decisions/`, the list of ignored problems, and the checklist (completeness, consistency between domain, schema and contract, glossary words, nothing contradicting a decision, tenant isolation, open choices marked as questions). Never give it your summary.
3. The reviewer ends `VERDICT: APPROVE` or `VERDICT: REJECT — <reason>`. Write the verdict and every finding to `docs/reviews/05-data-and-api-review.md` (create `docs/reviews/` when missing); on REJECT the file lists the findings to rework, so a fresh session resumes from it. A `REJECT` means rework and a narrow re-review, never arguing past it. Record each finding as fixed or accepted with a reason. After the rework re-run the checks of step 1.
4. Only after `VERDICT: APPROVE`, show the founder the outputs, the decisions and the verdict, and ask for the go. The `APPROVE` comes before the founder's go; the founder's go never replaces it.

## 6. Close step 5

After `VERDICT: APPROVE` and the founder's go, edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 6 — Architecture
LAST: <timestamp> — step 5 done: DOMAIN.md, erd.dot, SCHEMA.md, MIGRATIONS.md, openapi.yaml; reviewer APPROVE, see docs/reviews/05-data-and-api-review.md
NEXT: step 6 — architecture diagram, threat model, Helm and environment layout
```

Commit and close as in the shared rules.
