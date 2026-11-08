# System-design questions

None may be skipped. "Not needed" is valid only with a recorded reason. Per area: question, options, recommended default, what the answer changes. Each answer feeds a decision, `SYSTEM-DESIGN.md` (with numbers), the architecture diagram (step 6), `SERVICES.md` for any new service, and the data design and plan (locking becomes columns, file locations become storage keys, targets become tests). Any new service: ask before adding (what it is, what it will do, why nothing in use does it, verified cost; the founder approves), never designed to a free tier.

## Backend

FastAPI is the preferred default. Run `backend-evaluate`; it recommends, the founder decides. **Next.js is frontend only:** no business logic; the only server code allowed is a pass-through auth-cookie proxy, enforced by a CI boundary check.

## Auth

Ask exactly: "Clerk (default), or do you need something else?" Details in `auth-contract.md`.

## Security and compliance

Data classification · encryption in transit and at rest · secrets location · insert-only audit log · edge rate limits plus per-tenant quotas · least-privilege database roles · security headers and CSP · upload malware scanning · break-glass access. If compliance is in scope (decision 0003): field-level encryption and access logging for sensitive records, data residency, and a processor agreement (DPA) with every vendor that touches personal data (auth, email, SMS, storage, analytics, billing).

## Concurrency

Users, requests per second, peak · two people editing one record (locking or a version check) · idempotency keys · the background queue (Postgres job table with `FOR UPDATE SKIP LOCKED`, default, or Redis).

## Time and scheduling

Timestamps in UTC · user and location time zones and DST · calendars, recurrence, slot generation · contention for the same slot (exclusion constraints or row locks, never session advisory locks under PgBouncer).

## Scheduled jobs

What must run on time (reminders, renewals, reports) · retries and exactly-once effects · how a late or failed job is detected · tested with a fake clock.

## Performance

Targets: API p95, page load, mobile start-up · caching · connection pooling.

## Images and files

Present? Types and sizes · direct-to-bucket upload (signed URL) or through the API · compress or resize where (device, worker, CDN) · storage (Cloudflare R2, S3, OCI Object Storage) · public or private · CDN · retention · bucket versioning.

## Real-time

None, polling, server-sent events or websockets.

## Notifications

Email (provider, sending domain, SPF/DKIM/DMARC, bounces, unsubscribe) · SMS (provider, sender registration, opt-in and opt-out, quiet hours, abuse limits) · push (APNs/FCM through Expo or direct; permission prompts) · in-app · a user preferences screen.

## Payments taken by tenants

Do tenants collect money from their own customers (deposits, invoices)? The provider (marketplace or connect model), payouts, refunds, disputes, PCI scope kept off our servers, per-tenant webhooks. Separate from the SaaS's own billing.

## Billing

The SaaS's own: needed at launch? Provider (Clerk Billing, Stripe or Paddle) · plans and entitlements enforced on the server · webhook verification and idempotency · trials, failed payments, tax/VAT, invoices.

## Accessibility

Target **WCAG 2.2 AA** (default) for website, web app and mobile · enforced as a gate and annotated in Figma.

## Mobile offline

What works without signal; how conflicts resolve on sync.

## Multi-region

One region at launch (default) or several · data residency · a cross-region backup copy · a standby database · CDN · cost.

## Service mesh

Needed at all (mTLS between services, L7 policy, traffic splitting)? Facts are in `sources.md` (re-checked on the web; never from memory). Default: no mesh at launch unless a requirement demands one; if needed, ambient mode; sidecar only for multi-cluster or VMs. Whatever the answer, network policy is default-deny and the allow-list is derived from the components (ingress, webhooks, object storage, backups).

## Website, blog and SEO

Rendering (fully server-rendered, static or incremental: default) · content source (MDX in git, or a headless CMS for non-developer writers) · languages and `hreflang` · analytics (Search Console only, or self-hosted Umami) · image delivery · the AI-crawler policy in robots.txt. Every non-public origin (app, API, others) serves a disallow-all `robots.txt` and `X-Robots-Tag: noindex`.

## Search

Needed? Postgres full-text first (default), or a service.

## Availability and recovery

Uptime target · RPO · RTO.
