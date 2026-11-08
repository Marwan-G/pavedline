# Sources (checked 2026-11-08)

Re-check before relying on any of these; they are facts at a date, not rules.

| Fact | Value | URL | Date |
|---|---|---|---|
| Redocly CLI pin | `@redocly/cli` 2.71.0, published 2026-10-23 (npm registry), the newest version at least 14 days before 2026-11-08 (2.71.1 followed on 2026-10-26, newer 2.72–2.76 after); MIT; requires Node >=22.12.0 or >=20.19.0 <21 | https://www.npmjs.com/package/@redocly/cli (via `npm view @redocly/cli time`) | 2026-11-08 |
| Pinned lint command | `npx @redocly/cli@2.71.0 lint docs/api/openapi.yaml` | `npx @redocly/cli@2.71.0 lint --help` run locally (usage `openapi lint [apis...]`) | 2026-11-08 |
| OpenAPI Specification | latest published version v3.2.1 (release date not shown on the page) | https://spec.openapis.org/oas/ | 2026-11-08 |
| OpenAPI 3.1 in Redocly CLI | "Supports OpenAPI 3.x and 2.0 (legacy Swagger), AsyncAPI 3.x and 2.6, Arazzo 1.x"; the `redocly.com/docs/cli/` pages checked say nothing about 3.1 specifically, so the first lint run confirms `openapi: 3.1.x` passes | https://github.com/Redocly/redocly-cli | 2026-11-09 |
| Idempotency-Key header | IETF Internet-Draft `draft-ietf-httpapi-idempotency-key-header-08`, active, last updated 2026-10-22, expires 2027-04-25, not an RFC; retry while processing: 409; same key with different payload: 422; missing required key: 400 | https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ | 2026-11-08 |

Not confirmed: Redocly's default ruleset and rule names for this version (run the lint and read its output); the OpenAPI 3.2.1 release date.
