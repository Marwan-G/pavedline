# Pavedline

**Ship a multi-tenant SaaS to production with Claude Code, not a demo.**

The GitOps software factory for serious builders: idea → market → spec → system design → Figma → tested code →
local Kubernetes → cloud staging → production. Website, blog, web app and mobile app, built as one product.

> **Status: in development.** v0.1 (steps 0–3, memory, hooks, local cluster) is being built. See the
> [roadmap](#roadmap). Every feature below is marked with the release that delivers it.

<p align="center"><img src="docs/flow.svg" alt="The Pavedline flow: Discover, Design, Deliver on local Kubernetes, then Production once" width="100%"></p>

> **Built for:** developers, tech leads, DevOps, DevSecOps and platform engineers building a real, multi-tenant
> product that people will pay for and depend on.
>
> **Not for:** weekend demos, one-prompt apps, or anyone who wants an agent to merge code nobody reviewed.
>
> **Privacy:** Pavedline collects nothing. Every answer stays in your own repository.

## Install

```
/plugin marketplace add anthropics/knowledge-work-plugins
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
/plugin marketplace add Marwan-G/pavedline
/plugin install pavedline@pavedline
/pavedline:start
```

`/pavedline:doctor` checks every tool and skill Pavedline needs and prints the exact command for anything missing.

---

## Why Pavedline exists

**The skills are great. The path is missing.**

Today's best agent kits are excellent parts: a build discipline, a spec format, a large toolbox, sharp
interrogation skills. Their focus is general, and deliberately so. Pavedline's focus is different: **one path, end to
end, for one kind of product**, from the first idea to a multi-tenant SaaS running in production.

That path is where AI-built products stall. Developers say it plainly:

> "Vibe coding is great for a PoC but we usually do a full rewrite until it's production ready."
> — [Hacker News, 2026](https://news.ycombinator.com/item?id=47169540)

> "Each session is a blank slate."
> — [Hacker News, 2026](https://news.ycombinator.com/item?id=47929504)

- **66%** of developers name "AI solutions that are almost right, but not quite" as a frustration, **45.7%**
  distrust the accuracy of AI output, and **77.5%** say vibe coding is not part of their professional work.
  ([Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/ai))
- AI-generated code introduced security vulnerabilities in **45%** of cases in tests across 100+ models.
  ([Veracode, 2025](https://www.veracode.com/press-release/ai-generated-code-poses-major-security-risks-in-nearly-half-of-all-development-tasks-veracode-research-reveals/))

Pavedline is the paved road through that gap. It is distilled from building and running a real production platform
end to end, and from every place where that went wrong.

## What makes it different

| The usual way | Pavedline | Release |
|---|---|---|
| General skills you assemble yourself | **One path, step 0 → production.** Every step has inputs, output files, an owner and your approval | v0.1 → v0.4 |
| Context lost every session | **Memory lives in the repo:** `PRODUCT.md`, `STATE.md`, decision records, a glossary. A fresh session or a new teammate resumes from files | v0.1 |
| Questions asked again and again | **Each kind of question has one owner** and is asked once, at the step where it matters | v0.1 |
| Multi-tenancy bolted on later | **The first architecture question.** Row-level security forced on every table; a cross-tenant leak test at the merge gate | v0.2 → v0.3 |
| "The agent wrote it, looks fine" | **Five gates per change:** tests first · blind code review · security review · adversarial review · verification. Scanners fail CI like a failing test | v0.3 |
| Deployment is "your problem" | **GitOps from day one:** Helm and ArgoCD, every wave verified on Kubernetes on your machine | v0.1 (cluster) → v0.3 |
| The website is an afterthought | **Website, blog, web app and mobile app** from one design system, with SEO and accessibility gates | v0.2 → v0.3 |
| You find out late what it needs | **Accounts asked just in time.** Production infrastructure is asked once, at the end, with a list of exactly what is needed from you | v0.4 |
| Rules written in prose | **Rules enforced** by CI and hooks | v0.1 → v0.3 |

## Is this waterfall?

No. Steps 0–7 decide the **expensive** things once, before code makes them costly to change: tenancy, data, auth,
architecture, design. After that, work ships in **small waves** of slices, each tested, reviewed and running on
Kubernetes. Any earlier step can be reopened with a recorded decision. A small fix takes the light path straight to
build.

## The flow

| | Steps | You get |
|---|---|---|
| **Discover** | 0 Start · 1 Market + SEO · 2 Grill · 3 Spec | your product statement and first decisions, a competitor and pricing brief, an SEO strategy, a glossary, a spec with acceptance tests |
| **Design** | 4 System design · 5 Data + API · 6 Architecture · 7 Figma | answers to every must-ask question (backend, auth, security, jobs, notifications, payments, regions), schema and ERD, OpenAPI, diagrams, every screen in every state |
| **Deliver** | 8 Plan · 9 Build · 10 Deploy to local · 11 Learn | waves of tested, reviewed slices running on a real cluster on your machine |
| **Production** | 12 Go to production | cloud staging, then production, verified, behind a launch checklist. Asked once, when everything works |

## Requirements

Asked for **just in time**, never all on day one:

| You need | When | Cost |
|---|---|---|
| GitHub account (+ GHCR) | step 0 | free for public repos; private-repo CI minutes are billed |
| Claude Code | step 0 | your Claude plan or API |
| A Mac or Linux machine, 16 GB memory (32 GB recommended), a container runtime | step 0 | — |
| Figma, **Full seat** | step 7 | paid |
| Clerk (authentication) | first auth slice | per Clerk pricing |
| Apple Developer Program · Google Play Console | before the first mobile build | yearly fee · one-time fee |
| A Kubernetes cluster (OCI profile included, or your own) · domain + Cloudflare · S3-compatible storage | step 12 | your cloud bill |
| Google Search Console · Bing Webmaster Tools | step 12 | free |

## Roadmap

| Release | What works |
|---|---|
| **v0.1** | steps 0–3 · memory files and hooks · `doctor` · local Kubernetes cluster (kind + ArgoCD + CNPG) · CI for the factory itself |
| **v0.2** | steps 4–7: system design, compliance, data and API, architecture, Figma |
| **v0.3** | steps 8–11: plan, build with the five gates and scanners, the `nextjs-fastapi` stack pack, Helm base chart, deploy to local, learn |
| **v0.4** | integration wave, step 12 (cloud staging, production, launch checklist), the optional cockpit pane |
| **v1.0** | an example product completes steps 0–11 on local Kubernetes, proven in CI on every PR |

## Built on the shoulders of

Pavedline installs these from their makers; it does not copy them. Full list with licences in
[`CREDITS.md`](CREDITS.md).

[superpowers](https://github.com/obra/superpowers) (Jesse Vincent) ·
[skills](https://github.com/mattpocock/skills) (Matt Pocock) ·
[knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) (Anthropic) ·
[ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) ·
[impeccable](https://github.com/pbakaus/impeccable) (Paul Bakaus) ·
[Figma plugin](https://www.figma.com/) ·
[Next.js skills](https://github.com/vercel/next.js) and [agent-skills](https://github.com/vercel-labs/agent-skills) (Vercel) ·
Clerk skills · [Playwright MCP](https://github.com/microsoft/playwright-mcp) (Microsoft).
Ideas from [ECC](https://github.com/affaan-m/ECC), [spec-kit](https://github.com/github/spec-kit) and
[BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD).

## Who's behind this

**Marwan Ghubein**: DevOps, DevSecOps, AI platform engineering and AI architecture. Pavedline comes from running a
production platform end to end: Kubernetes, GitOps, security and agent-driven delivery.
[LinkedIn](https://www.linkedin.com/in/marwan-ghubein/)

## Licence

MIT.
