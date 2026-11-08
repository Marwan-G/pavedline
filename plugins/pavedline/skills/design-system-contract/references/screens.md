# Screens required beyond the product's own

Each is drawn in every state that applies (empty, loading, error, success, no permission, offline on mobile), mobile and desktop.

| Screen | Why | From |
|---|---|---|
| Suspended tenant | sign-in is blocked but data is kept; say what happened and who to contact | `TENANCY-LIFECYCLE.md`, Suspend / offboard |
| Export | tenant and individual data export, format named | `TENANCY-LIFECYCLE.md`, Export |
| Delete | confirmation, what is removed, how long backups keep it | `TENANCY-LIFECYCLE.md`, Delete |
| Impersonation banner | always-visible banner while support acts as a user | `TENANCY-LIFECYCLE.md`, Support access |
| Legal pages | terms, privacy policy, processor agreement, sub-processors, cookie consent where needed; layout only, the text is the founder's | `TENANCY-LIFECYCLE.md`, Legal surface |
| "Please update" | blocking screen on mobile when the app is below the API's minimum version | release rules in `DEPLOYMENT.md` and the API contract |

Single-tenant products (decision 0002) skip the tenant rows and say "not applicable (decision 0002)". A dropped surface (decision 0005) skips its screens.
