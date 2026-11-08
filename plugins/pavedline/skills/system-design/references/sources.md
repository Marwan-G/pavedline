# Sources (checked on the web 2026-11-08)

Re-check before relying on any of these; they are facts at a date, not rules.

| Fact | Value | URL | Date |
|---|---|---|---|
| FastAPI current release | 0.162.2 (released 2026-11-07); requires Python 3.10 or newer | https://pypi.org/project/fastapi/ · https://fastapi.tiangolo.com/release-notes/ | 2026-11-08 |
| Clerk Python SDK | `clerk-backend-api` 7.1.0; its docs describe `authenticate_request` for authenticating frontend requests in a Python backend | https://pypi.org/project/clerk-backend-api/ | 2026-11-08 |
| Istio current release | 1.31.4 (docs site marks v1.31 as current) | https://istio.io/latest/news/releases/ | 2026-11-08 |
| Istio ambient mode | per-node L4 proxy (`ztunnel`) and optional per-namespace L7 waypoint proxies; feature stages: ztunnel core, waypoints core, AuthorizationPolicy, PeerAuthentication stable; multi-network multicluster beta; some waypoint extensions alpha | https://istio.io/latest/docs/ambient/overview/ · https://istio.io/latest/docs/releases/feature-stages/ | 2026-11-08 |

Not confirmed from these pages: the exact upload date of `clerk-backend-api` 7.1.0, and the resource-cost comparison of ambient against sidecar (quote it only with a fresh source). Vendor prices are never copied from here; check them for each approved service.
