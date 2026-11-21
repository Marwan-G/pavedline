---
name: guardrails
description: The system guardrails registry, SYSTEM-GUARDRAILS.md, and how every decision, slice, deploy and launch keeps it true. Use when a decision is recorded (it answers the four guardrail questions), when a step sets a limit, a rule or a target, when a slice is planned, built, reviewed or deployed, before step 8 and step 12 (the consistency review), and to adopt the registry in a project that has none yet.
---

# guardrails

A **guardrail** is a constraint the system must keep: a security control, a tenant-isolation rule, a connection or
rate limit, a latency target, a retry or idempotency policy, a retention period, a job rule, an infrastructure or
network rule, a service boundary. Decisions create them one at a time, in many files. Nothing lists them together,
says where each is enforced and how it is checked, or notices when two files disagree, unless one file does.

`SYSTEM-GUARDRAILS.md`, at the repository root, is that file. **It is an index, never a home.** A value lives in its
decision or its detailed document (for example a database-operations or runbook file); the registry quotes it and
names that home. If the registry and a home disagree, the home wins and the registry has a defect.

## The registry

Four sections, in this order:

1. **Inventory:** one table row per guardrail, `| ID | Guardrail | Status | Source | Flags |`, grouped by domain, then
   a count line by status.
2. **Entries:** one block per guardrail, grouped by domain (format below).
3. **By source decision:** `| Decision | Guardrails it introduced or restates |`.
4. **Consistency review:** the latest review's findings, and the rulings on them (see below).

Create the file with the first decision that introduces a guardrail, or by adoption (below). Its header states that
it is an index, the statuses, and the date and decision of its last review.

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

`<DOMAIN>-<AREA>-<NNN>`, for example `SEC-AUTH-001`, `DB-ISOLATION-002`, `REL-RETRY-001`, `INFRA-NET-003`. An ID is
stable: a changed guardrail keeps it, and a removed one stays in the file marked `SUPERSEDED by NNNN`. **An ID is never
reused.** A new guardrail takes the next free number in its area.

| Domain | Prefix | Examples of areas |
|---|---|---|
| Security and access control | `SEC` | AUTH, SECRET, CRYPTO, DATA, AUDIT, BROWSER, UPLOAD, BOUNDARY |
| Database and tenant isolation | `DB` | ISOLATION, ROLE |
| Database connections and resource management | `DB` | CONN |
| Performance and capacity | `PERF` | TARGET, LIMIT, QUERY |
| Caching and rate limiting | `CACHE`, `RATE` | (none: `CACHE-001`, `RATE-001`) |
| Reliability and failure handling | `REL` | IDEM, RETRY, FAIL, SYNC, CONC, HA, BACKUP |
| Data lifecycle and retention | `DATA` | RETENTION, LIFE, DELETE, EXPORT, INTEGRITY |
| Scheduling and background jobs | `JOB` | QUEUE, SCHED, TIME |
| Infrastructure and networking | `INFRA` | NET, K8S, IAC, REGION, COST, OBS |
| Service boundaries and operations | `OPS` | BOUND, UI, SUSPEND, REC, FAIL |

Add an area when a product needs one. Never add a domain without a decision.

### Statuses

| Status | Meaning | Evidence it needs |
|---|---|---|
| `PROPOSED` | written in a design document, not yet accepted | — |
| `APPROVED` | accepted in a decision | the decision number |
| `IMPLEMENTED` | code or configuration exists | the `file:line` of that code or configuration |
| `TESTED` | its validation passed | the test id and a passing run (CI run, or the command and its output) |
| `VERIFIED` | confirmed in a deployed environment | `local` or `cloud`, the date, and the check that was run |
| `OPEN` | a decision requires it, but no rule or value is approved yet | the decision that requires it |

A status **never rises on documentation alone**, and never on an agent's report alone: re-run the evidence or read it
yourself. `APPROVED (provisional)`, `APPROVED (value open)` and `APPROVED (assumption)` say exactly what is still
missing. A template copied into the project but used by no decision is `IMPLEMENTED (template)`, with no source
decision, until a decision adopts it.

## Recording a decision: the four questions

Every decision record has a `## Guardrails` section, before `## Stale outputs`:

