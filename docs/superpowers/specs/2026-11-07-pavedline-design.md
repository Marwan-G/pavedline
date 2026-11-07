# Pavedline — design

> **The GitOps software factory for Claude Code: from idea to production on a paved road.**

Status: **approved 2026-11-07.** Written 2026-11-07.
Author: Marwan Ghubein ([LinkedIn](https://www.linkedin.com/in/marwan-ghubein/)), with Claude Opus 5.5.
Flow diagram: [`docs/flow.dot`](../../flow.dot), rendered to `docs/flow.svg`.

Each decision below is marked **(founder)** if Marwan made it in the 2026-11-07 conversation, or **(call)** if
the designer made it from verified facts. The founder can overturn any (call).

---

## 1. Intent: why this exists

AI coding agents are good at producing a demo. Almost nothing open-source takes a **serious product** through a
**complete, real SDLC that ends in production**: market research, interrogating the idea, a spec, the data model and
multi-tenancy, the architecture, a real Figma design system, a plan, test-driven build, independent reviews, GitOps
deploy, and post-deploy verification. And it has to remember everything between sessions. Existing kits cover parts.
superpowers covers build discipline. spec-kit covers specs. ECC covers a large toolbox. Matt Pocock's skills cover
interrogation and specs. None ends in a running, verified production system on Kubernetes through GitOps.

Pavedline is that end-to-end path. It is distilled from the workflow the author used to build and run a production
platform. It keeps what that workflow proved and fixes what hurt it (§14).

Its first user is the author, for a new multi-tenant SaaS built in its own private repo. **No product built with
Pavedline is named in this repo (founder).** Product notes live only in that product's own repo.

**Every product ships four surfaces (founder):**
1. **Website**: public marketing pages (product, pricing, about, legal), SEO-ready.
2. **Blog**: articles on the website's domain (MDX), with RSS and sitemap.
3. **Web app**: the multi-tenant SaaS application.
4. **Mobile app**: native iOS and Android, sharing the API, auth, tokens and glossary with the web app.

Steps 3 (spec), 6 (architecture), 7 (Figma: a frame set per surface), 8 (plan), 10 (local deploy) and 11 (production) cover all four. A
project may defer a surface only through a recorded ADR.

## 2. Who it is for

- **Solo founders working with Claude, and teams of several developers. Both must work (founder).**
- **Serious production projects, not local demo apps (founder).** It expects real accounts: cloud, domain,
  Figma, GitHub. The README says so up front and lists the requirements (§12).
- **Public and open-source (founder):** a public GitHub repo, MIT licence (call), and no secret anywhere.

## 3. Goals

0. **Four surfaces, always (founder):** website, blog, web app and mobile app (§1).
1. One clear path: **step 0 → step 12** (§5). Built and verified on local Kubernetes; the cloud comes once, at step 11. Each step has defined inputs, output files, skills, an agent, a gate
   and an approver.
2. **Memory from files only.** A fresh session, or a new teammate, resumes from the repo with no chat history (§6).
3. **Production from the first commit.** A Helm base chart, GitOps through ArgoCD, staging and production
   environments, backups with a tested restore, least privilege and secret hygiene (§10).
4. **GitOps is the backbone, not a feature (founder).** Git is the only way anything reaches a cluster (§10.1).
5. **Diagrams everywhere (founder).** Every folder that holds architecture carries a `.dot`, and every plan carries
   a `.dot`. CI validates and renders them, and fails on drift (§9).
6. **Figma is required (founder).** There is a real design system and every screen in every state, approved
   before build (§5, step 7).
7. **Database design is its own step (founder).** The step-0 intake asks: DB in Kubernetes or a managed service?
   (founder). **Multi-tenancy is the first intake question** (§5.1); a dedicated skill covers it (§5, step 5).
8. **Market research toward profitability (founder),** done with free open-source tools only (founder).
9. **Rules are enforced by hooks and CI, not prose.** Each rule is written once, in one place.
10. **Attractive public face (founder).** A diagram on the first page, a clear "what you get", a requirements list,
    and "who's behind this".

## 4. Non-goals and anti-goals

**Non-goals (not now):**
- **Observability and tracing: out of scope (founder)**, except two alerts (uptime and backup failure, §10.9). A clean seam is left (`templates/infra/k8s/addons/` slot +
  `docs/extending.md`), so a future observability agent and skill can plug in. No OpenTelemetry, Prometheus or
  logging stack ships in v1.
- Building any product inside this repo.
- Supporting every cloud in v1. The process and the Helm/ArgoCD core are cloud-agnostic, and **one infra profile
  ships: OCI/OKE** (call). Other profiles come later, as contributions.
- Replacing the plugins it depends on.

**Anti-goals (failure even if it technically works):**
- **A changelog posing as instructions.** In the source project, the instructions file reached 1,213 lines of dated amendments.
  Pavedline's project `CLAUDE.md` stays at about 150 lines or fewer, and current rules are stated only once.
- **Records that outgrow their purpose.** Its progress checklist reached 933 KB and its hand-off 9,272 lines, and 89
  of 120 PRs in eight days were records-only. Pavedline caps record size with hooks and archives history automatically.
- **The same rule copied into 5–7 files.** That made drift unavoidable.
- **Gates that exist only in prose.**
- **Anything that only works as a local demo.**
- **A paid or closed tool inside the factory.** The user's own production accounts (cloud, Figma, app stores, Clerk, domain) are requirements, listed in §12, not factory tools.
- **Leaking anything private.** No real cloud IDs, tenancy OCIDs, domains, names in examples, or secrets.

## 5. The flow: thirteen steps

Source of truth: [`docs/flow.dot`](../../flow.dot). Every step writes files. A step is done when its output files
exist, its gate passed, and `STATE.md` points at the next step. **Every checkpoint ends by asking the founder
"go?"; nothing moves on without it (founder).**

| # | Step | Output files (in the product repo) | Skills (new = Pavedline writes it) | Agent | Gate / approver |
|---|---|---|---|---|---|
| 0 | **Start** | `STATE.md`, `CLAUDE.md`, `decisions/0001-…` (one ADR per intake answer), `RUN.md`, `SERVICES.md`, `LINKS.md`; stack-neutral templates only (records, GitOps core) | new `start`, new `architecture-intake`, new `state`, new `doctor` | orchestrator | founder confirms intake |
| 1 | **Market** | **Input: the founder names the sites and products they already have in mind (founder); the researcher starts there and widens.** Output: `docs/business/competitors/*.md`, `docs/business/BRIEF.md` (pricing, positioning, market size, how it makes money), `docs/business/landscape.dot` | new `competitor-teardown`, new `pricing-model`, new `market-size`; `competitive-brief` + `synthesize-research` (Anthropic knowledge-work-plugins) | researcher | founder approves brief |
| 2 | **Grill** | `decisions/*`, `GLOSSARY.md` | `grilling`, `grill-with-docs` (Matt Pocock) | orchestrator | interrogation frontier empty |
| 3 | **Spec** | `docs/spec/SPEC.md` (users, jobs, features per surface, non-goals, acceptance tests); team mode adds GitHub issues | new `spec`; `to-tickets` (Matt Pocock, team mode) | orchestrator | founder approves spec |
| 4 | **System design decisions** (new; mandatory questions, §5.2) | one ADR per answer; `docs/architecture/SYSTEM-DESIGN.md` (all answers with real numbers); `docs/architecture/AUTH.md`; `SERVICES.md` rows for any new service | new `system-design`, new `backend-evaluate`; Clerk skills (`clerk-orgs`, `clerk-nextjs-patterns`, `clerk-expo-patterns`, `clerk-webhooks`) | architect (+ researcher for evidence) | founder answers / approves each decision, then "go?" |
| 5 | **Data + API** | `docs/data/DOMAIN.md`, `docs/data/erd.dot`, `docs/data/SCHEMA.md` (tables, keys, constraints, indexes, tenancy key, version columns for concurrent edits, storage keys for files, retention, billing and entitlements, the audit log, feature flags; RLS rules per §11), `docs/data/MIGRATIONS.md`, `docs/api/openapi.yaml` | new `domain-model`, new `db-schema`, new `multi-tenancy`, new `api-contract` | architect + blind reviewer | reviewer `VERDICT: APPROVE`, then founder |
| 6 | **Architecture** | `docs/architecture/ARCHITECTURE.dot` (context + containers, showing every step-4 result: bucket, CDN, queue, workers, regions), `docs/architecture/THREATS.md`, Helm/env layout; **the stack-dependent templates are copied now**, after step 4 decided the stack | new `system-architecture`, new `helm-base-chart`, new `gitops`, new `threat-model` | architect | founder approves |
| 7 | **Figma (required)** | Figma file: tokens (light/dark), type, spacing, components with all variants (Figma name = code name), FigJam user flows, a frame set **per surface** (website, blog, web app on desktop + mobile web, native mobile app), every screen in every state (empty, loading, error, success, no-permission); **multi-tenant screens when step 0 said multi-tenant**: org switcher, invite members, roles, tenant settings, a new tenant's first run, org switching on mobile; **lifecycle and release screens**: billing and plans, legal pages and cookie consent, data export and delete, the admin/support console with its impersonation banner, the "please update" screen for old mobile versions; `docs/design/DESIGN.md` (file + node links); Code Connect map; exported tokens | `ui-ux-pro-max` (reference input, never the authority), `figma-use`, `figma-generate-library`, `figma-generate-design`, `figma-use-figjam`, `figma-code-connect`, `impeccable` (critique), new `design-system-contract` | designer + design-verifier (blind) | `DESIGN VERDICT: APPROVE`, then **founder approves the visual** |
| 8 | **Plan** | `docs/plans/<date>-<wave>.md` + `docs/plans/<date>-<wave>.dot` (slice dependency graph) | `superpowers:writing-plans`, new `plan-graph` | orchestrator | founder approves the wave |
| 9 | **Build** (per slice) | code + tests + migrations, PR with the gates line, `handoff/<branch>.md` | superpowers `test-driven-development`, `subagent-driven-development`, `using-git-worktrees`, `verification-before-completion`, `finishing-a-development-branch`; built-in `security-review`; new `quality-gates`; `db-schema` / `multi-tenancy` when a slice touches data | builder + reviewer (blind) + adversary (blind) | five gates (§8), squash-merge |
| 10 | **Deploy to local Kubernetes** (every wave) | web, site and API: the image-tag bump PR, synced by ArgoCD **inside the local kind cluster**; mobile: a CI build installed on simulators/devices; deploy record in `STATE.md` | new `deploy`, new `local-cluster` | deployer | migrations first, sync, then **verify the running pods**, never the `Synced` label |
| 11 | **Go to production** (once, at the end; §5.6) | `docs/production/INFRA.md`, `NEEDS.md`, `LAUNCH.md`; Terraform profile filled; **cloud staging, then production** | new `go-to-production`, `deploy`, `gitops` | deployer + architect | founder: "time for production?" → infra answers → founder's `terraform apply` → staging verified → production verified → **"go live"** |
| 12 | **Learn** | `docs/retros/<date>.md`; new rules land as edits to the one place they live | `retro` (Matt Pocock), new `lessons` | orchestrator | founder reads |

Steps 8–10 repeat per wave until the product is feature-complete on local Kubernetes; then step 11 runs once; after launch every wave goes local → cloud staging → production. Steps 1–7 can be re-entered when a later step changes the plan. The
re-entry is recorded as a decision.

### 5.1 Step 0 intake: stack-neutral questions only

Each answer becomes an ADR:
1. **Is the product multi-tenant? (first question; founder)** Options: single-tenant, multi-tenant B2B (organisations), or B2C.
   If multi-tenant: the model (default: shared schema + `tenant_id` + row-level security; alternatives:
   schema-per-tenant, database-per-tenant). The answer flows into steps 4 (auth: Clerk Organization ↔ tenant), 5
   (tenant key on every table, RLS), 6 (architecture), 7 (Figma tenant screens), 9 (cross-tenant leak test at the
   merge gate) and the API (every call is scoped to a tenant).
2. Solo or team.
3. Local runtime for the test cluster (default: Colima + kind; Docker Desktop or OrbStack if already installed). **No cloud question here (founder):** the cloud is chosen at step 11.
4. **Database in Kubernetes (CNPG) or a managed service (founder).**
5. Surfaces: all four by default (§1). Deferring one needs a recorded reason.
6. Domain, environments (default: staging + production), email provider.

**Not asked at the start (founder):** cost per tenant. It would block early progress. It is not a mandatory
question. A project can add usage metering later as an ordinary wave.

### 5.2 Step 4: the mandatory system-design questions

None may be skipped. "Not needed" is a valid answer only with a recorded reason. Each answer goes to: **an ADR** · **`docs/architecture/SYSTEM-DESIGN.md`** (with numbers) · **`ARCHITECTURE.dot`** (step 6) · **`SERVICES.md`** for any new service (the ask-before-new-service rule applies: what, why, verified cost) · **the data design and the plan** (locking becomes columns, file locations become storage keys, targets become tests).

| Area | Questions |
|---|---|
| **Backend** | **FastAPI is the founder's preference. `backend-evaluate` checks it against the spec's needs with sources, names anything it would struggle with, compares alternatives only then, and recommends. The founder decides.** **Next.js is frontend only (founder).** No business logic in Next.js. The only server code allowed is a pass-through proxy for auth cookies if the auth setup needs one, enforced by a CI import-boundary check |
| **Auth: Clerk (founder)** | Clerk Organization = tenant? (our `tenants` table keeps the Clerk org id, synced by signed webhooks) · the tenant always comes from the verified token, never from the client · roles: Clerk org roles or app permissions · FastAPI verifies every request with Clerk's Python SDK `clerk-backend-api` → `authenticate_request` (verified 2026-11-07, MIT) and sets the tenant for RLS with `SET LOCAL` · web and mobile sign-in through Clerk's Next.js and Expo SDKs (verified in `clerk/javascript`) · machine tokens / API keys for integrations · all Clerk calls behind one auth wrapper (exit path) · Clerk cost at expected user counts, verified at the time, never designed to the free tier |
| **Security** | data classification (personal or payment data?) · encryption in transit and at rest · where secrets live · insert-only audit log · rate limits at the Cloudflare edge, never in app code · dependency and container scanning (Trivy, Apache-2.0) · least-privilege DB roles · security headers / CSP · malware scan of uploads (if uploads exist) · deleting one tenant's data on request · break-glass admin access and who holds it |
| **Concurrency** | expected users, requests/sec, peak · two people editing one record (locking or version check) · retries and duplicate requests (idempotency keys) · background work and its queue (Postgres job table with `FOR UPDATE SKIP LOCKED`, or Redis) |
| **Performance** | response-time targets: API p95, page load, mobile start-up · caching: what, where, for how long · DB connection pooling (PgBouncer transaction mode rules) |
| **Images and files** | present at all? types and sizes · upload direct to the bucket (signed URL) or through the API · compress/resize where: on the device, in a background worker, or at the CDN · storage: Cloudflare R2, S3 or OCI Object Storage · public or private (signed reads) · CDN in front · retention |
| **Real-time** | none, polling, server-sent events or websockets |
| **Mobile offline** | what works without signal, and how conflicts resolve on sync |
| **Multi-region** | one region at launch or several · data-residency needs per customer · cross-region backup copy · a standby database in a second region · CDN for global users · cost of each option |
| **Billing (founder: must-ask)** | needed at launch? provider: Clerk Billing, Stripe or Paddle (verified at the time; ask-before-new-service applies) · plans and **entitlements enforced on the server**, never only in the UI · webhook signature verification and idempotency · trials, failed payments (dunning), tax/VAT, invoices · billing screens in step 7 |
| **Search, email, notifications** | needed? built in, or a service? |
| **Service mesh (Istio?)** | needed at all? (mTLS between services, L7 policy, traffic splitting, retries). Options, facts from istio.io 2026-11-07, Istio 1.31.4, Apache-2.0: **none** (NetworkPolicy + app-level auth); **Istio ambient mode** (no sidecar: a per-node Rust `ztunnel` for L4 mTLS, plus optional per-namespace Envoy "waypoint" proxies for L7; resource cost "Small" vs sidecar "Large"; p90/p99 latency ~0.16–0.20 ms at L4 vs ~0.63–0.88 ms for sidecar; production-ready for single-cluster since 1.22; multi-cluster and multi-network still beta; no VMs, no EnvoyFilter); **Istio sidecar mode** (an Envoy proxy in every pod; full features including stable multi-cluster and VMs). **Recommended answer (call):** no mesh at launch unless a requirement demands one; if one is needed, **ambient**. Ambient joins without changing application pods, so it can be added later at low cost. Choose **sidecar** only for multi-cluster / multi-region active-active or VMs (ties to the multi-region answer). The mesh's Gateway API support can also serve as the in-cluster entry point behind Cloudflare Tunnel |
| **Availability and recovery** | uptime target · RPO (data you can afford to lose) · RTO (time to recover) |

### 5.3 Tenant lifecycle and compliance (mandatory when step 0 answered "multi-tenant")

Decided in step 4, designed in steps 5 and 7, and built and tested in step 9. Output:
`docs/architecture/TENANCY-LIFECYCLE.md` + one ADR per item.

| Stage | What must be designed and tested |
|---|---|
| **Create** | Sign-up → Clerk organisation → our `tenants` row → default roles, settings and onboarding state, all **in one transaction**. A half-created tenant is impossible |
| **Sync and repair** | Clerk webhooks are signature-verified and idempotent (replaying an event is a no-op). A scheduled **reconciliation job** compares Clerk with our tables and repairs drift from missed events. The reconciliation run is part of the test suite |
| **Suspend / offboard** | Suspension blocks sign-in and API keys but keeps data. Offboarding starts the retention clock. Both are recorded in the audit log |
| **Export** | A tenant (and a person, for data-subject requests) can export their data in a documented machine-readable format |
| **Delete** | Deletion removes live data and files. The ADR states how long deleted data survives in backups and WAL, and that restores re-apply deletions. The privacy policy states the same period |
| **Legal surface** | Terms of service, privacy policy, data-processing agreement, sub-processor list (Clerk, email, analytics, storage, billing) and cookie consent where analytics or marketing cookies exist. These are pages on the website (step 7 designs them, step 9 builds them). Legal text is the founder's responsibility; the workflow only makes sure the pages, links and consent mechanics exist |
| **Support access** | An admin/support console: who may see a tenant's data, impersonation only with an audit-log entry and a visible banner, and no shared logins |
| **Per-tenant limits** | Quotas and rate limits per tenant, not only per IP at the edge, so one tenant cannot starve others |

### 5.4 Who asks what: no question twice (call)

Several pieces ask questions: superpowers' brainstorming, the step-0 intake, grill-me and step 4. Each kind of
question has **one owner**:
- step 0 (`start`): platform questions only (§5.1)
- step 2 (grill-me): product decisions
- step 4 (`system-design`): system and stack questions (§5.2)
- **superpowers brainstorming runs only inside a wave, for one feature's design.** It must read `decisions/`,
  `GLOSSARY.md` and `SPEC.md` first, and ask only what is undecided.

This is enforceable because superpowers states that instructions in `CLAUDE.md` take precedence over its skills
(`using-superpowers`, "User Instructions"). Pavedline's `CLAUDE.md` template carries this rule.

### 5.5 Website and blog: the SEO path (founder)

**Principle (facts, 2026-11-07):** Core Web Vitals "good" = LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at the 75th
percentile, mobile and desktop; INP replaced FID in 2024 (web.dev/articles/vitals). Industry coverage of Google's
2026 AI-search guidance says classic SEO is the foundation for Google's AI features, and that `llms.txt` has no
ranking effect in Google Search (secondary sources; the exact wording is re-checked on developers.google.com when the
skill is written). So Pavedline does **classic, excellent SEO** and no "AI tricks". `llms.txt` is optional, for
other agents only.

| Step | What is done for the website and blog |
|---|---|
| 1 Market | SEO research: competitors' sitemaps and page structure (Playwright MCP), the topics they cover, the queries and search intent from free sources (autocomplete, "people also ask", Google Trends), content gaps → `docs/business/SEO-STRATEGY.md` (topic clusters, pillar pages, a target query per page) |
| 3 Spec | site map and URL structure (short, stable, readable; blog under `/blog`: call), every page's search intent and conversion goal |
| 4 System design (must-ask, added to §5.2) | rendering: site and blog fully server-rendered, static or incremental (call) · content source: MDX in git, or a headless CMS for non-developer writers · languages and `hreflang` · analytics: Search Console only, or self-hosted Umami (MIT; a new service, so ask first) · image delivery (AVIF/WebP, fixed dimensions) · **AI-crawler policy** in robots.txt (allow or block each AI crawler: a business decision) |
| 7 Figma | site and blog templates built for Core Web Vitals: space reserved for every image (CLS), one clear LCP element, font loading plan, readable article layout, an author box (real author and credentials), a social-share (Open Graph) image template |
| 9 Build: **SEO gate** for `apps/site` (CI fails below it) | Lighthouse CI (Apache-2.0) on mobile: **SEO 100 · Performance ≥ 95 · Accessibility ≥ 95 · Best Practices ≥ 95**, lab LCP ≤ 2.5 s, CLS ≤ 0.1 (call: thresholds) · every page has a unique title and description, a canonical URL, Open Graph tags, and valid JSON-LD (Organization, WebSite, Article, BreadcrumbList) · `sitemap.xml` and `robots.txt` are generated (Next.js `sitemap.ts` / `robots.ts`) and tested · redirects map, real 404/410 · broken-link check (lychee, Apache-2.0) · alt text on every image · **staging is never indexable** (a `noindex` header + robots block, tested) |
| 10 Deploy | only production is indexable · sitemap submitted to Google Search Console and Bing Webmaster Tools (founder signups) · after the first deploy, check that staging is still blocked |

**The operation process: "Grow", a standing loop beside the waves (call).** A new `growth` agent (the 9th) with the new
skills `seo-foundation` (the technical items above) and `content-ops` (the publishing loop), plus Anthropic's marketing
plugin (`seo-audit`, `content-creation`, `draft-content`, `performance-report`, Apache-2.0):
1. **Publish:** brief (target query, intent, outline) → draft → **human edit and fact-check; the founder approves**
   (generic AI text is the main risk named in Google's guidance) → SEO checklist → PR → deploy → request indexing.
2. **Weekly:** content calendar in `docs/growth/calendar.md`.
3. **Monthly:** Search Console review (queries, click rate, impressions, pages not indexed, real-user Core Web Vitals)
   + `seo-audit` → `docs/growth/YYYY-MM.md` with actions.
4. **Quarterly:** refresh posts that are losing traffic, merge or remove thin ones, re-check internal links.

### 5.6 Step 11: Go to production (cloud), asked once, at the end (founder)

**Principle:** build everything on local Kubernetes and bind to the cloud **once**, at the end. Steps 0–10 make
only **portable** decisions ("Postgres 16, S3-compatible storage, Kubernetes with Gateway API, one region plus a
backup copy"). Step 11 maps them onto real infrastructure. Decisions that change the *design* stay early (step 0:
database in Kubernetes or managed; step 4: multi-region, data residency); only "where exactly" waits for step 11.

**Accounts are asked for just in time, never all at the start:** Figma at step 7, Clerk development keys at the
first auth slice, Apple and Google developer accounts before the first mobile build, production accounts at step 11.
The README lists all of them up front, so nothing is a surprise.

**Step 11, in order:**
1. **The question:** "Everything works on local Kubernetes. Is it time to go to production in the cloud?" Nothing
   moves until the founder says go.
2. **Infra intake, "what do you already have?"** Cloud account and provider · existing cluster or new · regions
   (from the step-4 multi-region decision) · domain and DNS (Cloudflare?) · container registry · secrets store ·
   object storage · managed database (if step 4 chose one) · email sending domain · budget ceiling. Output:
   `docs/production/INFRA.md` + an ADR per binding.
3. **"What I need from you":** `docs/production/NEEDS.md`. Each item also goes into `STATE.md ▶ WAITING ON YOU`:
   accounts to create, logins, approvals, every `terraform apply` (always the founder's), and secrets placed directly
   in the vault, **never pasted into chat**.
4. **Provision:** the agent fills the infra profile (Terraform). The founder applies it, and an applied plan shows
   `0 to destroy`. ArgoCD is bootstrapped.
5. **Cloud staging first (founder):** deployed through the same GitOps path and verified against everything local
   could not prove: real DNS and TLS, Cloudflare Tunnel, cloud IAM and vault, a backup **and a real restore**, the
   two alerts (§10.9), email deliverability (SPF/DKIM/DMARC), and running pods on the release SHA. Staging holds
   generated data only and is never indexable.
6. **Production:** promoted from the verified staging SHA through a GitOps PR, verified the same way. Then the
   mobile store submissions, the Search Console and Bing sitemap submissions, and the legal pages live.
7. **Launch checklist** (`docs/production/LAUNCH.md`), then the founder's final **"go live"**. The Grow loop (§5.5)
   starts.

After launch, waves continue: build → local → cloud staging → production, each promotion by PR.

**Stack packs (`stacks/<name>/`), applied at step 6 once step 4 has decided the stack:** one directory per supported stack, holding its Dockerfiles, Helm values, CI jobs,
test/typecheck commands, `RUN.md` fragment and the list of stack skills it switches on. v1 ships **`nextjs-fastapi`** (name kept short; it includes the mobile app). It is a monorepo:
`apps/web` (Next.js web app), `apps/site` (Next.js website + MDX blog; a separate deployment so the public site
caches and releases independently of the app: call), `apps/mobile` (Expo), `services/api` (FastAPI), and
`packages/` (shared TypeScript API client generated from the OpenAPI contract, design tokens exported from Figma,
glossary strings).
- **Mobile: Expo (React Native).** Verified 2026-11-07: reactnative.dev says "if you're building a new app with React
  Native, we recommend using a Framework" and calls Expo "a production-grade React Native Framework". React Native
  docs default to v0.88. Same language (TypeScript) and same component model as the web, so tokens, API client and
  glossary are shared. Builds run in GitHub Actions (macOS runners for iOS). **Expo's hosted EAS build service is a
  new paid-tier service and is not used unless the founder approves it (call; ask-before-new-service rule).** Mobile
  ships through the App Store and Google Play, not GitOps: the store submission is a founder step.
- Next.js **≥ 16.3**. Verified: from 16.3, `next dev` generates `AGENTS.md`/`CLAUDE.md` and bundles version-matched
  docs in `next/dist/docs/`, which is why Vercel retired its `next-best-practices` skill. Latest is v16.4.5,
  2026-11-03. Its generated agent file lives in the Next.js app folder, not the repo root, so the root `CLAUDE.md`
  stays at about 150 lines (where `next dev` writes it is to be verified in the build).
- Next.js workflow skills from `vercel/next.js/skills` (MIT; includes a Claude plugin manifest): `next-dev-loop`,
  `next-bundle-optimizer`, `next-cache-components-adoption`/`-optimizer`, `next-partial-prefetching-*`.
- `vercel-labs/agent-skills`: `react-best-practices`, `composition-patterns`, `web-design-guidelines`,
  `react-view-transitions`, and `react-native-skills` (always: every product has a mobile app). There is no licence file detected, so
  install only, never vendor. The Vercel-deploy skills are excluded, because deploys go through GitOps.
- new `fastapi-service` skill (no well-established FastAPI agent skill exists, checked 2026-11-07), written from the
  Python tooling proven in production: uv workspace, ruff, pyright strict, Pydantic v2, import-linter
  boundaries, Alembic with explicit-SQL invariants, an in-image boot check, and money as `int`/`Decimal`, never float.
- optional: `vercel/next-devtools-mcp` (no licence file detected; optional only).

**Light path (call):** a small change (a bug fix, a copy edit) skips steps 1–8 and runs step 9 only. Ceremony
scales with size.

## 6. Memory and records: how a fresh session resumes

**Files, in reading order** (product repo):

1. `CLAUDE.md`, about 150 lines or fewer: what the project is, the authority chain, the commands, and pointers. No
   history.
2. `STATE.md`, **hard cap 60 lines (hook-enforced):** `STEP` · `LAST` · `NEXT` · `LEFT BEHIND` (red/unrun tests,
   unfixed defects, carried findings) · `WAITING ON YOU` (only steps the agent cannot take; removed only on the
   founder's word) · `OWNER` (the single writer) · `MODE` (solo | team; a missing MODE is treated as review-only).
3. `decisions/NNNN-title.md`: ADRs. Dated, append-only. A superseded ADR gets `Superseded by NNNN` and is
   never edited.
4. `GLOSSARY.md`: one name per concept, used in the UI, API, database and code. The gate-2 reviewer checks it.
5. `handoff/<branch>.md`: one file per working branch. The owner folds it into `STATE.md` on merge, then deletes it.
   Never a shared file that every lane edits.
6. `docs/archive/`: history moves here automatically. A hook moves overflow from `STATE.md` instead of letting it
   grow.

**Rules:** one writer for `STATE.md` and the decision index (solo: the main session; team: the person or session on
the `OWNER` line). Other sessions work in their own `git worktree` and write only their hand-off file. Timestamps come
from `date`, never estimated. Every state-changing turn commits and pushes. Records merge at milestones, not every
turn. A session start prints a short **opening block** (state, recommended next step, what needs approval). A session
end prints a short **closing block** (done, changed, next, waiting on you, clear-safe yes/no).

**Wave protocol (kept from the source workflow):** one approval starts one wave. The wave ends by verifying, updating the
records, stating the next recommended wave, and **stopping**. The next wave is re-derived from the files, not
inherited.

**Team mode differences (call):** approvals move to GitHub (PR reviews, `CODEOWNERS`, required checks,
branch protection). Tickets are GitHub issues created from the spec. `WAITING ON YOU` names a person per item.

## 7. Agents and model policy

Nine agents (`plugins/pavedline/agents/`; `growth` added by §5.5), each with one job. Every subagent prompt is self-contained (mode, branch,
files to read, the question, report format).

| Agent | Job | Default mode |
|---|---|---|
| researcher | market, competitor and vendor facts; cites a URL for every claim; definite / inferred / unknown | read-only |
| architect | data, API, system and Helm/GitOps design | writes docs only |
| designer | Figma design system + screens | writes Figma + design docs |
| design-verifier | blind check of words, data, states and accessibility; never approves visuals | read-only |
| builder | implements one slice, in its own worktree | execute (approval quoted in the prompt) |
| reviewer | blind gate 2 + 3: reads the diff, never the summary; `VERDICT: APPROVE / REJECT` | read-only |
| adversary | blind gate 3b: tries to break the code with concrete inputs; required on security-sensitive slices | read-only |
| deployer | opens the GitOps PR, syncs, verifies the running state | execute |
| growth | SEO foundation, content publishing loop, monthly Search Console review (§5.5) | writes content drafts; publishing needs the founder |

**Model policy lives in one file:** `plugins/pavedline/config/models.yaml` (call). Default: orchestrator and designer
`opus`, everyone else `sonnet`, never `haiku` (this matches the founder's current rule). Each report's first line records
the model that actually ran. A subagent that fails is re-dispatched once. Third-party reviewer agents are never used,
because their own model settings would bypass `models.yaml`. Their skills may be used as checklists.

## 8. Quality gates (per build slice)

Kept from the source workflow, enforced by `quality-gates` + a PR check:
1. **TDD:** red first.
2. **Code review:** a blind reviewer reads the diff. A reject means re-work, never arguing past it.
3. **Security review:** tenancy, auth, secrets, injection, sensitive data in logs.
3b. **Adversarial review:** required when a slice touches auth, tenancy, IAM, infra, CI, secrets, input parsing,
   money or migrations. The threat model and stop rule are given in the first prompt. A fix round gets **one narrow
   re-check**, and a full new review only when a high-severity finding was fixed.
4. **Verification:** typecheck and the tests of the touched packages. The **full suite runs once, at the merge
   gate**, on a branch up to date with main. Migrations are applied to a throwaway Postgres in CI. **Every image boots
   in CI** before it ships. Lint counts as evidence only if a lint config exists.
5. **Merge:** squash, on the remote. Then post-merge verification at deploy (§10.4).

PR line (CI fails if it is missing or malformed):
`Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓`.
`✗` is not a valid value. Every unfixed finding is listed as `accepted — <reason>`.

### 8.1 The automated layer under gates 2 and 3

The AI reviewers judge design, logic and tenant safety. **Tools that never get tired** catch the rest. All are free
(licences checked on GitHub, 2026-11-07). **A failing scanner fails CI, exactly like a failing test**, and the
reviewers receive the scanner output with the diff.

| Layer | Tool (licence) | Catches |
|---|---|---|
| Code quality, TypeScript | Biome (Apache-2.0) or ESLint, plus `tsc` strict | style, likely bugs, unused code, type errors |
| Code quality, Python | ruff + pyright strict + import-linter boundaries | lint, type errors, layering violations |
| Security of first-party code | CodeQL (GitHub code scanning, free for public repos) and Semgrep (LGPL-2.1, used as a tool, not linked) | injection, unsafe patterns, taint flows |
| Dependencies | **Renovate** (AGPL-3.0, run as a CI tool) for updates; Dependabot security alerts (GitHub built-in) + Trivy (Apache-2.0) for known vulnerabilities | outdated and known-vulnerable packages, images, charts, actions |
| Containers | Trivy | vulnerable base images and OS packages |
| Infrastructure as code | Checkov (Apache-2.0) | insecure Terraform, Kubernetes manifests and Helm values |
| Running application | OWASP ZAP baseline (Apache-2.0) against the local cluster | missing security headers, exposed endpoints |
| Secrets | gitleaks (MIT) | committed keys and tokens |
| Tenancy | the RLS schema check + cross-tenant leak fixture (§11) | a table or path that escapes tenant isolation |

**The lint and format configs ship with the stack pack from the first commit.** A lint step without a config does
not run, so it cannot count as evidence. Gate 4 cites lint only when its config exists and CI ran it.

## 9. Diagrams

- Every folder that holds architecture has `ARCHITECTURE.dot`: repo root, `infra/`, `infra/k8s/`,
  `infra/terraform/`, each service, `docs/data/` (`erd.dot`), `docs/architecture/`. **Every plan has its own `.dot`.**
- GitHub does **not** render `.dot` (verified: GitHub's diagram docs list Mermaid, GeoJSON, TopoJSON and ASCII STL).
  So CI runs `dot -Tcanon -o /dev/null` (validate; exits 1 on a syntax error. `-Tnull` is not available in every Graphviz build: verified absent in Graphviz 16.1.0, 2026-11-07) and `dot -Tsvg` (render), and commits the SVG next to the source. READMEs
  embed the SVG with light and dark variants.
- **Drift check (hook + CI):** a change under a folder that has an `ARCHITECTURE.dot`, with no change to that `.dot`,
  fails. The fix is to update the diagram, or to state `diagram unchanged: <reason>` in the PR.
- A shared style file (`docs/diagram-style.md` + a `.dot` snippet) keeps colours and shapes consistent.

## 10. Production architecture templates

### 10.1 GitOps: the backbone
Git is the only way anything reaches a cluster. Infrastructure (Terraform), cluster add-ons, apps, Helm values and
image tags all live in git. ArgoCD reconciles. The `deployer` agent opens PRs and never runs `kubectl apply` or
`helm upgrade` by hand. A rollback of code and manifests is a git revert; migrations and mobile need more (§10.4b). Kept from the source workflow:
- **ApplicationSets** over `k8s/addons/*`, auto-sync + self-heal.
- **ApplicationSets** over `k8s/apps/*`, **manual sync** with `preserveResourcesOnDeletion: true`, so that renaming a
  folder can never delete a database.
- CI builds the image and commits the tag bump; it never syncs.

### 10.2 Helm base chart (`templates/infra/helm/base-chart/`, a library chart)
Every workload gets these defaults: liveness/readiness/startup probes · resource requests and limits · a
PodDisruptionBudget · an optional HPA · topology spread across nodes · non-root, read-only root filesystem, dropped
capabilities, a seccomp profile · a dedicated least-privilege ServiceAccount per workload · NetworkPolicy
default-deny + explicit allows · a priorityClass · migrations as an ArgoCD **PreSync Job**, so the schema exists
before the new image starts · per-environment values (`values-staging.yaml`, `values-production.yaml`). Covered by
`helm lint` + `helm template` + a schema test in CI.

### 10.3 Database: chosen at step 0 (founder)
- **In Kubernetes:** a CloudNativePG cluster (verified current: v1.30.1, 2026-09-23). It has 3 instances with
  synchronous replication and anti-affinity, and backups through the **Barman Cloud CNPG-I plugin** (verified:
  `cloudnative-pg/plugin-barman-cloud` v0.15.1) to S3-compatible object storage. A PgBouncer pooler runs in
  transaction mode. A **restore drill script** is included and is part of production readiness.
- **Managed service:** the chart takes the connection string from a Kubernetes Secret, plus a network allow-list,
  with nothing else in-cluster. The ADR records the provider, the backup policy and the restore test.
- Both: a separate app DB role and migration DB role (least privilege), and reversible migrations.

### 10.4 Deploy and post-deploy verification (`deploy` skill)
1. Migrations on staging, then production, **before** the image syncs.
2. CI green, and the tag-bump commit matches the merge SHA.
3. Manual sync of each changed app.
4. **Verify the running state:** pods run the new SHA, 0 restarts, health endpoint ok, plus one change-specific
   read-only check that the PR names.
5. On failure: revert and record it. Before launch, "staging" is the local cluster; at step 11 a **cloud staging** environment is created first and every later release passes through it (founder).

### 10.4b Release compatibility: why "rollback = git revert" is not enough

A git revert rolls back **code and manifests**. It does **not** roll back a migration that already ran, and it does
not reach mobile apps already on people's phones. So:
- **Expand / contract migrations.** A release only **adds** (new columns, tables, nullable fields, and both shapes
  accepted). Removal of the old shape ships in a **later** release, after nothing uses it. So the previous image
  always runs against the new schema, and reverting the image is safe. Each migration also ships a tested `down` path,
  and the rollback is rehearsed on the local cluster and staging.
- **API versioning.** The public API is versioned (`/v1`). A breaking change needs a new version and a documented
  deprecation window. The OpenAPI contract is diffed in CI, and a breaking diff without a version bump fails.
- **Mobile minimum version.** The API exposes a minimum supported app version. The app checks it on start and shows
  a blocking "please update" screen below it (designed in step 7). Old app versions must keep working until the
  minimum is raised.
- **Staged rollout.** Mobile releases use the stores' phased rollout. Risky web and API features go behind **feature
  flags** (a simple flags table first; a flag service only via the ask-before-new-service rule).
- **Store lead time.** The plan reserves time for App Store and Play review before any date that depends on mobile.

### 10.5 Infra profile: OCI/OKE (`templates/infra/terraform/profiles/oci-oke/`)
Derived from a production OCI setup with **every identifier turned into a placeholder**: VCN, subnets, OKE (arm64
Ampere node pools with labels/taints in native Terraform, no cloud-init), IAM, Vault → Kubernetes Secret, the
object-storage backup bucket and its credentials. State-protection rules are in the profile README: an applied plan must show
`0 to destroy` and nothing replaced, there are no state surgery commands, and removals are calculated item by item.
Cloudflare Tunnel (`cloudflared` add-on) is the ingress: no load balancer, no inbound ports. Cluster access through
Teleport is an optional add-on.

### 10.5b Local Kubernetes: the main test bed (founder)
- **Facts (2026-11-07):** Apple Silicon Macs are arm64, the same architecture as OCI Ampere nodes, so production
  images run locally unchanged. kind v0.33.0 (Apache-2.0), Colima v0.10.3 (MIT), Tilt v0.37.8 (Apache-2.0).
  **ingress-nginx is retired** by Kubernetes, with no security fixes after March 2026 (kubernetes.dev blog,
  2025-11-12), so the templates use **Gateway API** or port-forward, never ingress-nginx.
- **Default (call):** Colima as the container runtime + **kind** as
  the cluster. Docker Desktop or OrbStack work too, if the user already has one.
- **New `local-cluster` skill:** the agent creates `pavedline-<project>` and installs the **same** add-ons as
  production from the **same** GitOps manifests (ArgoCD, CNPG, the apps). An S3-compatible store for the backup and
  restore drill is chosen and verified when the skill is written. The skill tears the cluster down afterwards.
- **Two loops:** *fast*, where Tilt rebuilds and live-reloads in seconds; *GitOps*, where ArgoCD inside the local
  cluster syncs from the branch, proving the manifests deploy.
- **Safety:** on the local cluster the agent may apply and destroy freely. **A hook blocks every mutating
  `kubectl` / `helm` / `argocd` command whose context is not `kind-pavedline-*`**, which protects production.
- **CI runs the same script** on GitHub's arm64 runners on every PR, so local and CI give the same result.
- **What local cannot prove** (stated in the docs): Cloudflare Tunnel, real DNS/TLS, cloud IAM/Vault, real multi-node
  failure, real load. These belong to the user's own staging cluster.

### 10.9 Operations basics (minimum for a production SaaS)
- **Backups for every datastore**, not only Postgres. Object-storage buckets get versioning and a lifecycle policy.
  A managed database's restore test is a gate, not a note: the restore is run and recorded before launch.
- **Email deliverability.** SPF, DKIM and DMARC on the sending domain, bounce and complaint handling, and an
  unsubscribe link on every non-transactional email. Checked before the first real email.
- **Secrets rotation.** Every secret has an owner and a rotation procedure in `SERVICES.md`. Break-glass access is
  written down in `RUN.md`: who holds it and how it is audited.
- **Staging never holds production data.** Staging is seeded with generated data. A copy of production into staging
  is forbidden.
- **Two alerts only (founder; the one exception to "observability is out of scope"):** an **uptime check** on the
  public endpoints and an **alert when a backup fails**. Everything else waits for the observability agent.
- **Cost guardrail.** A cloud budget alarm is configured with the infra profile. This is not a per-tenant cost model
  (the founder ruled that out as blocking); it only stops a runaway bill.

### 10.6 CI templates (`templates/.github/workflows/`)
- arm64 image build on native runners + tag bump
- unit tests + typecheck on PRs
- DB tests (throwaway Postgres built from the migrations) at the merge gate only
- `.dot` validate/render + drift check
- secret scan (gitleaks, MIT; call)
- Renovate (self-run in CI, weekly) for every pinned version (§18.8)
- Helm lint/template
- the gates-line check
- `claude plugin validate` (in Pavedline's own repo)

### 10.7 Secrets
Never in git. The OCI profile uses OCI Vault → Kubernetes Secret via Terraform, and the Vault value is authoritative.
`SERVICES.md` records **where** each key lives, never the key. Hooks block reading `.env*` and writing anything that
matches a secret pattern.

## 11. Skills, dependencies, hooks and the cockpit mod

**Dependencies, installed, not copied (call: keeps licences clean and updates flowing). All verified on GitHub
2026-11-07:**

| Plugin / tool | Licence | Used for |
|---|---|---|
| obra/superpowers (v7.0.2) | MIT | build discipline (TDD, plans, worktrees, review, verification) |
| mattpocock/skills | MIT | grilling, grill-with-docs, to-tickets, retro |
| anthropics/knowledge-work-plugins (product-management) | Apache-2.0 | competitive-brief, synthesize-research |
| nextlevelbuilder/ui-ux-pro-max-skill (v2.15.0, needs Python 3) | MIT | style/palette/font reference for step 7 |
| Figma official plugin + MCP | Figma terms; **a Full seat is needed to write to the canvas** | step 7 |
| microsoft/playwright-mcp | Apache-2.0 | competitor-site scraping (default) |
| unclecode/crawl4ai | Apache-2.0 (attribution required) | optional bulk crawl |
| pbakaus/impeccable | Apache-2.0 (verified 2026-11-07) | design critique |

**Borrowed with credit, not installed:** sickn33/agentic-awesome-skills `saas-multi-tenant` (MIT) is the base of
`multi-tenancy`. supabase/agent-skills `supabase-postgres-best-practices` (MIT) is a reference for `db-schema`. ECC
(MIT) is *ideas only*: project memory, session-summary hooks, the learning loop and guard hooks. ECC is **not
installed**, because it overlaps superpowers and its agents declare their own models, which conflicts with the single model-policy file.

**New skills (30: + `seo-foundation`, `content-ops`, `local-cluster`, `go-to-production`; the earlier "21" was a miscount; `doctor` added by §18.4; `system-design` + `backend-evaluate` added with step 4):** start · architecture-intake · state · competitor-teardown ·
pricing-model · market-size · spec · system-design · backend-evaluate · domain-model · db-schema · multi-tenancy · api-contract · system-architecture ·
helm-base-chart · gitops · threat-model · fastapi-service (stack pack) · design-system-contract · plan-graph · quality-gates · deploy · lessons · seo-foundation · content-ops · local-cluster · go-to-production · diagram · project-registry
· doctor (`diagram`, `project-registry` and `doctor` are cross-cutting). Each skill does one job, has a short `SKILL.md`, and keeps
detail in `references/`.

**`multi-tenancy` + `db-schema`: lessons from production, added on top of the base:**
- a tenant key on every tenant table, enforced by a migration CI check
- row-level security as the backstop, set with **`SET LOCAL` inside a transaction**, because session `SET` and
  session advisory locks break under PgBouncer transaction mode
- a cross-tenant leak test at the merge gate
- reversible migrations applied before the image
- big sums read as text, never overflowing BIGINT
- separate admin roles and routes
- tenant provisioning in one transaction

**Tenant isolation: the non-negotiable rules (enforced, not advised):**
- The runtime database role **does not own** any table and **has no `BYPASSRLS`**. Migrations run under a separate
  owner role. Admin and reporting access uses a third, audited role.
- Every tenant table has `tenant_id NOT NULL`, **`ENABLE` and `FORCE ROW LEVEL SECURITY`**, and a policy on
  `current_setting('app.tenant_id')`. **A CI check reads the real schema and fails if any tenant table lacks any of
  these.** Global tables are listed explicitly in an allow-list.
- The tenant is set with **`SET LOCAL` inside the transaction** for every request **and every background job,
  webhook handler and scheduled task**. Session `SET` and session advisory locks are forbidden under PgBouncer
  transaction mode.
- File storage keys start with the tenant id, and signed URLs are issued only after the same tenant check.
- **The cross-tenant leak test is a fixture, not a sample.** Two tenants with data; every API endpoint, every job
  type and every file path is exercised as tenant A against tenant B's ids, and must fail. It runs at the merge gate.
  A new endpoint or job without leak-test coverage fails CI.

**Competitor scraping rules:** Playwright MCP by default. Respect robots.txt and each site's terms. **Review sites
(G2, Capterra) only through manual export or official APIs.** G2's terms could not be verified, so the kit does not
assume scraping is allowed. Firecrawl self-host is documented only, with an AGPL-3.0 warning.

**Hooks (settings hooks; they work everywhere, including `claude -p` and CI):** block `.env*` reads and
secret-pattern writes · `STATE.md` 60-line cap and auto-archive · `.dot` drift warning · `CLAUDE.md` size warning
(about 150 lines) · gates-line check on PR creation · block `--no-verify` and force-push to main · session-start reads
`STATE.md` and prints the opening block.

**`pavedline-cockpit`, an optional mod (call).** Facts: mods run inside Claude Code (v2.1.287 or later), can draw a
pane and add instant `/commands`, are **not sandboxed**, and draw nothing in `claude -p` or cloud sessions. So the
cockpit is a **separate, optional plugin**: a pane showing step, next action, the open slice's gates and
`WAITING ON YOU`, plus `/pavedline-status`. **Nothing depends on it.** Every rule is a settings hook.

## 12. The public face: README and docs

**README top to bottom:**
1. Name + tagline + badges (licence, version, CI).
2. **The flow diagram (SVG from `docs/flow.dot`), light and dark.**
3. "Why Pavedline": the gap is that no open kit takes a serious product through a complete, real SDLC to verified
   production through GitOps. Three or four lines, then the thirteen steps.
4. "What you get": skills, agents, hooks, templates and infra, as a short table with links.
5. **"This is for serious projects": requirements, shown plainly:**

| You need | Why | Cost note |
|---|---|---|
| GitHub account (+ GHCR) | repo, CI, images | free tier works for public repos |
| Claude Code (v2.1.287+ for the optional cockpit) | runs the factory | Claude plan or API |
| Figma, **Full seat** | step 7 writes to the canvas | paid |
| **Apple Developer Program** | publish the iOS app | yearly fee |
| **Google Play Console** | publish the Android app | one-time fee |
| Google Search Console + Bing Webmaster Tools | submit sitemaps, monthly SEO review | free |
| A Kubernetes cluster: OCI/OKE profile included (or bring your own) | runs staging + production | cloud bill |
| A domain + Cloudflare account | DNS, TLS, Tunnel ingress | domain cost |
| S3-compatible object storage | database backups | small |
| Local tools: git, gh, Node 22, Python 3 + uv, Graphviz, Docker, kubectl, helm, terraform | build, test, diagrams | free |
| Optional: managed Postgres, Teleport | per step-0 answer | varies |

6. Quick start: install → `/pavedline:start` → what happens in the first hour.
7. **"Who's behind this":** Marwan Ghubein: DevOps, DevSecOps, AI platform engineering and **AI architecture**
   experience. Pavedline is built from running a production platform end to end (Kubernetes, GitOps, security,
   agent-driven delivery). Link: [LinkedIn](https://www.linkedin.com/in/marwan-ghubein/). No employer is named
   (founder, 2026-11-07).
8. Licence, contributing, credits (every dependency and borrowed skill).

### 12.1 Credits on GitHub (founder)

The README carries a **"Built on the shoulders of"** section. It is a short table, near the top, after "What you get",
so people see exactly what they are installing and who made it. `CREDITS.md` holds the full list. A
`THIRD_PARTY_NOTICES.md` keeps the original copyright and licence text of anything *adapted* into this repo; MIT and
Apache-2.0 both require that. A CI check fails if a dependency is added to the marketplace or `doctor` without a
`CREDITS.md` row. Licences verified on GitHub on 2026-11-07:

| Project | Author | Licence | How Pavedline uses it |
|---|---|---|---|
| superpowers | Jesse Vincent (obra) | MIT | **installed**: the build-discipline backbone |
| skills (grilling, grill-with-docs, to-tickets, retro) | Matt Pocock | MIT | **installed**: step 2 grill, team tickets, retros |
| knowledge-work-plugins (product-management) | Anthropic | Apache-2.0 | **installed**: competitive brief, research synthesis |
| ui-ux-pro-max-skill | nextlevelbuilder | MIT | **installed**: step 7 style reference |
| impeccable | Paul Bakaus | Apache-2.0 | **installed**: design critique |
| Figma plugin + MCP | Figma | Figma terms | **installed**: step 7 |
| Next.js workflow skills | Vercel (vercel/next.js) | MIT | **installed** (stack pack) |
| agent-skills (React, web design, React Native) | Vercel Labs | no licence file detected | **installed only, never copied** |
| Clerk skills | Clerk | no licence file detected | **installed only, never copied** (stack pack) |
| playwright-mcp | Microsoft | Apache-2.0 | **installed**: competitor research |
| crawl4ai | unclecode | Apache-2.0 (attribution required) | **optional**: bulk crawl; README attribution line |
| saas-multi-tenant skill | sickn33 (agentic-awesome-skills) | MIT | **adapted with credit** into `multi-tenancy` |
| supabase-postgres-best-practices | Supabase | MIT | **reference with credit** for `db-schema` |
| Everything Claude Code (ECC) | Affaan Mustafa | MIT | **ideas only**: project memory, session summaries, guard hooks, learning loop |
| spec-kit | GitHub | MIT | **ideas only**: the constitution → spec → plan → tasks chain |
| BMAD-METHOD | BMad Code | licence not machine-detected (to check before citing beyond "inspired by") | **ideas only**: right-size the process |
| Argo CD · CloudNativePG + barman-cloud plugin · Trivy | Argo Project · CNPG · Aqua Security | Apache-2.0 | **used by the templates** |
| gitleaks | Gitleaks | MIT | **used by CI** |
| Graphviz | Graphviz authors | EPL (to confirm) | **used** for every `.dot` |

Wording rule: "installed" means the user installs it from its own source, and Pavedline only references it.
"Adapted" means code or text was changed and included, with the original notice kept. "Ideas only" means no code
or text was copied.

### 12.2 Installable, not just downloadable (verified against the Claude Code plugin docs, 2026-11-07)

Pavedline is a **Claude Code plugin marketplace** hosted in its own GitHub repo (`Marwan-G/pavedline`, personal
account: founder). Users **install** it. They do not download or copy it:

```
/plugin marketplace add Marwan-G/pavedline
/plugin install pavedline@pavedline
/plugin install pavedline-cockpit@pavedline      # optional status pane (a mod)
```

- **Dependencies install with it.** `plugin.json` declares superpowers, Matt Pocock's skills, Anthropic's
  knowledge-work-plugins and the others as `dependencies`. They install automatically because Pavedline's
  `marketplace.json` lists their marketplaces in `allowCrossMarketplaceDependenciesOn` (verified behaviour). Skills
  installed with `npx skills` (Vercel, Clerk) cannot be declared, so `/pavedline:doctor` detects them and prints the
  exact install command.
- **Updates.** Each release is a git tag `pavedline--v<version>` (made with `claude plugin tag`), so users update
  with `/plugin update` and can pin a version. `CHANGELOG.md` says what changed.
- **Starting a product.** In a new empty repo, `/pavedline:start` copies the templates (records, GitOps core) and
  begins step 0. The stack-specific templates arrive at step 6.
- **Later (optional):** submit to Anthropic's plugin directory, once v1.0 is proven.
- **Also documented:** loading from a local clone with `claude --plugin-dir`, for contributors.

**`docs/`** has one page per step (what goes in, what comes out, who approves, an example), plus solo vs team,
lessons learned (§14), extending (new infra profile, the observability slot), and FAQ. **Every folder has a short
README + its diagram.**

## 13. Repository layout

```
pavedline/
├── README.md · LICENSE · CHANGELOG.md · VERSION · CONTRIBUTING.md · SECURITY.md
├── ARCHITECTURE.dot/.svg
├── .claude-plugin/marketplace.json        → pavedline, pavedline-cockpit
├── plugins/pavedline/{.claude-plugin/plugin.json, skills/, agents/, commands/, hooks/, config/models.yaml}
├── plugins/pavedline-cockpit/             optional mod
├── stacks/nextjs-fastapi/                 the default stack pack: web app · website + blog · Expo mobile · FastAPI
├── templates/                             copied into a product repo by /pavedline:start
│   ├── CLAUDE.md · STATE.md · GLOSSARY.md · RUN.md · SERVICES.md · LINKS.md · decisions/ · handoff/
│   ├── docs/{business,spec,data,api,architecture,design,plans,retros,archive}/
│   ├── infra/{helm/base-chart, k8s/{applicationsets,addons,apps}, terraform/profiles/oci-oke}/
│   └── .github/{workflows/, CODEOWNERS, pull_request_template.md}
├── docs/  flow.dot/.svg · steps/ · solo-vs-team.md · lessons.md · extending.md · faq.md · superpowers/specs/
└── tests/ hook tests · template render tests · skill evals (claude plugin eval) · helm tests
```


## 14. Lessons from production, and where each is enforced

| Lesson | Enforced by |
|---|---|
| Merged ≠ deployed: verify running pods, not `Synced` | `deploy` skill step 4 |
| Migrations before the image syncs | Helm PreSync Job + `deploy` |
| Terraform: 0 destroy, 0 replace, no state surgery | OCI profile README + `deploy`/`gitops` skills |
| Never design to a vendor's free tier; ask before adding any new service (state what, why, cost) | `architecture-intake`, `SERVICES.md` rule |
| Vendor and infra facts verified on the web, never from memory | `researcher` agent rule |
| Commit and push after every edit; never leave work local | `state` skill + closing block |
| Reviewers never check out branches in the main working tree | reviewer agent prompt + worktree rule |
| Timestamps from `date` | `state` skill |
| Every image boots in CI | CI template |
| Lanes green alone can fail together: rebase and re-prove before each merge | `quality-gates` (multi-lane merge) |
| A skip-CI marker in a squash body builds nothing | `deploy` checks that a CI run exists for the SHA |
| PgBouncer transaction mode breaks session state | `multi-tenancy` / `db-schema` |
| Records bloat; rules accrete as amendments | size-cap hooks, one-place rules, ADR supersession |
| A stalled agent may already have pushed | `state` skill: check the remote before redoing work |

## 15. Constraints

Public repo, MIT, no secrets, no private identifiers. Free and open-source tools only inside the factory
(paid accounts in §12 are the user's own production accounts). Claude Code plugin format, distributed as a
marketplace. Must work for solo and team. Observability excluded. Every vendor fact in docs is verified with a source
link and date.

## 16. Waiting on the founder

- **F1 (RESOLVED 2026-11-07, founder: no):** no employer is named anywhere; the README shows only the LinkedIn link.
- **F2 (RESOLVED 2026-11-07, founder: personal account):** create the public GitHub repo `pavedline` (or approve that the agent creates it with `gh`) and choose the
  owner: personal account or an org.
- **F3 (RESOLVED 2026-11-07):** design approved; build the workflow and push to GitHub.

## 17. Left to the builder

The exact hook script language (POSIX shell vs Node), the `models.yaml` schema, the wording of each `SKILL.md`, the
Helm chart's value names, the cockpit's layout, the docs-site generator (none in v1, plain Markdown unless asked),
and the order of the build plan. That order is a plan for the founder to approve after this document.

## 18. Builder-check answers (2026-11-07)

A fresh reviewer read this document as the builder would. It raised 8 questions. Each one is answered here:
**(answered)** from the project or verified facts, **(call)** by the designer, **(founder)** for the one that only
the founder can answer.

1. **Source material (answered).** The author's private production workflow (agent commands and definitions, k8s,
   Terraform and CI) is kept **outside** this repo. Rule: **port and generalise; never copy verbatim**. **Sanitisation is
   checked by CI**: a deny-list scan fails the build on
   - built-in patterns: cloud resource IDs (e.g. `ocid1.`), private IP literals, key and token formats
   - the author's private identifiers (usernames, internal domains, regions, product names), kept **only** in a
     gitignored local file, never written in the repo

   The committed deny-list holds only generic patterns. The scan covers docs as well as templates.
2. **What "done" means for v1: see §19 (founder question).**
3. **Release order: vertical slices (call).** Each release is usable on its own:
   - v0.1: steps 0–3 + memory files + hooks + `doctor` + README/diagram.
   - v0.2: steps 4–7 (system design, data, architecture, Figma).
   - v0.3: steps 8–10 + Helm base chart + GitOps templates + CI.
   - v0.4: step 11 (go to production: OCI profile, cloud staging, production) + step 12 + the cockpit mod.
   - v1.0: the §19 proof passes.
4. **Dependencies (answered, verified 2026-11-07 in the plugin docs).** `plugin.json` `dependencies` accepts
   `"name@marketplace"`. Dependencies auto-install **only if** Pavedline's `marketplace.json` lists the other
   marketplace in `allowCrossMarketplaceDependenciesOn`. Version ranges resolve only against
   `<plugin>--v<version>` git tags, so dependencies are declared **without** ranges unless the upstream tags.
   Skills installed with `npx skills` (vercel/next.js, vercel-labs/agent-skills) cannot be declared at all. So a new
   **`doctor`** skill (24th) runs at `/pavedline:start` and on demand. It checks every dependency, plugin, MCP server
   and CLI tool, and prints the exact install command for anything missing. Optional dependencies (impeccable, its
   Apache-2.0; crawl4ai; next-devtools-mcp) degrade gracefully: skills name a fallback.
5. **Hooks vs CI (call).** **CI is authoritative for every rule that can be checked on a PR**, because hooks are
   bypassable and local. Hooks are early warnings, **except** the secret and `.env` guards, which **block**. Gates
   line and `.dot` drift: a hook warns, CI fails. `STATE.md` cap: a hook blocks a write that would exceed 60 lines and
   tells the agent to archive. Archiving moves the oldest *closed* items (LEFT BEHIND items marked done, old LAST
   entries) into `docs/archive/state-YYYY-MM.md`, appended and dated. NEXT, WAITING ON YOU and open LEFT BEHIND items
   never move.
6. **Team mode in v1 (call).** It includes parallel lanes, each in its own worktree with its own
   `handoff/<branch>.md`. `OWNER` is **a person** in team mode and **the main session** in solo mode. Branch
   protection, CODEOWNERS and required checks: `start` *prints* the `gh` commands and runs them **only after the
   founder says yes** in the session. They are never applied silently.
7. **Deploy access (call).** Default access is the user's own kubeconfig context, named in `RUN.md`. Teleport is
   optional. The `deployer` agent may run read-only `kubectl` / `argocd` to verify. It **syncs only after the founder
   says "deploy" in the session**, with that approval quoted in its prompt. The change-specific check is written by the
   builder into the PR template's `Post-deploy check:` field. A PR without it fails CI when it touches deployable paths.
8. **Version pins and updates (call; Renovate added at the founder's request).** Templates pin **exact versions**
   (images by digest, charts, CNPG, the Barman plugin, Next.js, Python packages via `uv.lock`, GitHub Actions by SHA).
   **Renovate** keeps them current. Facts (2026-11-07): `renovatebot/renovate` is AGPL-3.0, v44.222.2. Its managers
   include `argocd`, `helm-values`, `helmv3`, `kubernetes`, `dockerfile`, `github-actions`, `npm`, `pep621`, plus
   custom regex managers for versions written in scripts. So it updates image tags inside Helm values and ArgoCD
   manifests, which Dependabot version updates do not do generically. It **runs inside our own CI** through
   `renovatebot/github-action`, not Mend's hosted app, so no third party gets repository access (no new service).
   Running AGPL software as a CI tool creates no obligation for the product's code.
   - Weekly schedule. Minor and patch updates are grouped. A dependency-dashboard issue lists everything pending.
   - **Auto-merge only** patch updates of development tooling, after CI is green.
   - **Never auto-merge** cluster add-ons, CNPG, ArgoCD, base images or Terraform providers. These open a PR that
     must pass the local-cluster test and the five gates.
   - GitHub's built-in **Dependabot security alerts** stay on as a second net.
   - The template's dated facts are re-verified when each template is written, and the date goes into its README.

## 19. How v1 is proven: RESOLVED by the founder, 2026-11-07

**Ruled: local Kubernetes** (founder). v1 is proven by the §10.5b `local-cluster` script, run locally and in CI on every PR. **No OKE run is required for v1.** The README claims "verified end to end on Kubernetes (kind) in CI on every PR". The options below are kept as the record.


The options considered:

- **(A, recommended) A real end-to-end run.** Every PR in Pavedline's own CI runs the templates on a throwaway
  **kind** cluster: install ArgoCD, sync the example app, run migrations, check that the pods run and that a CNPG
  restore works. This is free and runs on GitHub's runners. **v1.0 additionally requires one live run on your OKE
  cluster**: a throwaway example app (`pavedline-example`) in its own namespace and Argo project, deployed through the
  full flow, verified running, then removed. Its cost is negligible on the existing nodes. Any `terraform apply` is
  yours.
- **(B) Templates only.** `helm lint`, `helm template`, `terraform validate` and kind smoke tests, with no live run.
  This is cheaper, but the README could not claim "verified on a real cluster".

## 20. Sources (checked 2026-11-07)

Versions and behaviours change. Each template re-verifies its facts and records the date in its README.
- Claude Code plugins, dependencies and mods: code.claude.com/docs/en/plugins/manifest-reference ·
  code.claude.com/docs/en/plugins/dependencies · code.claude.com/docs/en/plugins/mods/overview
- Core Web Vitals: web.dev/articles/vitals
- Istio data-plane modes: istio.io/latest/docs/overview/dataplane-modes/ · istio.io/latest/docs/ambient/overview/
- ingress-nginx retirement: kubernetes.dev/blog/2025/11/12/ingress-nginx-retirement
- React Native framework recommendation: reactnative.dev/docs/environment-setup
- Next.js agent skills moved into the framework: github.com/vercel-labs/next-skills (README)
- Clerk Python SDK: github.com/clerk/clerk-sdk-python · Clerk JS SDKs: github.com/clerk/javascript
- GitHub diagram rendering: docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams
- Every other project in §11 and §12.1: its GitHub repository (licence, latest release) via the GitHub API.
