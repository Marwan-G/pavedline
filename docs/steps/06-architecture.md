# Step 6: Architecture

Starts when `STATE.md` says `STEP: 6` and you say go. Skills, in order: `system-architecture`, `threat-model`. Agents: `architect` (the documents) and `reviewer` (blind gate).

## What it is for

Drawing the whole system once, deciding where it runs, and writing down what can go wrong and where each risk is stopped, before any design or code depends on it.

## What you will be asked

Only what is still undecided, one area at a time with options and a recommended default ("default" is a valid answer; "not needed" needs a reason): the stack pack, which apps and services are separate deployments, environments and namespaces, ingress, database placement, secrets path, observability, release and rollback; then threats for tenancy, auth, secrets, uploads, webhooks and, if your compliance decision says yes, compliance. Any new service is introduced with what it is, what it will do, why nothing in use does it and its verified cost; nothing is added until you say so.

## Output files

`docs/architecture/ARCHITECTURE.dot` (+ `ARCHITECTURE.svg`), `docs/architecture/DEPLOYMENT.md`, `docs/architecture/THREATS.md`, one decision per answer, and the gate's verdict in `docs/reviews/06-architecture-review.md`.

## What this step does not do

It copies no stack templates. It records the chosen pack (`nextjs-fastapi`) and writes the Helm and environment layout (local, staging, production, each with its values file) as a document. The pack's templates are copied in a later release.

## Checks and gate

`dot -Tcanon` passes, the diagram renders, and every service decided in step 4 appears in it. Every threat has a mitigation and a named place where it is enforced. Then a blind `reviewer` reads the three outputs and must return `VERDICT: APPROVE`, written to `docs/reviews/06-architecture-review.md`; a `REJECT` means rework and re-review. Only then do you give the go.

## Who approves

The reviewer first, then you.

## Re-entry

A changed answer is a new decision that supersedes the old one and lists the outputs it makes stale; they stay in `STATE.md ▶ STALE` until updated.

## Hand-off

`STATE.md` is set to `STEP: 7 — Figma`.

Next: [step 7: Figma](07-figma.md).
