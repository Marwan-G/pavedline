# Step 0: Start

Run once, in the repository of your new product: `/pavedline:start`.

## What it is for

It checks your machine, asks the platform questions that are expensive to change later, and creates the files that
carry the project's memory. Nothing is installed without your go.

## Inputs

An empty (or nearly empty) git repository. If it is not a git repository, you are asked before `git init` runs. If
`CLAUDE.md` or `STATE.md` already exists, nothing is overwritten: the conflicting files are listed and nothing is written.

## What you will be asked

One question at a time, each with its default. You can answer "default".

1. What are you building? One paragraph: who it serves, the problem, the one thing it must do well.
2. Multi-tenant? Single-tenant, multi-tenant for businesses, or for consumers. If multi-tenant, which isolation
   model (default: shared schema with a tenant column and row-level security).
3. Compliance, with this exact wording: "Should we design with compliance in mind (privacy laws such as GDPR,
   health or payment rules)? Recommended: yes." On yes, three short follow-ups.
4. Solo or team (default: solo).
5. Surfaces: web app, website with blog, mobile app, API (default: all four).
6. Database in Kubernetes with CloudNativePG (default) or a managed service.
7. Local runtime (default: Colima with kind).

The cloud provider is not asked now. It is chosen at step 12, when the product is ready for production.

Before the first question you will see: "Pavedline collects nothing. Every answer stays in your own repository."

## Output files

In your repository:

- `PRODUCT.md`, `STATE.md`, `WAITING.md`, `CLAUDE.md`, `GLOSSARY.md`, `RUN.md`, `SERVICES.md`, `LINKS.md`
- `decisions/0001-…` to `decisions/0007-…`: one decision record per question, numbered in question order, plus
  `decisions/0000-template.md`
- `handoff/README.md`, `docs/rules-index.md`, and the starting folders under `docs/`
- `ARCHITECTURE.dot` and its rendered `.svg`

## Who approves

You. The step ends with a summary and the question "go?". Step 1 starts only when you say go.

## Hand-off to the next step

`STATE.md` is set to `STEP: 1 — Market + SEO research`, and anything only you can do (for example installing a tool
that `doctor` reported missing) is listed in `WAITING.md`. The files are committed in one commit. Next:
[step 1](01-market.md).
