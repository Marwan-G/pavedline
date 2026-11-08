# Pavedline — design

> **The GitOps software factory for Claude Code: ship a multi-tenant SaaS to production, not a demo.**

Author: Marwan Ghubein ([LinkedIn](https://www.linkedin.com/in/marwan-ghubein/)). Written 2026-11-07. Flow:
[`docs/flow.dot`](../../flow.dot), rendered to `docs/flow.svg`.

**Legend.** **(decided)** = settled by the project owner. **(default)** = the designer's choice from verified facts;
a project may override it with a recorded decision. Facts carry the date they were checked; §19 lists the sources.

---

## 1. Why Pavedline exists

Agent kits today are excellent **parts**: a build discipline (superpowers), a spec format (spec-kit), a large
toolbox (ECC), sharp interrogation skills (Matt Pocock's skills). Their focus is general, and deliberately so.
Pavedline's focus is different: **one path, end to end, for one kind of product**, from the first idea to a
multi-tenant SaaS running in production, with every step producing files, every change reviewed, and every release
verified on a real Kubernetes cluster.

It is distilled from the workflow the author used to build and run a production platform, keeping what that workflow
proved and fixing what hurt it (§15).

## 2. Who it is for

- **Built for (decided):** developers, tech leads, DevOps, DevSecOps and platform engineers building a real,
  multi-tenant product that people will pay for and depend on. **Solo founders and teams both work (decided).**
- **Not for:** weekend demos, one-prompt apps, or anyone who wants an agent to merge code nobody reviewed.
- **Serious means real accounts (decided):** cloud, domain, Figma, app stores. They are requested **just in time**,
  never all at once (§6.8), and the README lists them up front (§13).
- **Privacy (decided):** Pavedline collects nothing and has no telemetry. Every answer stays in the user's own repo.
- **Public and open-source (decided):** MIT licence (default), no secret and no private identifier anywhere (§16).

## 3. Goals

1. **Every product ships four surfaces (decided):** website, blog, web app and a native mobile app. A project defers
   one only through a recorded decision.
2. **One clear path, step 0 → step 12 (§6).** Every step has inputs, output files, skills, an agent, a gate and an
   approver. Every checkpoint ends with "go?"; nothing moves without it (decided).
3. **Memory from files only (§7).** A fresh session or a new teammate resumes with no chat history.
4. **Production architecture from the first commit (§11).** Helm base chart, GitOps, backups with tested restores,
   least privilege, secret hygiene.
5. **GitOps is the backbone (decided).** Git is the only path to any cluster.
6. **Built and verified on local Kubernetes; the cloud comes once, at the end (decided, §6.10).**
7. **Multi-tenancy is the first architecture question (decided, §6.1)** and is enforced, not advised (§12.3).
8. **Figma is required (decided, step 7):** a real design system and every screen in every state.
9. **Database design is its own step (decided, step 5);** in-cluster or managed is asked at step 0 (decided).
10. **Market research toward profitability, with free open-source tools only (decided, §6.2).**
11. **The best possible website SEO (decided, §6.6).**
12. **Rules enforced by CI and hooks, each written in one place (§9, §12).**
13. **An attractive, honest public face (decided, §13).**

## 4. Non-goals and anti-goals

**Non-goals (now):**
- **Observability and tracing (decided).** A clean seam is left for a future observability agent (§12.5). The only
  exception is **three alerts** (decided, §11.11).
- Building any product inside this repo; naming any product built with it (decided).
- Replacing the plugins it depends on.

**Anti-goals (failure even if it technically works):**
- An instructions file that turns into a changelog (the source project's grew past 1,000 lines of dated amendments).
- Records that outgrow their purpose (the source project's progress files grew to hundreds of kilobytes).
- The same rule copied into several files; gates that exist only in prose.
- Anything that works only as a local demo.
- A paid or closed tool **inside the factory**. The user's own production accounts are requirements, not factory tools.
- Leaking anything private.

## 5. Vocabulary (one definition each)

| Term | Meaning |
|---|---|
| **local** | the kind cluster on the developer's machine. Every wave deploys and is verified here, through ArgoCD (§11.6) |
| **staging** | the **cloud** staging environment, created at step 12 before production. Generated data only; never indexable |
| **production** | the live cloud environment, promoted from a verified staging SHA |
| **verified (local)** | migrations applied, ArgoCD synced, pods running the release SHA with 0 restarts, health endpoints OK, the slice's acceptance tests passing against the cluster |
| **verified (cloud)** | verified (local) **plus** what local cannot prove: real DNS and TLS, the tunnel or ingress, cloud IAM and vault, a backup **and a real restore**, the three alerts fired in a test, email deliverability |
| **wave** | a planned group of slices (step 8) that ends with deploy (step 10) and learn (step 11) |
| **slice** | the smallest change with its own tests, review gates and PR |
| **feature-complete** | every acceptance test in `SPEC.md` mapped to a merged slice and passing on local. The integration wave (§6.7) follows it, before step 12 |

## 6. The flow: thirteen steps

Source of truth: [`docs/flow.dot`](../../flow.dot). A step is done when its output files exist, its gate passed,
and `STATE.md` points at the next step.

| # | Step | Output files (in the product repo) | Skills (new = Pavedline writes it) | Agent | Gate / approver |
|---|---|---|---|---|---|
| 0 | **Start** (§6.1) | `PRODUCT.md`, `STATE.md`, `WAITING.md`, `CLAUDE.md`, `decisions/0001-…`, `RUN.md`, `SERVICES.md`, `LINKS.md`, stack-neutral templates | new `start`, `architecture-intake`, `compliance`, `state`, `doctor` | orchestrator | founder confirms the intake |
| 1 | **Market + SEO research** (§6.2) | `docs/business/competitors/*.md`, `BRIEF.md`, `SEO-STRATEGY.md`, `landscape.dot` | new `competitor-teardown`, `pricing-model`, `market-size`; `competitive-brief`, `synthesize-research` (knowledge-work-plugins) | researcher | founder approves the brief |
| 2 | **Grill** | `decisions/*`, `GLOSSARY.md` | `grilling`, `grill-with-docs` (Matt Pocock) | orchestrator | the interrogation frontier is empty |
| 3 | **Spec** | `docs/spec/SPEC.md`: users, jobs, features **per surface**, non-goals, acceptance tests, non-functional needs, site map and URL plan; team mode adds GitHub issues | new `spec`; `to-tickets` (team mode) | orchestrator | founder approves; the brief is updated if the spec changes pricing |
| 4 | **System design** (§6.3, §6.4) | an ADR per answer, `docs/architecture/SYSTEM-DESIGN.md` (with numbers), `AUTH.md`, `TENANCY-LIFECYCLE.md`, `docs/production/LEAD-TIME.md` | new `system-design`, `backend-evaluate`; Clerk skills | architect (+ researcher for evidence) | founder answers and approves each decision |
| 5 | **Data + API** | `docs/data/DOMAIN.md`, `erd.dot`, `SCHEMA.md`, `MIGRATIONS.md`, `docs/api/openapi.yaml` | new `domain-model`, `db-schema`, `multi-tenancy`, `api-contract` | architect + blind reviewer | reviewer `APPROVE`, then founder. Machine checks (RLS, migrations) run from step 9 |
| 6 | **Architecture** | `docs/architecture/ARCHITECTURE.dot`, `THREATS.md`, Helm and environment layout; **stack templates copied now** (§6.9) | new `system-architecture`, `helm-base-chart`, `gitops`, `threat-model` | architect | founder approves |
| 7 | **Figma (required)** | tokens (light/dark), type, spacing, components (Figma name = code name), FigJam flows, a frame set **per surface**, every screen in every state, the screens required by §6.4 and §11.4, accessibility annotations; `docs/design/DESIGN.md` with file and node links; Code Connect; exported tokens | `ui-ux-pro-max` (reference only), `figma-use`, `figma-generate-library`, `figma-generate-design`, `figma-use-figjam`, `figma-code-connect`, `impeccable`; new `design-system-contract` | designer + design-verifier (blind) | `DESIGN VERDICT: APPROVE`, then **founder approves the visual** |
| 8 | **Plan** (§6.7) | `docs/plans/<date>-<wave>.md` + `.dot`; every acceptance test mapped to a slice | `superpowers:writing-plans`, new `plan-graph` | orchestrator | founder approves the wave |
| 9 | **Build** (per slice, §9) | code, tests, migrations, a PR with the gates line, `handoff/<branch>.md` | superpowers TDD, subagent-driven development, worktrees, verification, finishing a branch; built-in `security-review`; new `quality-gates`; stack and data skills as needed | builder + reviewer + adversary (both blind) | the five gates, squash-merge |
| 10 | **Deploy to local** | the tag-bump PR synced by ArgoCD in the local cluster; mobile builds on simulators and devices | new `deploy`, `local-cluster`, `mobile-build` | deployer | verified (local) |
| 11 | **Learn** (end of every wave) | `docs/retros/<date>.md`; each new rule lands in the one place it lives (`docs/rules-index.md` says where) | `retro` (Matt Pocock), new `lessons` | orchestrator | founder reads |
| 12 | **Go to production** (once, §6.10) | `docs/production/INFRA.md`, `NEEDS.md`, `LAUNCH.md`; infra profile filled; **cloud staging, then production** | new `go-to-production`, `deploy`, `gitops` | deployer + architect | "time for production?" → infra intake → founder's apply → staging verified → production verified → **"go live"** |

**The loop.** Steps 8 → 9 → 10 → 11 repeat per wave on local Kubernetes. The **integration wave** (§6.7) runs
before step 12. Step 12 runs once. After launch, every wave goes local → staging → production, each promotion by PR.

**Re-entry.** Any of steps 1–7 can be reopened with a recorded decision. The decision lists the downstream outputs it
makes stale (for example, a changed step-4 answer marks `SCHEMA.md` and the affected Figma screens stale), and
`STATE.md ▶ STALE` tracks them until they are updated.

**Light path (default).** A small change (a bug fix, a copy edit) skips steps 1–8 and runs 9–11.

### 6.1 Step 0: start

Asked in this order. Each answer becomes an ADR:
1. **"What are you building?"** One paragraph: who it serves, the problem, the one thing it must do well. Saved as
   `PRODUCT.md`; every later step reads it.
2. **Multi-tenant? (decided: the first architecture question)** Single-tenant, multi-tenant B2B (organisations) or
   B2C. If multi-tenant: shared schema + `tenant_id` + row-level security (default), schema-per-tenant or
   database-per-tenant. The answer flows into auth (step 4), data (5), architecture (6), the tenant screens (7), the
   leak test (9) and the API.
3. **Compliance (decided wording):** "Should we design with compliance in mind (privacy laws such as GDPR, health
   or payment rules)? Recommended: yes." On **yes**, three short questions: the kinds of data (personal, health,
   payment, children's), the countries served, and any rule set the founder already knows applies. The answers feed
   the market step, the security rows of step 4, the threat model, the processor agreements and the launch
   checklist. On **no**, an ADR records "compliance not in scope" with one line on what that means (some data types
   carry legal duties regardless), and the launch checklist asks once more before go-live (default).
4. Solo or team.
5. Surfaces: all four by default.
6. **Database in Kubernetes (CNPG) or a managed service (decided).** Local always runs CNPG; a managed choice is
   bound to a real service at step 12.
7. Local runtime: Colima + kind (default), or Docker Desktop / OrbStack if already installed.

**Not asked at step 0 (decided):** the cloud provider and production accounts (step 12), and cost per tenant (not a
mandatory question at all). Domain and email provider are asked in step 4 or just in time.

### 6.2 Step 1: market and SEO research

- **Input:** the founder names the sites and products they already have in mind; the researcher starts there.
- Competitor pages, pricing, feature lists and public complaints → `competitors/*.md`.
- `BRIEF.md`: positioning, pricing tiers, how the product makes money, market size (sourced).
- `SEO-STRATEGY.md`: competitors' sitemaps and topics, the queries and search intent (autocomplete, "people also ask",
  trends), topic clusters, pillar pages, a target query per page.
- If compliance is in scope: the regulatory landscape for the chosen countries, with sources.
- **Scraping rules:** Playwright MCP (default) or crawl4ai; robots.txt and each site's terms respected; review sites
  only through manual export or official APIs; a login-gated competitor is researched from public material only.
  Every claim carries a URL and is marked definite, inferred or unknown.

### 6.3 Step 4: the mandatory system-design questions

None may be skipped. "Not needed" is valid only with a recorded reason. Each answer goes to an ADR,
`SYSTEM-DESIGN.md` (with numbers), the architecture diagram (step 6), `SERVICES.md` for any new service, and the data
design and plan (locking → columns, file locations → storage keys, targets → tests). **Any new service follows the
ask-before-adding rule** (§12.6). To avoid one exhausting session, the questions come in three short rounds:
*platform* (backend, auth, tenancy lifecycle, security and compliance), *behaviour* (concurrency through
notifications and payments), *reach* (accessibility, regions, mesh, website and SEO, search, availability).

| Area | Questions |
|---|---|
| **Backend** | FastAPI is the preferred default (decided). `backend-evaluate` checks it against the spec with sources. Pass criteria: every must-have need has a supported, maintained path; no blocker in concurrency, real-time or background work; the team can run it. It names anything FastAPI would struggle with, compares alternatives only then, and recommends; the founder decides. **Next.js is frontend only (decided):** no business logic; the only server code allowed is a pass-through auth-cookie proxy, enforced by a CI boundary check |
| **Auth: Clerk by default** | Asked, not assumed (founder, 2026-11-08): *"Clerk (default), or do you need something else?"* Typical reasons to choose another: the product already uses Supabase; compliance or data residency needs self-hosted auth (e.g. Keycloak); enterprise SSO first. Any alternative is checked with sources against the spec (multi-tenant organisations, roles, SSO, MFA, mobile SDK, Python token verification, webhooks or another sync path, data residency, cost at expected users); the founder decides and an ADR records it. Tenancy is written against a small **auth contract**: tenant and roles from the verified token, membership sync, a reconciliation job; the chosen provider implements it. Clerk is the built-in, tested implementation; another provider is planned per project, not pre-built. **With Clerk:** Clerk Organisation = tenant, with our `tenants` table keeping the Clerk org id, synced by verified webhooks · the tenant always comes from the verified token · roles: Clerk org roles or app permissions · FastAPI verifies each request with Clerk's Python SDK (`clerk-backend-api`, `authenticate_request`) · web and mobile sign-in through Clerk's Next.js and Expo SDKs · machine tokens for integrations · every Clerk call behind one wrapper · Clerk's cost at expected user counts, never designed to a free tier |
| **Security and compliance** | data classification · encryption in transit and at rest · secrets location · insert-only audit log · edge rate limits plus **per-tenant** quotas · least-privilege DB roles · security headers and CSP · upload malware scanning · break-glass access · if compliance is in scope: field-level encryption and access logging for sensitive records, data residency, and a **processor agreement (DPA) with every vendor that touches personal data** (auth, email, SMS, storage, analytics, billing) |
| **Concurrency** | users, requests per second, peak · two people editing one record (locking or a version check) · idempotency keys · the background queue (Postgres job table with `FOR UPDATE SKIP LOCKED`, or Redis) |
| **Time and scheduling** | timestamps in UTC; user and location timezones and DST · calendars, recurrence, slot generation · contention for the same slot (exclusion constraints or row locks, never session advisory locks under PgBouncer) |
| **Scheduled jobs** | what must run on time (reminders, renewals, reports) · retries and exactly-once effects · how a late or failed job is detected (alert 3, §11.11) · tested with a fake clock |
| **Performance** | targets: API p95, page load, mobile start-up · caching · connection pooling |
| **Images and files** | present? types and sizes · direct-to-bucket upload (signed URL) or through the API · compress or resize where (device, worker, CDN) · storage (Cloudflare R2, S3, OCI Object Storage) · public or private · CDN · retention · bucket versioning |
| **Real-time** | none, polling, server-sent events or websockets |
| **Notifications** | email (provider, sending domain, SPF/DKIM/DMARC, bounces, unsubscribe) · **SMS** (provider, sender registration, opt-in and opt-out, quiet hours, abuse limits) · **push** (APNs/FCM through Expo or direct; permission prompts) · in-app · a user preferences screen |
| **Payments taken by tenants** | do tenants collect money from *their* customers (deposits, invoices)? the provider (marketplace or connect model), payouts, refunds, disputes, PCI scope kept off our servers, per-tenant webhooks. Separate from the SaaS's own billing |
| **Billing (the SaaS's own)** | needed at launch? provider (Clerk Billing, Stripe or Paddle) · plans and **entitlements enforced on the server** · webhook verification and idempotency · trials, failed payments, tax/VAT, invoices |
| **Accessibility** | target **WCAG 2.2 AA (default)** for website, web app and mobile · enforced as a gate (§9) and annotated in Figma |
| **Mobile offline** | what works without signal; how conflicts resolve on sync |
| **Multi-region** | one region at launch or several · data residency · a cross-region backup copy · a standby database · CDN · cost |
| **Service mesh (Istio?)** | needed at all (mTLS between services, L7 policy, traffic splitting)? Facts (istio.io, Istio 1.31.4, 2026-11-07): **ambient mode** has no sidecar (a per-node `ztunnel` for L4 mTLS, optional Envoy waypoints for L7; resource cost "Small" against sidecar's "Large"; production-ready for a single cluster since 1.22; multi-cluster still beta); **sidecar mode** puts an Envoy in every pod (full features, including multi-cluster and VMs). **Recommended answer (default):** no mesh at launch unless a requirement demands one; if needed, ambient; sidecar only for multi-cluster or VMs |
| **Website, blog and SEO** | rendering (fully server-rendered, static or incremental: default) · content source (MDX in git, or a headless CMS for non-developer writers) · languages and `hreflang` · analytics (Search Console only, or self-hosted Umami) · image delivery · the AI-crawler policy in robots.txt |
| **Search** | needed? Postgres full-text first (default), or a service |
| **Availability and recovery** | uptime target · RPO · RTO |

**Lead-time register (default).** Step 4 lists every item that takes days or weeks outside our control: payment
provider verification, SMS sender registration, Apple and Google developer accounts and store review, processor
agreements, domain verification. They go into `docs/production/LEAD-TIME.md` and `WAITING.md` **at step 4**, so they
are finished by step 12.

### 6.4 Tenant lifecycle and compliance (when multi-tenant)

Decided in step 4, designed in 5 and 7, built and tested in 9. Output: `docs/architecture/TENANCY-LIFECYCLE.md`.

| Stage | Must be designed and tested |
|---|---|
| **Create** | sign-up → auth-provider organisation (Clerk by default) → `tenants` row → default roles, settings and onboarding state, **in one transaction** |
| **Sync and repair** | auth-provider webhooks (or the provider's sync path) verified and idempotent; a scheduled **reconciliation job** repairs drift from missed events; covered by tests |
| **Suspend / offboard** | suspension blocks sign-in and API keys but keeps data; offboarding starts the retention clock; both audited |
| **Export** | tenant and individual (data-subject request) export in a documented machine-readable format |
| **Delete** | live data and files removed; the ADR states how long deleted data survives in backups, and that restores re-apply deletions; the privacy policy says the same |
| **Legal surface** | terms, privacy policy, processor agreement, sub-processor list, cookie consent where needed. Pages exist and are linked; the legal text is the founder's |
| **Support access** | an admin console; impersonation only with an audit entry and a visible banner; no shared logins |
| **Limits** | per-tenant quotas and rate limits |

### 6.5 Who asks what: no question twice (default)

Step 0 asks platform questions (§6.1). Step 2 (grill-me) asks product decisions. Step 4 asks system and stack
questions (§6.3). **superpowers brainstorming runs only inside a wave, for one feature's design.** It first reads
`PRODUCT.md`, `decisions/`, `GLOSSARY.md` and `SPEC.md`, and asks only what is undecided. This is enforceable because
superpowers states that instructions in `CLAUDE.md` take precedence over its skills (`using-superpowers`, "User
Instructions"); Pavedline's `CLAUDE.md` template carries the rule.

### 6.6 Website, blog and SEO (decided: "it must be the best")

**Principle (facts, 2026-11-07):** Core Web Vitals "good" means LCP ≤ 2.5 s, INP ≤ 200 ms and CLS ≤ 0.1 at the 75th
percentile; INP replaced FID in 2024 (web.dev). Coverage of Google's 2026 AI-search guidance says classic SEO is the
foundation of its AI features and that `llms.txt` has no ranking effect (secondary sources; re-checked on
developers.google.com when the skill is written). So: classic, excellent SEO. `llms.txt` is optional, for other agents.

| Step | Website and blog work |
|---|---|
| 1 | SEO research → `SEO-STRATEGY.md` (§6.2) |
| 3 | the site map, short stable URLs (blog under `/blog`: default), each page's intent and conversion goal |
| 4 | the SEO row of §6.3 |
| 7 | templates built for Core Web Vitals: space reserved for images, one clear LCP element, a font loading plan, readable articles, an author box (real author and credentials), an Open Graph image template |
| 9 | **The SEO gate** for `apps/site`, run on the **local production build** (never on staging, which is `noindex` by design): Lighthouse CI on mobile with **SEO 100, Performance ≥ 95, Accessibility ≥ 95, Best Practices ≥ 95** (default thresholds); lab LCP ≤ 2.5 s and CLS ≤ 0.1; unique titles and descriptions, canonical URLs, Open Graph tags, valid JSON-LD (Organization, WebSite, Article, BreadcrumbList); generated and tested `sitemap.xml` and `robots.txt`; redirects and real 404/410 pages; a lychee link check; alt text everywhere; a test that staging sends `noindex` |
| 12 | only production is indexable; sitemaps submitted to Google Search Console and Bing Webmaster Tools (founder) |

**Grow, a standing loop after launch (default).** The `growth` agent runs it with the new skills `seo-foundation` and
`content-ops`, plus Anthropic's marketing plugin (`seo-audit`, `content-creation`, `draft-content`,
`performance-report`):
1. **Publish:** brief (query, intent, outline) → draft → **human edit and fact-check; the founder approves** →
   SEO checklist → PR → deploy → request indexing.
2. **Weekly:** the content calendar, `docs/growth/calendar.md`.
3. **Monthly:** a Search Console review plus `seo-audit` → `docs/growth/YYYY-MM.md`.
4. **Quarterly:** refresh, merge or remove posts; re-check internal links.

`STATE.md ▶ GROW DUE` records the next due date, so a fresh session knows when the loop is due.

### 6.7 Waves, the integration wave, and feature-complete

- **Wave order (default):** the first wave is a **thin vertical slice through every layer**: one core user journey,
  end to end, on web and API, deployed to local. Mobile and the website follow in later waves. Each wave adds whole
  journeys, never a layer in isolation.
- **Feature-complete:** every acceptance test in `SPEC.md` is mapped to a merged slice (checked by `plan-graph`) and
  passes on local.
- **Integration wave (default), before step 12:** provider **test modes** (payments, SMS, email, auth), real
  webhooks delivered to the local cluster through a tunnel (chosen and verified when the skill is written), and a
  TestFlight / internal-track mobile build. Step 12 is never the first contact with a real provider or a real store.

### 6.8 Accounts just in time

Figma at step 7 · auth-provider development keys (Clerk by default) at the first auth slice · provider test accounts at the integration wave ·
Apple and Google developer accounts when the lead-time register says (they take time) · production accounts at step
12. The README lists all of them up front.

### 6.9 Stack packs

`stacks/<name>/` holds one stack's Dockerfiles, Helm values, CI jobs, lint and format configs, test and typecheck
commands, the `RUN.md` fragment, and the list of skills it enables. It is applied at step 6, after step 4 has decided
the stack. v1 ships **`nextjs-fastapi`**, a monorepo:
- `apps/web` (Next.js web app), `apps/site` (Next.js website + MDX blog, deployed separately so it caches and
  releases independently: default), `apps/mobile` (Expo), `services/api` (FastAPI), and `packages/` (a TypeScript
  API client generated from OpenAPI, design tokens, glossary strings).
- **Next.js ≥ 16.3.** From 16.3, `next dev` generates `AGENTS.md`/`CLAUDE.md` and bundles version-matched docs, and
  Vercel moved its Next.js agent skills into the framework repo (checked 2026-11-07). Workflow skills from
  `vercel/next.js/skills`: `next-dev-loop`, `next-bundle-optimizer`, `next-cache-components-*`,
  `next-partial-prefetching-*`. From `vercel-labs/agent-skills`: `react-best-practices`, `composition-patterns`,
  `web-design-guidelines`, `react-view-transitions`, `react-native-skills`. Deploy-to-Vercel skills are excluded;
  deploys go through GitOps.
- **Mobile: Expo.** React Native's docs recommend a framework for new apps and call Expo "a production-grade React
  Native Framework" (checked 2026-11-07). Builds run in GitHub Actions (`mobile-build`: `expo prebuild`, Xcode on
  macOS runners, Gradle on Linux). Signing material (`.p12`, provisioning profiles or an App Store Connect API key,
  the Android keystore) lives in **GitHub encrypted secrets**, is imported into a temporary keychain per job and
  deleted afterwards; its owner and rotation are in `SERVICES.md`. Expo's hosted EAS service is used only if the
  founder approves it as a new service. Store submission is a founder step.
- **`fastapi-service`** (new): uv workspace, ruff, pyright strict, Pydantic v2, import-linter boundaries, Alembic
  with explicit-SQL invariants, an in-image boot check, money as `int` or `Decimal`, never float.
- Lint and format configs ship from the first commit (§9.2).

### 6.10 Step 12: go to production, once, at the end (decided)

Steps 0–11 make only **portable** decisions ("Postgres 16, S3-compatible storage, Kubernetes with Gateway API, one
region plus a backup copy"). Step 12 binds them to real infrastructure:
1. **"Everything works on local Kubernetes and the integration wave passed. Is it time to go to production?"**
2. **Infra intake, "what do you already have?"** Cloud account and provider · an existing cluster or a new one ·
   regions · domain and DNS · container registry · secrets store · object storage · managed database (if chosen) ·
   email domain · budget ceiling → `docs/production/INFRA.md` + ADRs.
3. **"What I need from you"** → `NEEDS.md`, each item also in `WAITING.md`: accounts, logins, approvals, every
   `terraform apply` (always the founder's), and secrets placed directly in the vault, never pasted into chat.
4. **Provision:** the agent fills the infra profile (§11.8); the founder applies it; an applied plan shows `0 to
   destroy`. ArgoCD is bootstrapped.
5. **Cloud staging first (decided):** deployed through GitOps and **verified (cloud)** (§5). Then **one buffer
   wave** for whatever real infrastructure reveals.
6. **Production:** promoted from the verified staging SHA by PR and verified (cloud). Then the store submissions
   and the sitemap submissions.
7. **`LAUNCH.md`, a blocking checklist.** "Go live" is refused until every item is ticked or carries a recorded
   exception: processor agreements signed · payment and SMS providers approved for live use · store approvals ·
   legal pages live · compliance confirmed once more (§6.1) · a restore tested in the cloud · the load targets of
   §6.3 met · an accessibility audit passed (automated plus one manual screen-reader pass) · the three alerts tested
   · the observability decision recorded (install the observability extension, or accept the risk in an ADR).
8. **The founder's "go live".** The Grow loop starts.

## 7. Memory and records

**Every session reads, in this order:**
1. `CLAUDE.md` (≤ 150 lines): what the project is, where the rules live, the commands. No history.
2. `PRODUCT.md`: the one-paragraph product statement.
3. `STATE.md` (**≤ 60 lines, hook-enforced**): `STEP` · `WAVE` · `SLICES IN FLIGHT` (branch, worktree, owner) ·
   `LAST` · `NEXT` · `LEFT BEHIND` (red or unrun tests, unfixed defects, carried findings) · `STALE` · `GROW DUE` ·
   `OWNER` · `MODE` (solo | team; missing means review-only).
4. `WAITING.md`: every step only the founder can take. Removed only on the founder's word. No size cap.
5. `decisions/NNNN-*.md`: ADRs, dated, append-only, superseded by number.
6. `GLOSSARY.md`: one name per concept across the UI, API, database and code (a gate-2 check).
7. `handoff/<branch>.md`: one per working branch, folded into `STATE.md` on merge.
8. `docs/archive/`: overflow and history, moved there automatically.
9. `docs/rules-index.md`: where each rule lives.

**Rules.** One writer for `STATE.md` (solo: the main session; team: the person on `OWNER`). Other sessions work in
their own `git worktree` and write only their hand-off. Timestamps come from `date`. Every state-changing step
commits and pushes; records merge at milestones. A session starts with a short opening block (state, recommended
next step, what needs approval) and ends with a closing block (done, changed, next, waiting on you, clear-safe).
Before redoing work, a session checks the remote: a stalled agent may already have pushed.

**Wave protocol.** One approval starts one wave. The wave ends by verifying, updating the records, stating the next
recommended wave, and **stopping**. The next wave is re-derived from the files.

**Team mode.** Parallel lanes, each in its own worktree with its own hand-off. Approvals move to GitHub (PR reviews,
`CODEOWNERS`, required checks). `start` prints the `gh` commands for branch protection and runs them only after the
founder says yes. Switching between solo and team is an ADR that updates `MODE`, `OWNER` and `CODEOWNERS`.

## 8. Agents and model policy

Nine agents (`plugins/pavedline/agents/`), one job each. Every subagent prompt is self-contained (mode, branch,
files to read, the question, the report format). Read-only agents are restricted with `tools` / `disallowedTools`,
because plugin agents ignore `permissionMode` (plugin docs, checked 2026-11-07).

| Agent | Job | Access |
|---|---|---|
| researcher | market, competitor and vendor facts; a URL per claim; definite / inferred / unknown | read-only + web |
| architect | system, data, API, Helm and GitOps design | docs only |
| designer | the Figma design system and screens | Figma + design docs |
| design-verifier | a blind check of words, data, states and accessibility; never approves visuals | read-only |
| builder | one slice, in its own worktree | execute (approval quoted in the prompt) |
| reviewer | blind gates 2 and 3: reads the diff, never the summary; `APPROVE` / `REJECT` | read-only |
| adversary | blind gate 3b: breaks the code with concrete inputs | read-only |
| deployer | GitOps PRs, syncs, verification | execute |
| growth | SEO foundation, the publishing loop, the monthly review | content drafts; publishing needs the founder |

**Model policy lives in one file, `config/models.yaml`.** Default: the main session and the designer use `opus`; all
other agents use `sonnet`; `haiku` is never used. Agent frontmatter `model:` is static, so a script **generates**
each agent's `model:` line from `models.yaml`, and CI fails on drift. Each report's first line records the model
that ran. A failed subagent is re-dispatched once. Third-party reviewer agents are not used, because their own model
settings would bypass `models.yaml`; their skills may be used as checklists.

## 9. Quality gates

### 9.1 The five gates (per slice)
1. **TDD:** red first.
2. **Code review:** a blind reviewer reads the diff and checks architecture, layering, duplication, error handling,
   types, naming, complexity, dead code and the glossary. A reject means rework, never arguing past it.
3. **Security review:** the built-in `security-review`, briefed with tenancy, auth, secrets, injection and
   sensitive-data checks. **3b. Adversarial review** is required when a slice touches auth, tenancy, IAM, infra, CI,
   secrets, input parsing, payments or migrations. The threat model and the stop rule are in its first prompt; a fix
   round gets one narrow re-check, and a full new review only after a high-severity fix.
4. **Verification:** typecheck, lint, the touched packages' tests, migrations on a throwaway Postgres, the
   **accessibility checks** (axe on web app pages; the mobile accessibility linter and screen-reader labels), and
   every image booting in CI. The full suite runs once, at the merge gate, on a branch up to date with main.
5. **Merge:** squash on the remote; then deploy to local and verify (step 10).

The PR line (CI fails if it is missing or malformed):
`Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓`.
`✗` is not a valid value; every unfixed finding is listed as `accepted — <reason>`.

### 9.2 The automated layer
A failing scanner fails CI like a failing test, and reviewers receive the scanner output with the diff. Licences
checked 2026-11-07.

| Layer | Tool | Catches |
|---|---|---|
| TypeScript quality | Biome (Apache-2.0) or ESLint, plus `tsc` strict | style, likely bugs, type errors |
| Python quality | ruff + pyright strict + import-linter | lint, types, layering |
| First-party code security | **Semgrep** (LGPL-2.1, run as a tool) by default; **CodeQL** where available (free for public repos; private repos need GitHub's Code Security licence) | injection, unsafe patterns |
| Dependency updates | **Renovate** (AGPL-3.0, run as a CI tool, §11.9) | outdated packages, images, charts, actions |
| Known vulnerabilities | Dependabot security alerts + Trivy (Apache-2.0) | vulnerable packages and images |
| Infrastructure as code | Checkov (Apache-2.0) | insecure Terraform, manifests and Helm values |
| Running app | OWASP ZAP baseline (Apache-2.0), against the local cluster | missing headers, exposed endpoints |
| Secrets | gitleaks (MIT) | committed keys |
| Tenancy | the RLS schema check + the leak fixture (§12.3) | isolation gaps |
| Accessibility | axe (web app), Lighthouse (site), the mobile accessibility linter | WCAG 2.2 AA failures |

Lint counts as evidence only when its config exists and CI ran it; the stack pack ships the configs.

### 9.3 Hooks versus CI
**CI is the authoritative enforcer.** Plugin hooks run in interactive and `claude -p` sessions when the plugin is
loaded; they do **not** run under `--bare`, outside Claude, or when hooks are disabled (checked 2026-11-07). So hooks
are early warnings, **except** the blocking hooks listed in §12.4 (secret and `.env` guards, the cluster-context
guard, the `--no-verify` / force-push guard, the `STATE.md` cap). Their CI backstops: gitleaks and the deny-list scan
(secrets), branch protection on main (force-push, required checks), and a CI line-count check on `STATE.md`. The
cluster-context guard has no CI equivalent, because CI never holds cloud cluster credentials.

## 10. Diagrams

- Every folder that holds architecture has an `ARCHITECTURE.dot` (the repo root, `infra/`, `infra/k8s/`, each
  service, `docs/architecture/`); `docs/data/erd.dot`; every plan has its own `.dot`.
- GitHub does not render `.dot` (its diagram docs list Mermaid, GeoJSON, TopoJSON and ASCII STL). CI validates with
  `dot -Tcanon -o /dev/null` (exit 1 on a syntax error; `-Tnull` is absent in some builds, e.g. Graphviz 16.1.0) and
  renders with `dot -Tsvg`; the SVG is committed next to its source.
- **Drift check:** a change under a folder that has an `ARCHITECTURE.dot`, with no change to that `.dot`, fails CI
  unless the PR states `diagram unchanged: <reason>`.
- A shared style file keeps colours and shapes consistent.

## 11. Production architecture

### 11.1 GitOps
Git is the only way anything reaches a cluster: Terraform, add-ons, apps, Helm values, image tags. ArgoCD
reconciles. ApplicationSets cover `k8s/addons/*` (auto-sync, self-heal) and `k8s/apps/*` (**manual sync**,
`preserveResourcesOnDeletion: true`, so renaming a folder can never delete a database). CI builds images and commits
the tag bump; it never syncs. The `deployer` opens PRs; it never runs `kubectl apply` or `helm upgrade` against a
cloud cluster.

### 11.2 Helm base chart (a library chart)
Probes · requests and limits · a PodDisruptionBudget · an optional HPA · topology spread · non-root, read-only root
filesystem, dropped capabilities, seccomp · a dedicated least-privilege ServiceAccount per workload · NetworkPolicy
default-deny with explicit allows · a priorityClass · migrations as an ArgoCD **PreSync Job** · per-environment values
(`values-local.yaml`, `values-staging.yaml`, `values-production.yaml`). Tested with `helm lint`, `helm template`, a
schema test and Checkov.

### 11.3 Database
- **In Kubernetes:** CloudNativePG (v1.30.1, released 2026-09-23): 3 instances, synchronous replication,
  anti-affinity, backups through the **Barman Cloud CNPG-I plugin** (v0.15.1) to S3-compatible storage, a PgBouncer
  pooler in transaction mode, and a restore-drill script that is part of production readiness.
- **Managed:** the chart reads the connection string from a Secret; the restore test is a **gate** before launch.
- Both: separate owner (migration), runtime and admin roles (§12.3); reversible migrations.

### 11.4 Release compatibility ("rollback = git revert" is not enough)
A revert rolls back code and manifests. It does not undo a migration that already ran, and it does not reach a
mobile app already on people's phones.
- **Expand / contract migrations:** a release only adds; removals ship later, once nothing uses the old shape. The
  previous image always runs against the new schema. Every migration has a tested `down` path, rehearsed on local.
- **API versioning:** `/v1`; a breaking change needs a new version and a deprecation window. CI diffs the OpenAPI
  contract and fails on an unversioned breaking change.
- **Mobile minimum version:** the API exposes it, and below it the app shows a blocking "please update" screen
  (designed in step 7).
- **Staged rollout and feature flags:** the stores' phased rollouts; risky web and API features behind flags (a flags
  table first; a flag service only through the ask-first rule).
- **Store lead time:** in the lead-time register (§6.3).

### 11.5 Deploy and verification
1. Migrations run first (PreSync) on the target environment.
2. CI is green; the tag-bump commit matches the merge SHA; a CI run exists for the SHA (a skip-CI marker in a squash
   message builds nothing).
3. Each changed app is synced.
4. **Verify the running state**, never the `Synced` label: "verified (local)" or "verified (cloud)" from §5, plus the
   change-specific read-only check the PR names in its `Post-deploy check:` field.
5. On failure: revert, record it, and apply §11.4.

### 11.6 Local Kubernetes: the test bed (decided)
- **Facts (2026-11-07):** Apple Silicon is arm64, like OCI Ampere nodes, so production images run unchanged. kind
  v0.33.0 (Apache-2.0), Colima v0.10.3 (MIT), Tilt v0.37.8 (Apache-2.0). **ingress-nginx is retired** by Kubernetes
  (no security fixes after March 2026), so the templates use **Gateway API** (a controller chosen and pinned when the
  skill is written) or port-forward.
- **Machine:** 16 GB of memory minimum, 32 GB recommended; Colima started with 4 CPUs and 10 GB (default).
- **The `local-cluster` skill** creates `kind-pavedline-<project>` with `extraPortMappings` and a **local image
  registry** (the kind local-registry recipe), so every build pushes a unique tag and ArgoCD pulls it the way it
  would from a real registry. It installs the same add-ons as production from the same manifests (ArgoCD, CNPG, the
  apps). An S3-compatible store for the restore drill is chosen and verified when the skill is written. It tears
  everything down afterwards.
- **Two loops:** fast (Tilt live reload) and GitOps (ArgoCD in kind syncing from the branch).
- **Safety:** on the local cluster the agent may apply and destroy freely; a hook blocks every mutating `kubectl`,
  `helm` or `argocd` command whose context is not `kind-pavedline-*`, including a `--context` override.
- **CI runs the same script** on GitHub's arm64 runners (free for public repos). "Verified in CI" is claimed only
  after a real run passes.
- **What local cannot prove:** real DNS and TLS, the tunnel, cloud IAM and vault, multi-node failure, real load and
  real webhooks. The integration wave covers webhooks; step 12 covers the rest.

### 11.7 CI templates
arm64 image builds on native runners + the tag bump · unit tests, typecheck and lint · DB tests (a throwaway
Postgres built from the migrations) at the merge gate · the local-cluster end-to-end job · `.dot` validate, render and
drift · the scanners (§9.2) · Helm lint and template · the OpenAPI breaking-change diff · the gates-line check · the
deny-list scan · Renovate. **Cost note:** GitHub-hosted runners are free for public repos. On private repos, Linux
arm64 minutes and especially macOS minutes (mobile builds) are billed (GitHub runner pricing, checked 2026-11-07).

### 11.8 Infra profiles
- **Bring your own Kubernetes (default, generic):** a kubeconfig context, the ArgoCD bootstrap and the add-ons. It
  works on any conformant cluster with Gateway API.
- **OCI/OKE (Terraform):** VCN, subnets, OKE with arm64 Ampere node pools (labels and taints in native Terraform, no
  cloud-init), IAM, Vault → Kubernetes Secret, the backup bucket, a budget alarm. Every identifier is a placeholder.
  State protection: an applied plan shows `0 to destroy` and nothing replaced; no state surgery; removals are
  calculated item by item.
- Cloudflare Tunnel as the ingress (no load balancer, no inbound ports) with a Gateway behind it. Teleport is optional.
- Other clouds are contributions.

### 11.9 Versions and updates
Templates pin **exact** versions: images by digest, charts, CNPG and its plugin, Next.js, Python via `uv.lock`, and
GitHub Actions by SHA. **Renovate** (AGPL-3.0; v44.222.2 on 2026-11-07; its managers include `argocd`,
`helm-values`, `helmv3`, `kubernetes`, `dockerfile`, `github-actions`, `npm` and `pep621`, plus regex managers) runs
**inside our own CI** through `renovatebot/github-action`. It needs a token: a personal access token (default) or
the user's own GitHub App. `GITHUB_TOKEN` is not used, because PRs it opens do not trigger CI. The token is listed in
`SERVICES.md` with a rotation procedure.
- Weekly; minor and patch updates grouped; a dependency-dashboard issue.
- **Auto-merge only** patch updates of development tooling, after CI is green.
- **Never auto-merge** cluster add-ons, CNPG, ArgoCD, base images or Terraform providers. These open a PR that must
  pass the local-cluster test and the five gates.

### 11.10 Secrets
Never in git. The vault is authoritative (OCI profile: OCI Vault → Kubernetes Secret via Terraform). Provider test
keys for local live in a gitignored `.env.local` that only the local cluster's Secret generator reads; the hooks block
agents from reading it. Mobile signing material lives in GitHub encrypted secrets (§6.9). `SERVICES.md` records
**where** each secret lives, its owner and its rotation, never the value.

### 11.11 Operations basics
- **Backups for every datastore**, including bucket versioning and lifecycle rules.
- **Email:** SPF, DKIM and DMARC, bounce and complaint handling, unsubscribe on non-transactional mail.
- **Secrets rotation** and **break-glass** procedures in `RUN.md`.
- **Staging never holds production data.**
- **Three alerts (decided; the only exception to "observability is out of scope"):** (1) uptime of the public
  endpoints; (2) a backup failed; (3) **a scheduled job failed or is late**.
- **Cost guardrail:** a cloud budget alarm with the infra profile (not a per-tenant cost model).

## 12. Skills, dependencies, hooks and the cockpit

### 12.1 New skills (32)
start · architecture-intake · compliance · state · doctor · competitor-teardown · pricing-model · market-size · spec ·
system-design · backend-evaluate · domain-model · db-schema · multi-tenancy · api-contract · system-architecture ·
helm-base-chart · gitops · threat-model · fastapi-service · design-system-contract · plan-graph · quality-gates ·
deploy · local-cluster · mobile-build · go-to-production · lessons · seo-foundation · content-ops · diagram ·
project-registry.

`project-registry` keeps `RUN.md`, `SERVICES.md` and `LINKS.md` current. `diagram`, `project-registry` and `doctor`
are used in every step. Each skill does one job, has a short `SKILL.md`, and keeps detail in `references/`. Skills
that agents preload are **not** marked `disable-model-invocation`, because that flag prevents preloading.

### 12.2 Dependencies (installed, never copied)

| Plugin / tool | Licence | Used for | How it is installed |
|---|---|---|---|
| obra/superpowers | MIT | build discipline | plugin dependency |
| mattpocock/skills | MIT | grilling, grill-with-docs, to-tickets, retro | plugin dependency |
| anthropics/knowledge-work-plugins (product-management, marketing) | Apache-2.0 | competitive brief, research synthesis, SEO audit, content | plugin dependency |
| nextlevelbuilder/ui-ux-pro-max-skill | MIT | style reference (step 7) | plugin dependency |
| pbakaus/impeccable | Apache-2.0 | design critique | optional |
| Figma plugin + MCP | Figma terms; a **Full seat** writes to the canvas | step 7 | plugin dependency |
| Clerk skills | no licence file detected | auth (stack pack) | `npx skills`; `doctor` prints the command |
| vercel/next.js skills · vercel-labs/agent-skills | MIT · no licence file detected | stack pack | `npx skills`; `doctor` prints the command |
| microsoft/playwright-mcp | Apache-2.0 | competitor research | shipped in the plugin's `.mcp.json`, pinned |
| unclecode/crawl4ai | Apache-2.0 (attribution required) | optional bulk crawl | optional |

Dependencies are declared in `plugin.json`, and `marketplace.json` allow-lists their marketplaces. Observed on a
clean profile (`scripts/install_test.sh`, isolated with `CLAUDE_CONFIG_DIR`): with the Pavedline and
`knowledge-work-plugins` marketplaces added, `product-management` installed automatically and the two
`claude-plugins-official` dependencies (`superpowers`, `mattpocock-skills`) did not; the install printed a warning that
Pavedline will not load without them. After also adding `anthropics/claude-plugins-official`, installing
`pavedline@pavedline` installed all three dependencies automatically. The built-in `anthropic-plugin-directory` is not
`claude-plugins-official`. A further observation from a live smoke test (2026-11-08): when a declared dependency is
missing, Claude Code does not load the Pavedline plugin at all, so `/pavedline:start` and `/pavedline:doctor` are
unavailable and `doctor` cannot diagnose a missing dependency; `claude plugin list` shows the warning. The README
therefore requires the dependency marketplaces to be added before installing Pavedline, and tells the user to run
`claude plugin list` if `/pavedline:start` is not found.

**Doctor installs missing tools itself (2026-11-08, founder).** `doctor` does not only print commands. When a required
tool or Claude Code plugin is missing, the agent installs it: first one short message saying what it will install,
why (which Pavedline step needs it) and the exact command; then it runs the command (`brew install …`, `colima start
--cpu 4 --memory 10` for the container runtime, `claude plugin marketplace add` and `claude plugin install
<name>@<marketplace>` for plugins, followed by `/reload-plugins`). Claude Code's permission prompt is the user's
approval point. Never silent, never `sudo`, nothing outside doctor's list. A refusal or a failed install stops the step
and is recorded in `WAITING.md`. New paid services, accounts or spend stay under §12.6.

### 12.3 `multi-tenancy` and `db-schema`: the non-negotiable rules
The base is sickn33's `saas-multi-tenant` skill (MIT, adapted with credit), with Supabase's Postgres best practices
(MIT) as a reference. Enforced:
- The runtime role **does not own** any table and has **no `BYPASSRLS`**. Migrations run as a separate owner role;
  admin and reporting use a third, audited role.
- Every tenant table has `tenant_id NOT NULL`, **`ENABLE` and `FORCE ROW LEVEL SECURITY`**, and a policy on
  `current_setting('app.tenant_id')`. **CI reads the real schema and fails** if any tenant table lacks one. Global
  tables are explicitly allow-listed.
- The tenant is set with **`SET LOCAL` inside the transaction** for every request **and every job, webhook handler
  and scheduled task**. Session `SET` and session advisory locks are forbidden under PgBouncer transaction mode.
- Storage keys start with the tenant id; signed URLs are issued only after the same tenant check.
- **The cross-tenant leak test is a fixture:** two tenants; every endpoint, every job type and every file path is
  exercised as tenant A with tenant B's ids, and must fail. A new endpoint or job without coverage fails CI.
- Reversible, expand/contract migrations; large sums read as text so they never overflow BIGINT; tenant creation in
  one transaction.

### 12.4 Hooks (shipped by the plugin)
**Block:** `.env*` reads (except `.example`, `.sample` and `.template`) and secret-pattern writes · mutating cluster
commands outside `kind-pavedline-*` · `--no-verify` and force-pushes to main · a `STATE.md` write over 60 lines (with
an archive instruction). **Warn:** `CLAUDE.md` over 150 lines · `.dot` drift · a PR body without the gates line.
**SessionStart:** reads `STATE.md`, `WAITING.md` and `PRODUCT.md` and prints the opening block. A hook that receives
malformed input exits 0 with a stderr note (fail open), except the secret guard, which fails closed whenever its
target path is readable.

### 12.5 The cockpit mod and the observability seam
- **`pavedline-cockpit`** (optional, separate plugin): a pane showing the step, wave, next action, the open slice's
  gates and `WAITING.md`, plus `/pavedline-status`. Mods run inside Claude Code (v2.1.287+), are not sandboxed, and
  draw nothing in `claude -p`. Nothing depends on the cockpit.
- **The observability seam:** a reserved `k8s/addons/` slot and `docs/extending.md`, for a future observability agent.

### 12.6 The ask-before-adding rule (its one home)
Before any new service or billable resource, even a free one, state what it is, what it will do, why nothing already
in use does it, and its verified cost. The founder approves. This applies to every row of §6.3, to Renovate's token
choice, to EAS, analytics, flag services and providers.
Installing a tool or plugin on `doctor`'s list is not a new service; it follows the doctor rule in §12.2 (2026-11-08).

## 13. The public face

**README, top to bottom (default):** name and one-line promise · a status line ("v0.1: steps 0–3 usable; the rest in
development") · the flow diagram · built for / not for · the install commands · why Pavedline exists (sourced quotes
and figures) · what makes it different (each row marked with its release) · "is this waterfall?" · the flow table ·
requirements (accounts, costs, machine) · the roadmap · built on the shoulders of (credits) · who's behind this ·
licence. Claims are made only for what the current release does.

**Requirements:** GitHub (+ GHCR) · Claude Code · a Figma Full seat · the Apple Developer Program (yearly fee) ·
Google Play Console (one-time fee) · a Kubernetes cluster at step 12 (OCI profile or your own) · a domain and a
Cloudflare account · S3-compatible object storage · Google Search Console and Bing Webmaster Tools (free) · local
tools (git, gh, Node 22, Python 3 + uv, Graphviz, a container runtime, kind, kubectl, helm, terraform) · a Mac or
Linux machine with 16 GB of memory (32 GB recommended).

**Credits (`CREDITS.md`, `THIRD_PARTY_NOTICES.md`):** every dependency in §12.2 and every adapted source in §12.3,
with author, link, licence and how it is used ("installed", "adapted", "ideas only"). Ideas only: ECC (MIT), GitHub
spec-kit (MIT), and BMAD (licence not machine-detected; cited as inspiration only). Used by the templates: Argo CD,
CloudNativePG, Trivy, Checkov and ZAP (Apache-2.0), gitleaks (MIT), Graphviz. A CI check fails if a dependency is
added without a credit row.

**Who's behind this:** Marwan Ghubein: DevOps, DevSecOps, AI platform engineering and AI architecture experience;
built from running a production platform end to end. LinkedIn link. No employer named (decided).

**Install (personal account, decided):**
```
/plugin marketplace add Marwan-G/pavedline
/plugin install pavedline@pavedline
/pavedline:start
```
Releases are tagged `pavedline--v<version>` with `claude plugin tag`, and `/plugin update` updates. Anthropic's
plugin directory is an option after v1.0. Contributors load a clone with `claude --plugin-dir`.

**`docs/`:** one page per step, solo vs team, environments, lessons, extending, FAQ. Every folder has a short README
and its diagram.

## 14. Repository layout

```
pavedline/
├── README.md · LICENSE · CHANGELOG.md · VERSION · CONTRIBUTING.md · SECURITY.md · CREDITS.md · THIRD_PARTY_NOTICES.md
├── ARCHITECTURE.dot/.svg
├── .claude-plugin/marketplace.json            → pavedline, pavedline-cockpit
├── plugins/pavedline/{.claude-plugin/plugin.json, .mcp.json, skills/, agents/, hooks/, scripts/, config/models.yaml}
├── plugins/pavedline-cockpit/                 optional mod
├── stacks/nextjs-fastapi/                     the default stack pack
├── templates/                                 copied into a product repo by /pavedline:start (via ${CLAUDE_PLUGIN_ROOT})
│   ├── CLAUDE.md · PRODUCT.md · STATE.md · WAITING.md · GLOSSARY.md · RUN.md · SERVICES.md · LINKS.md
│   ├── decisions/ · handoff/ · docs/{business,spec,data,api,architecture,design,plans,retros,production,growth,archive}/
│   ├── infra/{helm/base-chart, k8s/{applicationsets,addons,apps}, profiles/{byo-kubernetes,oci-oke}}/
│   └── .github/{workflows/, CODEOWNERS, pull_request_template.md, renovate.json}
├── docs/  flow.dot/.svg · steps/ · environments.md · solo-vs-team.md · lessons.md · extending.md · faq.md · superpowers/
├── scripts/                                   deny-list scan, diagram tools, model-line generator, skill linter
└── tests/                                     hooks · scripts · template copy · skill contracts · evals
```

## 15. Lessons from production, and where each is enforced

| Lesson | Enforced by |
|---|---|
| Merged ≠ deployed: verify running pods, not `Synced` | `deploy` (§11.5) |
| Migrations before the image; a revert does not undo a migration | the PreSync Job, expand/contract (§11.4) |
| Terraform: 0 destroy, 0 replace, no state surgery | the infra profile README, `go-to-production` |
| Never design to a vendor's free tier; ask before any new service | §12.6, `architecture-intake` |
| Vendor and infra facts verified on the web, never from memory | `researcher` |
| Commit and push after every edit | `state` + the closing block |
| Reviewers never check out branches in the main working tree | reviewer prompts, worktrees |
| Timestamps from `date` | `state` |
| Every image boots in CI | the CI templates |
| Lanes green alone can fail together: rebase and re-prove before each merge | `quality-gates` |
| A skip-CI marker in a squash message builds nothing | `deploy` (§11.5) |
| PgBouncer transaction mode breaks session state | §12.3 |
| A lint step without a config never runs | the stack-pack configs (§9.2) |
| Records bloat; rules accrete as amendments | size caps, `rules-index.md`, ADR supersession |
| A stalled agent may already have pushed | `state` (§7) |
| A local process once acted on production through a forgotten connection | the cluster-context hook (§12.4) |

## 16. Constraints and sanitisation

Public repo, MIT, no secrets, no private identifiers. Free and open-source tools only **inside** the factory. Claude
Code plugin format, distributed as a marketplace. Solo and team. Observability excluded except the three alerts.
Every vendor fact carries a date and a source.

**Sanitisation (CI):** a deny-list scan over **all tracked files, docs included** fails on generic patterns (cloud
resource IDs such as OCI's `ocid1` prefix, private IP literals, key and token formats) and on the author's private identifiers,
which live only in a gitignored local extension file. The source material (the author's private production
workflow) stays outside the repo; it is ported and generalised, never copied.

## 17. Release plan and the v1 definition

| Release | Contents |
|---|---|
| **v0.1** | steps 0–3 · memory files and hooks · `doctor` · `local-cluster` (cluster + ArgoCD + CNPG) · README, diagram, credits · the marketplace and plugin skeleton · CI (unit tests, deny-list scan, `.dot` checks, `claude plugin validate`, gitleaks, Renovate) · the clean-profile install test |
| **v0.2** | steps 4–7: system design, compliance, data and API, architecture, Figma |
| **v0.3** | steps 8–11: plan, the build gates and scanners, the stack pack, the Helm base chart, GitOps templates, deploy to local, learn |
| **v0.4** | the integration wave, step 12 (profiles, cloud staging, production, `LAUNCH.md`), the cockpit mod |
| **v1.0** | the end-to-end local-cluster job passes in CI on every PR, and an example product completes steps 0–11 on local |

**v1 is proven on local Kubernetes (decided):** the `local-cluster` job runs locally and in CI on every PR; no cloud
run is required for v1. The repository stays **private until v0.1 installs and works**, then becomes public
(default).

## 18. Left to the builder

The hook scripts' language (POSIX shell or Python stdlib), the `models.yaml` schema, each `SKILL.md`'s wording, the
Helm chart's value names, the cockpit's layout, the Gateway API controller (pinned when chosen), the S3-compatible
store for local restore drills, the webhook tunnel, and the order of tasks inside each release's plan.

## 19. Sources (checked 2026-11-07)

Versions and behaviours change; each template re-verifies its facts and records the date in its README.
- Claude Code plugins, dependencies, hooks, headless mode and mods: code.claude.com/docs/en/plugins/manifest-reference ·
  /plugins/dependencies · /plugins/components · /hooks · /headless · /plugins/mods/overview
- Core Web Vitals: web.dev/articles/vitals
- Istio data-plane modes: istio.io/latest/docs/overview/dataplane-modes/ · /docs/ambient/overview/
- ingress-nginx retirement: kubernetes.dev/blog/2025/11/12/ingress-nginx-retirement
- React Native framework recommendation: reactnative.dev/docs/environment-setup
- Next.js agent skills: github.com/vercel-labs/next-skills (README) · github.com/vercel/next.js/tree/canary/skills
- Clerk SDKs: github.com/clerk/clerk-sdk-python · github.com/clerk/javascript
- GitHub: diagram rendering; hosted runners and pricing; code scanning availability (docs.github.com)
- kind: kind.sigs.k8s.io/docs/user/known-issues/ · /docs/user/local-registry/
- Renovate on GitHub: docs.renovatebot.com/modules/platforms/github/
- Developer sentiment cited in the README: survey.stackoverflow.co/2025/ai · the Veracode GenAI Code Security
  Report press release (2025-07-30) · the Hacker News items linked in the README
- Every project in §12.2 and §13: its GitHub repository (licence, latest release), via the GitHub API.
