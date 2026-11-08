# Auth contract

Ask, do not assume: "Clerk (default), or do you need something else?" Typical reasons to choose another: the product already uses Supabase; compliance or data residency needs self-hosted auth (for example Keycloak); enterprise SSO first. An alternative is checked on the web against the spec (multi-tenant organisations, roles, SSO, MFA, mobile SDK, Python token verification, webhooks or another sync path, data residency, cost at expected users) with a URL and date per claim; the founder decides; a decision records it.

Tenancy is written against a small contract, in `docs/architecture/AUTH.md`:

- the tenant and roles come from the **verified token**, never from a request field;
- membership sync (webhooks or the provider's path), verified and idempotent;
- a reconciliation job;
- every provider call behind one wrapper;
- the provider's cost at expected user counts, never designed to a free tier;
- session lifetime (fixed or rolling), cookie scope per origin, which origins accept tokens, and a sign-up abuse limit and sign-in abuse limit (rate limits on both).

Clerk is the built-in implementation; another provider is planned per project, not pre-built.

**With Clerk:** Clerk Organisation = tenant; our `tenants` table keeps the Clerk org id, synced by verified webhooks · roles: Clerk org roles or app permissions · FastAPI verifies each request with Clerk's Python SDK (`clerk-backend-api`, `authenticate_request`; versions in `sources.md`) · web and mobile sign-in through Clerk's Next.js and Expo SDKs · machine tokens for integrations.

Development keys are created at the first auth slice (just in time); production keys at step 12. Any new service follows ask-before-adding.
