---
name: backend-evaluate
description: Checks the preferred backend (FastAPI) against the spec with sources, names what it would struggle with, compares alternatives only then, and recommends. Used by system-design in round 1; the founder decides.
---

# backend-evaluate

Part of step 4. Output: a short report `docs/architecture/BACKEND-EVALUATION.md` (create `docs/architecture/` when missing; a v0.1 project lacks it) and a decision. The `researcher` agent (subagent type `pavedline:researcher`) gathers the evidence; every claim has a URL and a date, marked definite, inferred or unknown. Versions and support status come from the web now (`${CLAUDE_SKILL_DIR}/references/sources.md`), never from memory. Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

**FastAPI is the preferred default.** It stays the answer unless the evaluation finds a blocker.

## 1. Read

`docs/spec/SPEC.md` (must-have features, non-functional needs), decisions 0002, 0003 and 0005, `PRODUCT.md`.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. Pass criteria

FastAPI passes when all three hold:

1. every must-have need has a supported, maintained path;
2. there is no blocker in concurrency, real-time or background work;
3. the team can run it.

Walk the spec's must-have needs one by one against the criteria and say which fails and why. **Next.js is frontend only**; the backend is the place for all business logic.

## 3. If something fails

Name exactly what FastAPI would struggle with. Only then compare alternatives, with sources, against the same criteria. Never compare alternatives when FastAPI passes.

## 4. Recommend, then ask

State the recommendation and what it changes. **The founder decides.** Record the answer as a decision (format of `decisions/0000-template.md`, number after the highest existing). A new service or paid tool that the choice would add follows the ask-before-adding rule (what it is, what it will do, why nothing in use does it, verified cost), never designed to a free tier.
