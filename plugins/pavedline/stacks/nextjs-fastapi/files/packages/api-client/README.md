# @app/api-client

Typed client for the API, generated from `docs/api/openapi.yaml` (the contract written at step 5).

- Generator: `openapi-typescript` (types) with `openapi-fetch` (a tiny fetch wrapper that uses those types). Both are
  MIT, maintained together, and add no runtime code beyond `fetch`.
- `pnpm --filter @app/api-client generate` writes `src/generated/schema.d.ts`. Commit the result.
- `pnpm --filter @app/api-client check` regenerates into a temporary directory and fails if the committed file differs.
  CI runs it, so the client can never drift from the contract.
- In this stack pack `src/generated/schema.d.ts` is an empty placeholder: a product has no contract until step 5. The
  starter check overlays `example/`, which holds a generated file for its example contract.
- `getHealth()` is hand-written on purpose: `/healthz` is a probe, not a contract operation.
