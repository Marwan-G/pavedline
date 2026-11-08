# API-contract questions

One area at a time, in order. Each answer is one decision.

## Versioning and paths

Default: `/v1` prefix, additive changes within a version, breaking change = `/v2`. Changes: every path, the client, deprecation policy.

## Resources and operations

Derived from the spec per surface and from `DOMAIN.md`; confirm the list with the founder. Default: REST resources named by glossary terms, plural nouns, standard verbs, actions as sub-resources.

## Authentication and scopes

From `AUTH.md`: bearer token verified by the auth provider's SDK; the tenant is read from the verified token. Scopes or roles per operation. Changes: security schemes, the leak test.

## Errors

Default: one error object (`code`, `message`, `request_id`, optional `details`), stable machine codes, HTTP status per class (400, 401, 403, 404, 409, 422, 429, 5xx). Changes: client handling, every operation's responses.

## Pagination and filtering

Default: cursor pagination, `limit` with a stated maximum, stable sort, filters as query parameters named after fields. Changes: indexes (db-schema).

## Idempotency

Asks only the detail beyond the Concurrency decision of step 4. Default: `Idempotency-Key` on every state-changing operation, stored 24 hours under `(tenant_id, principal, key)` with a request fingerprint (method, path, body hash); same key and fingerprint returns the first result, a different fingerprint is a 422 error. Changes: an idempotency table in the schema (a tenant table under FORCE RLS, in the leak-test registry).

## Rate limits and quotas

From the security decision: edge limits plus per-tenant quotas; the contract documents `429` and `Retry-After` and the quota error.

## Webhooks

Incoming (auth provider, payments, SMS) and outgoing (if any): signature verification, event-id idempotency, retry policy, replay. Changes: an events table, the queue.

## Files and uploads

From the images-and-files decision: signed upload and download URLs, size and type limits, tenant-prefixed keys.

## Real-time or polling

From the real-time decision: the endpoints or event streams, polling interval, cache headers.
