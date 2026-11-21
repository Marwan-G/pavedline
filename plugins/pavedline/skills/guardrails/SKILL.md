---
name: guardrails
description: The system guardrails registry, SYSTEM-GUARDRAILS.md, and how every decision, slice, deploy and launch keeps it true. Use when a decision is recorded (it answers the four guardrail questions), when a step sets a limit, a rule or a target, when a slice is planned, built, reviewed or deployed, for the consistency review (before step 8, before step 12, on request), and to adopt the registry in a project that has none yet.
---

# guardrails

A **guardrail** is a constraint the system must keep: a security control, a tenant-isolation rule, a connection or
rate limit, a latency target, a retry or idempotency policy, a retention period, a job rule, an infrastructure or
network rule, a service boundary. Decisions create them one at a time, in many files. Nothing lists them together,
says where each is enforced and how it is checked, or notices when two files disagree, unless one file does.

`SYSTEM-GUARDRAILS.md`, at the repository root, is that file. **It is an index, never a home.** A value lives in its
decision or its detailed document (for example a database-operations or runbook file); the registry quotes it and
names that home. If the registry and a home disagree, the home wins and the registry has a defect.

**It is a shared record, like `STATE.md`:** only the session on `OWNER` writes it. Other sessions and agents (the
builder, reviewers, research lanes) report guardrail changes in their `handoff/<branch>.md`, and the owner folds them
in when the branch merges.

## The registry

Create it with the first decision that introduces a guardrail, or by adoption (below), with this header:

```
# System guardrails

An index of every constraint the system must keep. Each entry names its home: if this file and its home disagree,
the home wins and this file has a defect. Written only by the session on OWNER (the `guardrails` skill).

Last consistency review: <YYYY-MM-DD>, decision <NNNN>. Statuses: PROPOSED · APPROVED · IMPLEMENTED · TESTED ·
VERIFIED · OPEN · SUPERSEDED.

## 1. Inventory
## 2. Entries
## 3. By source decision
## 4. Consistency review
```

1. **Inventory:** one row per guardrail, `| ID | Guardrail | Status | Source | Flags |`, grouped by domain, then a
   count line by status.
2. **Entries:** one block per guardrail, grouped by domain (format below).
3. **By source decision:** `| Decision | Guardrails it introduced or restates |`.
4. **Consistency review:** the latest review's findings, and the rulings on them.

### Entry format

```
#### DB-CONN-001 · API connects through the pooler in transaction mode
- **Category** Database connections · **Status** APPROVED · **Source** 0042, 0051
- **Rule:** the explicit constraint, with its value quoted from the home.
- **Rationale:** why it exists.
- **Scope:** the services and components it applies to.
- **Enforcement:** where it is actually enforced (`file:line`, a CI check, a database grant), or "Not built".
- **Configuration:** where its value is configured: the home document and section.
- **Validation:** the test or check that proves it (acceptance-test id, CI job, drill), or "none named".
- **Related:** guardrails it depends on or interacts with. **Flags:** C-n, G-n, Q-n.
```

### IDs and domains

`<DOMAIN>-<AREA>-<NNN>` (for example `SEC-AUTH-001`, `REL-RETRY-002`), or `<DOMAIN>-<NNN>` for a domain without areas
(`CACHE-001`). An ID is stable: a changed guardrail keeps it, and a removed one stays in the file as `SUPERSEDED`.
**An ID is never reused.** A new guardrail takes the next free number.

| Domain | Prefix | Example areas (add your own) |
|---|---|---|
| Security and access control | `SEC` | AUTH, SECRET, CRYPTO, DATA, AUDIT, BROWSER, UPLOAD |
| Database and tenant isolation | `DB` | ISOLATION, ROLE |
| Database connections and resource management | `DB` | CONN |
| Performance and capacity | `PERF` | TARGET, LIMIT, QUERY |
| Caching | `CACHE` | — |
| Rate limiting | `RATE` | — |
| Reliability and failure handling | `REL` | IDEM, RETRY, FAIL, HA, BACKUP |
| Data lifecycle and retention | `DATA` | RETENTION, DELETE, EXPORT, INTEGRITY |
| Scheduling and background jobs | `JOB` | QUEUE, SCHED, TIME |
| Infrastructure and networking | `INFRA` | NET, K8S, IAC, REGION, COST, OBS |
| Service boundaries and operations | `OPS` | BOUND, REC |

A project keeps the IDs it already has, even when they differ from these examples. A new domain needs a decision.

### Statuses

| Status | Meaning | Evidence it needs |
|---|---|---|
| `PROPOSED` | written in a design document, not yet accepted | the document |
| `APPROVED` | accepted in a decision | the decision number |
| `IMPLEMENTED` | code or configuration exists | the `file:line` of that code or configuration |
| `TESTED` | its validation passed | the test id and a passing run (CI run, or the command and its output) |
| `VERIFIED` | confirmed in a deployed environment | `local` or `cloud`, the date, and the check that was run |
| `OPEN` | a decision requires it, but no rule or value is approved yet | the decision that requires it |
| `SUPERSEDED` | replaced or removed; the entry stays | the decision that replaced it |

