# TENANCY-LIFECYCLE.md

Only when multi-tenant (decision 0002). Single-tenant: write `not applicable (decision 0002)` and stop; do not invent tenancy. Decided in step 4, designed in 5 and 7, built and tested in 9. Each stage below becomes a section of `docs/architecture/TENANCY-LIFECYCLE.md` with what is designed and how it is tested.

1. **Create**: sign-up, auth-provider organisation (Clerk by default), `tenants` row, default roles, settings and onboarding state, all in one transaction.
2. **Sync and repair**: auth-provider webhooks (or the provider's sync path) verified and idempotent; a scheduled reconciliation job repairs drift from missed events; covered by tests.
3. **Suspend / offboard**: suspension blocks sign-in and API keys but keeps data; offboarding starts the retention clock; both audited.
4. **Export**: tenant and individual (data-subject request) export in a documented machine-readable format.
5. **Delete**: live data and files removed; the decision states how long deleted data survives in backups and that restores re-apply deletions; the privacy policy says the same. Delete third-party copies too (the auth provider's organisation and users, message logs, analytics); the decision states how audit-log retention and tenant deletion fit together.
6. **Legal surface**: terms, privacy policy, processor agreement, sub-processor list, cookie consent where needed. Pages exist and are linked; the legal text is the founder's.
7. **Support access**: an admin console; impersonation only with an audit entry and a visible banner; no shared logins. Access is by grant: a grant duration with a default and a maximum, revocable by the tenant admin, read-only by default; operator tokens are accepted only on support routes.
8. **Limits**: per-tenant quotas and rate limits.

Create `docs/architecture/` first when it is missing.
