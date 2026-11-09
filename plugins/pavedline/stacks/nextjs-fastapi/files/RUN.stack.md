## Run it locally (the `nextjs-fastapi` stack)

Tools: Docker, `kind`, `kubectl`, `helm`, `uv`.
<!-- pavedline-begin: web,site,mobile -->
Also Node (the version in `.node-version`) and pnpm (`packageManager` in `package.json`; without it,
`npx --yes pnpm@<that version> <command>`).
<!-- pavedline-end -->

**All apps on the local cluster (the realistic way).** `/pavedline:deploy-local` (step 10) builds each image, pushes it
to the local registry, pushes the branch to the local git server and syncs the apps through Argo CD. Then:

| App | URL | What you see |
|---|---|---|
<!-- pavedline-begin: web -->
| web | `http://app.localtest.me:8080/` | the home page, with the API's health read on the server |
<!-- pavedline-end -->
<!-- pavedline-begin: site -->
| site | `http://www.localtest.me:8080/` | the website, the blog at `/blog`, `/sitemap.xml`, `/robots.txt` (disallow-all: not the public origin) |
<!-- pavedline-end -->
<!-- pavedline-begin: api -->
| api | `http://api.localtest.me:8080/healthz` | `{"data":{"status":"ok"}}` |
<!-- pavedline-end -->

`*.localtest.me` resolves to 127.0.0.1; host port 8080 is the Gateway.

**One app on its own (fast loop).**
```bash
# pavedline-begin: web,site,mobile
pnpm install --frozen-lockfile
# pavedline-end
# pavedline-begin: web
API_INTERNAL_URL=http://127.0.0.1:8000 pnpm --filter @app/web dev     # http://localhost:3000, needs the API running (below)
# pavedline-end
# pavedline-begin: site
pnpm --filter @app/site dev                                            # http://localhost:3000 (use another port: -- -p 3001)
# pavedline-end
# pavedline-begin: api
(cd services/api && APP_ENV=development DATABASE_URL=... uv run uvicorn app.main:app --port 8000)  # the API; see the fastapi-service skill
# pavedline-end
```

**Checks (all from the repository root).**
```bash
# pavedline-begin: web,site,mobile
pnpm -r lint && pnpm -r typecheck && pnpm -r test     # biome ci, tsc --noEmit, vitest
# pavedline-end
# pavedline-begin: web
pnpm run check:generated                              # the API client and the tokens match docs/api/openapi.yaml and docs/design/tokens.json
# pavedline-end
# pavedline-begin: web,site
python3 scripts/web_boundary_check.py                 # Next.js is frontend only: no route handlers, server actions or database imports
# pavedline-end
# pavedline-begin: web
pnpm --filter @app/web build && pnpm --filter @app/web exec playwright install chromium && pnpm e2e   # browser test with axe (WCAG 2.2 AA)
# pavedline-end
# pavedline-begin: web
docker build -f apps/web/Dockerfile -t web:dev .      # context is the repository root; the image's boot check runs in the build
# pavedline-end
```

<!-- pavedline-begin: web -->
After the contract changes (step 5, or a slice that changes the API): `pnpm --filter @app/api-client generate`.
<!-- pavedline-end -->

<!-- pavedline-begin: web,site -->
After the design tokens change (step 7): `pnpm --filter @app/tokens build`. Commit the generated files.
<!-- pavedline-end -->

<!-- pavedline-begin: web,site -->
**Content-Security-Policy trade-off (deliberate).** Both apps allow `'unsafe-inline'` for scripts and styles (never
`'unsafe-eval'`), because Next.js inlines its bootstrap script and a nonce would force every page to render per request.
A product that renders user-generated content moves to nonces (per-request rendering) and drops `'unsafe-inline'`.
<!-- pavedline-end -->

<!-- pavedline-begin: web,site,mobile -->
**Exact versions.** `.npmrc` sets `save-exact=true`, so `pnpm add` writes exact versions (the pack's rule); keep
`minimumReleaseAge` in `pnpm-workspace.yaml`.
<!-- pavedline-end -->

<!-- pavedline-begin: api -->
**Backups and the restore drill (local).** The database ships with backups: WAL archiving and a daily base backup
through the Barman Cloud plugin, switched on by `backup.enabled`. Staging and production ship it `false` with placeholder endpoint and bucket; step 12 fills
them in, creates the `db-backup-s3` Secret and turns it on, and the chart refuses to render enabled backups that still
point at a placeholder. To try them on kind, create the cluster with `scripts/local-cluster/up.sh <project> --full`
(cert-manager, the plugin and a local S3 store), run `scripts/local_secrets.sh <project>` (it copies the store's throwaway key
into `db-backup-s3`), and deploy with `backup.enabled: true` and three instances in `infra/k8s/apps/postgres/values-local.yaml`
(`cluster.antiAffinity: preferred` on a one-node cluster). Then `scripts/restore_drill.sh <project>` writes a marker row, takes a
backup, restores it into a new cluster `db-restore`, reads the marker back, deletes the restore cluster and prints
`RESTORE DRILL PASS` (exit 0) or `RESTORE DRILL FAIL` (exit 1). It refuses any context that is not `kind-pavedline-*`.
<!-- pavedline-end -->