A status **never rises on documentation alone**, and never on an agent's report alone: re-run the evidence or read it
yourself. The only qualifiers are `(provisional)`, `(assumption)`, `(value open)` and `(template)`, for example
`APPROVED (value open)`; each says exactly what is missing. `IMPLEMENTED (template)` is configuration copied into the
project that no decision has adopted yet.

## Recording a decision: the four questions

Every decision record has a `## Guardrails` section, before `## Stale outputs`:

```
## Guardrails

- Introduces: <IDs, or none>
- Modifies: <IDs and what changed, or none>
- Removes or supersedes: <IDs, or none>
- Conflicts with: <IDs, or none>
```

The owner updates the registry **in the same commit** as the decision:

- **Introduces:** add an entry and an inventory row, with the decision as its Source.
- **Modifies:** keep the ID, change the rule, and add the decision to its Source.
- **Removes or supersedes:** mark the entry `SUPERSEDED` with the decision, and keep it.
- **Conflicts with:** do not record the decision yet. Show the founder both sides and a recommendation, through the
  question dialog. A conflict is never resolved silently, nor by editing an accepted decision. If the new decision
  is itself the founder's ruling on the conflict, record it as superseding the decision it overrules.

**One home per value.** When a value changes, its home and the registry change in the same commit. A value that is
written in a second document is listed under "values in more than one place" until that copy cites the home instead.

**Never invent a value.** A limit the decisions do not set is an `OPEN` guardrail with a gap flag, not a guess. A fact
reasoned rather than read is marked `[inferred]`.

## What each step does

| Step | Duty |
|---|---|
| Steps 1–3 | Decisions that constrain the system (retention, residency, age limits) enter the registry as they are recorded. The spec's non-functional needs enter it at step 3, as `APPROVED (provisional)` while they are assumptions. |
| Steps 4–7 | Each area's proposal names the guardrails it introduces or changes, before the founder answers; each decision's Guardrails section records them. |
| Step 8 | Run the consistency review. Each slice in the plan has a `Guardrails:` line naming the IDs it implements or tests. A guardrail with no slice and no reason is a gap in the plan. |
| Step 9 | The builder lists in its hand-off each guardrail the slice implemented or tested, with `file:line` and the test evidence. Reviewers check the slice against its `Guardrails:` line; a slice that breaks a guardrail is a REJECT. At merge, the owner folds the list into the registry: `IMPLEMENTED` with `file:line`, `TESTED` once the merge-gate verification passes. |
| Step 10 | A deploy whose post-deploy check proves a guardrail raises it to `VERIFIED (local)`, with the date and the check. |
| Step 11 | A lesson whose rule is a system constraint (security, a limit, retention, a job or infrastructure rule) becomes a guardrail through a decision. Other rules go to their home, as the `lessons` skill says. |
| Integration wave | Guardrails that depend on real providers (webhooks, sign-in, messaging, payments) are tested against them. |
| Step 12 | Run the consistency review once more. The launch checklist item for guardrails is ticked only when every guardrail a launch item depends on is `VERIFIED (cloud)` or accepted in a decision. |

After launch, the Grow loop does not change guardrails. An incident or a review that does change one goes through a
decision.

## Consistency review

Run it at adoption, before step 8, before step 12, and whenever the founder asks. Read every accepted decision, the
detailed documents, the spec's non-functional needs and the infrastructure files, then record in section 4:

1. **Contradictions** (`C-n`): two sources that disagree, quoted with their places, and a recommendation.
2. **Missing values or enforcement** (`G-n`): a guardrail without its number, its enforcement point or its home
   document.
3. **Constraints without a validation test.**
4. **Values written in more than one place**, with the proposed single home.
5. **Dependencies** between guardrails that must be decided together (for example, connection limits that share one
   capacity budget).
6. **What cannot be verified yet**, and what it waits for (a region, a rehearsal, real users, counsel).
7. **Questions** (`Q-n`), each with a recommended answer.

Show the findings as text, then ask for the rulings through the question dialog, at most four questions per dialog,
as `step-rules.md` asks. Record the accepted recommendations as one decision that lists each ruling. A finding whose
recommendation was only "decide" or "ask" stays open until the founder answers it. Fix the documents a ruling
corrects in the same commit, and keep each finding, marked ruled, in section 4.

## Adopting the registry in a project that has none

A project started before this skill existed has decisions but no registry. Do not block any step on adoption: offer
it once, and adopt when the founder says go.

1. Read every accepted decision (superseded ones only through the decision that replaced them), the detailed design
   and operations documents, the spec's non-functional needs, and the infrastructure and CI files.
2. Write `SYSTEM-GUARDRAILS.md` with the header above and an entry for every guardrail found. Quote values, never
   change them. Set statuses from evidence only: in a project with no code, nothing is above `APPROVED` except copied
   templates.
3. Run the consistency review.
4. Show the draft for one approval. On approval, record a decision that adopts the registry and this process. Add
   the `## Guardrails` section to the project's `decisions/0000-template.md` if it is missing, and a row for the
   registry to `docs/rules-index.md`.

Before showing the registry, check that the inventory and the entries carry the same IDs, that no ID appears twice,
and that every flag used is defined in section 4.
