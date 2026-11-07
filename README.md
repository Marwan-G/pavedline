# Pavedline

**Ship a multi-tenant SaaS to production with Claude Code, not a demo.**

The GitOps software factory for serious builders: idea → market → spec → system design → Figma → tested code →
local Kubernetes → cloud staging → production. Website, blog, web app and mobile app, built as one product.

<p align="center"><img src="docs/flow.svg" alt="The Pavedline flow: Discover, Design, Deliver on local Kubernetes, then Production once" width="100%"></p>

> **Built for:** developers, tech leads, DevOps, DevSecOps and platform engineers building a real, multi-tenant
> product that people will pay for and depend on.
>
> **Not for:** weekend demos, one-prompt apps, or anyone who wants an agent to merge code nobody reviewed.

```
/plugin marketplace add Marwan-G/pavedline
/plugin install pavedline@pavedline
/pavedline:start
```

---

## Why Pavedline exists

**The skills are great. The path is missing.**

Today's best agent kits are excellent parts: a planning method here, TDD discipline there, a spec format, a toolbox
of hundreds of skills. They are general by design. None was carried through **one real product**, from the first
idea to a multi-tenant system running in production, and none ends with a verified deploy.

That gap is where AI-built products stall. Developers say it plainly:

> "Vibe coding is great for a PoC but we usually do a full rewrite until it's production ready."
> — [Hacker News, 2026](https://news.ycombinator.com/item?id=47169540)

> "Each session is a blank slate."
> — [Hacker News, 2026](https://news.ycombinator.com/item?id=47929504)

- **66%** of developers name "AI solutions that are almost right, but not quite" as a top frustration. **45.7%**
  distrust the accuracy of AI output. **77.5%** say vibe coding is not part of their professional work.
  ([Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/ai))
- AI-generated code introduced security flaws in **45%** of tasks, across 100+ models.
  ([Veracode, 2025](https://www.veracode.com/press-release/ai-generated-code-poses-major-security-risks-in-nearly-half-of-all-development-tasks-veracode-research-reveals/))

Pavedline is the paved road through that gap. It was distilled from building and running a real production platform
end to end, and from every place where that went wrong.

## What makes it different

| The usual way | Pavedline |
|---|---|
| General skills you assemble yourself | **One path, step 0 → production.** Every step has inputs, output files, an owner and your approval |
| "The agent wrote it, looks fine" | **Five gates per change:** tests first · blind code review · security review · adversarial review · verification. Scanners (CodeQL, Semgrep, Trivy, Checkov, gitleaks) fail CI like a failing test |
| Context lost every session | **Memory lives in the repo:** `STATE.md`, decision records, a glossary. A fresh session, or a new teammate, resumes from files |
| Deployment is "your problem" | **GitOps from day one:** Helm, ArgoCD, every wave verified on local Kubernetes. Cloud staging, then production, when you say go |
| Multi-tenancy bolted on later | **The first question.** Row-level security forced on every table; a cross-tenant leak test at the merge gate |
| Rules written in prose | **Rules enforced** by hooks and CI |
| The website is an afterthought | **Website, blog, web app and mobile app** from one design system, with an SEO gate that fails CI |
| You find out late what it needs | **Accounts asked just in time**, and production infra asked once, at the end, with a list of exactly what is needed from you |

## Is this waterfall?

No. Steps 0–7 decide the **expensive** things once, before code makes them costly to change: tenancy, data, auth,
architecture, design. After that, work ships in **small waves** of slices, each tested, reviewed and running on
Kubernetes. Any earlier step can be reopened with a recorded decision. A small fix takes the light path straight to
build.

## The flow

| | Step | You get |
|---|---|---|
| **Discover** | 0 Start · 1 Market + SEO · 2 Grill · 3 Spec | rules, records, competitor and pricing brief, decisions, glossary, a spec with acceptance tests |
| **Design** | 4 System design · 5 Data + API · 6 Architecture · 7 Figma | must-ask answers (backend, auth, security, concurrency, files, regions, billing), schema + ERD, OpenAPI, diagrams, every screen in every state |
| **Deliver** | 8 Plan · 9 Build · 10 Deploy to local Kubernetes · 12 Learn | waves of tested, reviewed slices running on a real cluster on your machine |
| **Production** | 11 Go to production | cloud staging, then production, verified. Asked once, when everything works |

*(Draft: what you get, requirements, credits and who's behind this follow, per the design document §12.)*
