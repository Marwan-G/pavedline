# System-architecture questions

None may be skipped. "Not needed" is valid only with a recorded reason. Per area: question, options, recommended default, what the answer changes. Each answer feeds a decision, `ARCHITECTURE.dot` and `DEPLOYMENT.md`. A new service: ask before adding, never designed to a free tier.

## Stack pack
Default `nextjs-fastapi` (monorepo: web app, optional website and blog app, mobile app, FastAPI service, shared packages). Surfaces dropped in decision 0005 drop their app. Changes: which apps exist and what step 9 builds. The pack's templates are copied in a later release.

## Apps and services
Which apps and services run as separate deployments (default: web app, API, background worker, website separately so it caches and releases on its own) and which share one. Changes: nodes in the diagram, replicas, release independence.

## Environments and namespaces
Default: local, staging, production, one namespace per environment per concern (apps, data, platform), each with its own values file. Changes: isolation, cost, what staging proves.

## Ingress and edge
Default: Kubernetes Gateway API in front of the web app, website and API, with a tunnel or load balancer chosen per infra profile (decided in step 12). Changes: routes, TLS ownership, edge rate limits. Version facts: `${CLAUDE_SKILL_DIR}/references/sources.md`.

## Database placement
Asks only pool size, replicas and backups, given decision 0006 and the step 4 availability numbers. Changes: backups, restore drill, connection pooling, cost.

## Secrets path
Secret store to Kubernetes Secret, never in Git; who owns rotation (`SERVICES.md`). Changes: bootstrap steps, `WAITING.md` items.

## Observability seam
Structured JSON logs to stdout; one collector and one vendor, if any (a new service: ask). Changes: nodes, alert routing, cost.

## Release and rollback
Image tag bump by pull request, manual sync for apps, migrations as a pre-release job, expand/contract so a revert never meets a schema it cannot read. Changes: release order, mobile compatibility window.