```
## Guardrails

- Introduces: <IDs, or none>
- Modifies: <IDs and what changed, or none>
- Removes or supersedes: <IDs, or none>
- Conflicts with: <IDs, or none>
```

The registry changes **in the same commit** as the decision:

- **Introduces:** add an entry and an inventory row, with the decision as its Source.
- **Modifies:** keep the ID, change the rule, and add the decision to its Source.
- **Removes or supersedes:** mark the entry `SUPERSEDED by NNNN` and keep it.
- **Conflicts with:** stop. Show the founder both sides and a recommendation.
  A conflict is asked and never resolved silently, nor by editing an accepted decision; the ruling is a new decision.

**One home per value.** When a value changes, its home and the registry change in the same commit. A value that is
written in a second document is listed under "values in more than one place" until that copy cites the home instead.

**Never invent a value.** A limit the decisions do not set is an `OPEN` guardrail with a gap flag, not a guess. A fact
reasoned rather than read is marked `[inferred]`.

## What each step does

| Step | Duty |
|---|---|
| Steps 1–3 | Product decisions that constrain the system (retention, residency, age, uptime, latency and other non-functional targets in the spec) enter the registry as they are recorded; spec assumptions are `APPROVED (provisional)`. |
| Steps 4–7 | Each area's proposal names the guardrails it introduces or changes, before the founder answers. Before a step closes, run the consistency review on what it touched. |
| Step 8 | Each slice in the plan names the guardrail IDs it implements or tests, next to its acceptance tests. A guardrail with no slice and no reason is a gap in the plan. |
| Step 9 | The builder raises a guardrail to `IMPLEMENTED` with `file:line`, and to `TESTED` only after the gates' verification run passes. Reviewers check the slice against the guardrails it names; a slice that breaks one is a REJECT. |
| Step 10 | A deploy whose post-deploy check proves a guardrail raises it to `VERIFIED (local)`, with the date and the check. |
| Step 11 | A lesson that becomes a rule becomes a guardrail, through a decision. |
| Integration wave | Guardrails that depend on real providers (webhooks, sign-in, messaging, payments) are tested against them here. |
| Step 12 | Run the consistency review once more. Every guardrail behind a launch-checklist item must be `VERIFIED (cloud)`; one that is not is a blocking launch item, or is accepted in a decision. |

After launch, the Grow loop does not change guardrails; an incident or a review that does goes through a decision.

## Consistency review

Run it at adoption, before a design step closes, before step 8, before step 12, and whenever the founder asks. Read
every accepted decision, the detailed documents, the spec's non-functional needs and the infrastructure files, then
record in section 4:

1. **Contradictions** (`C-n`): two sources that disagree, quoted with their places, and a recommendation.
2. **Missing values or enforcement** (`G-n`): a guardrail without its number, its enforcement point or its home
   document.
3. **Constraints without a validation test.**
4. **Values written in more than one place**, with the proposed single home.
5. **Dependencies** between guardrails that must be decided together (for example, connection limits that share one
   capacity budget).
6. **What cannot be verified yet**, and what it waits for (a region, a rehearsal, real users, counsel).
7. **Questions** (`Q-n`), each with a recommended answer.

Show the findings to the founder in one turn. A recommendation the founder accepts is recorded as one decision that
lists each ruling; a finding whose recommendation was only "decide" or "ask" stays open until the founder answers it.
Fix the documents a ruling corrects in the same commit, and keep each finding, marked ruled, in section 4.

## Adopting the registry in a project that has none

A project started before this skill existed has decisions but no registry. Do not block any step on adoption: offer
it once, and adopt when the founder says go.

1. Read every accepted decision (superseded ones only through the decision that replaced them), the detailed design
   and operations documents, the spec's non-functional needs, and the infrastructure and CI files.
2. Write `SYSTEM-GUARDRAILS.md` with an entry for every guardrail found: values quoted, never changed; statuses from
   evidence only (in a project with no code, nothing is above `APPROVED` except copied templates).
3. Run the consistency review.
4. Show the draft as one approval turn. On approval, record a decision that adopts the registry and this process, add
   the `## Guardrails` section to the project's `decisions/0000-template.md` if it is missing, and add a row for the
   registry to `docs/rules-index.md`.

Check the inventory against the entries before showing it: the same IDs on both sides, no ID twice, and every flag
used is defined in section 4.
