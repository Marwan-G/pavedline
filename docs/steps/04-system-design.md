# Step 4: System design

Starts when `STATE.md` says `STEP: 4` and you say go. Skills: `system-design`, `backend-evaluate`. Agents: `architect` (the documents), `researcher` (evidence with URLs), `reviewer` (blind records-consistency check).

## What it is for

Settling every system-level question before the data model, so nothing is discovered late: backend, auth, tenancy lifecycle, security, concurrency, time, jobs, performance, files, real-time, notifications, payments taken by tenants, billing, accessibility, offline, regions, service mesh, website and SEO, search, availability.

## What you will be asked

Three short rounds: **platform** (backend, auth, tenancy lifecycle, security and compliance), **behaviour** (concurrency through billing, with generated documents and AI and models), **reach** (accessibility, languages and right-to-left, regions, mesh, website and SEO, search, availability).

A choice you already named (for example a database or storage provider in `docs/business/VISION.md`) is checked with sources, not compared, and recorded only when you confirm it. Alternatives are compared only if the check finds a blocker. One area at a time, with options and a recommended default. "Default" is a valid answer; "not needed" is valid only with a recorded reason. Areas of a surface you dropped in step 0 are skipped. Auth is asked, not assumed: "Clerk (default), or do you need something else?" Any new service is introduced with what it is, what it will do, why nothing in use does it and its verified cost, and is never designed to a free tier; nothing is added until you say so.

## Output files

One decision per answered area (`decisions/`), `docs/architecture/SYSTEM-DESIGN.md` (with numbers), `docs/architecture/AUTH.md`, `docs/architecture/TENANCY-LIFECYCLE.md` (single-tenant: "not applicable (decision 0002)"), `docs/production/LEAD-TIME.md`, `docs/architecture/BACKEND-EVALUATION.md` (the backend evaluation), and the same slow items in `WAITING.md`. Before the hand-off a blind `reviewer` reads the decisions and these outputs for contradictions and writes its verdict and findings to `docs/reviews/04-system-design-review.md`; a `REJECT` means rework and a narrow re-review. Folders missing from a v0.1 project are created.

## Re-entry

If you change a step-4 answer later, a new decision supersedes the old one and lists the outputs it makes stale; they stay in `STATE.md ▶ STALE` until updated.

## Who approves

You approve each decision.

## Hand-off

`STATE.md` is set to `STEP: 5 — Data and API`.

Next: [step 5: data and API](05-data-and-api.md).
