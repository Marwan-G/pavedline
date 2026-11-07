# {{PROJECT_NAME}}

Project memory for Claude Code. Started {{DATE}} with Pavedline, mode `{{MODE}}`. This file holds orientation and
standing rules only. No history lives here: history goes to `decisions/` and `docs/archive/`.

Pavedline collects nothing. Every answer stays in your own repository.

## Reading order (every session, before any work)

1. `CLAUDE.md` (this file, at most 150 lines).
2. `PRODUCT.md`: the one-paragraph product statement.
3. `STATE.md` (at most 60 lines): STEP, WAVE, SLICES IN FLIGHT, LAST, NEXT, LEFT BEHIND, STALE, GROW DUE, OWNER, MODE.
   A missing MODE means review-only: write no code.
4. `WAITING.md`: every step only the founder can take. Remove an item only on the founder's word.
5. `decisions/NNNN-*.md`: ADRs, dated, append-only; a changed decision is superseded by number, never edited.
6. `GLOSSARY.md`: one name per concept across UI, API, database and code.
7. `handoff/<branch>.md`: one per working branch, folded into `STATE.md` on merge.
8. `docs/archive/`: overflow and history. `docs/rules-index.md`: where each rule lives.

## Where rules live

Every rule has one home, listed in `docs/rules-index.md`. Fix a rule there, not in a copy. Commands to run the
product are in `RUN.md`; external services and where their secrets live (never the values) in `SERVICES.md`;
useful links in `LINKS.md`; the architecture diagram in `ARCHITECTURE.dot` (the rendered `ARCHITECTURE.svg` is
committed beside it).

## Who asks what: no question twice

Step 0 asks platform questions. Step 2 (grill) asks product decisions. Step 4 asks system and stack questions.
Superpowers brainstorming runs only inside a wave, for one feature's design. These instructions take precedence over
superpowers' brainstorming skill: before it asks anything it reads `PRODUCT.md`, `decisions/`, `GLOSSARY.md` and
`SPEC.md` (in `docs/spec/`), and it asks only what is still undecided.

## Wave protocol

One approval starts one wave. The wave ends by verifying, updating the records, stating the next recommended wave,
and stopping. Never continue into the next wave on your own. The next wave is re-derived from the files, not
inherited from the conversation.

## Standing rules

- One writer for `STATE.md`: solo, the main session; team, the person on `OWNER`. Other sessions work in their own
  `git worktree` and write only their hand-off in `handoff/`.
- Timestamps come from `date`, never from memory or estimation.
- Commit after every state change. Push after every state change only when the founder has allowed pushing for this
  project; the founder decides. Records merge at milestones.
- Before redoing any work, check the remote: a stalled agent may already have pushed.
- Never commit secrets. Keep them in the secret store named in `SERVICES.md`.
- Before any new service or billable resource, even a free one, say what it is, what it will do, why nothing already
  in use does it, and its verified cost. The founder approves first.

## Opening and closing blocks

Open every session with a short block: current state, recommended next step, and what needs approval. Close every
session that changed anything with: done, changed, next, waiting on you (all open items from `WAITING.md`), and
whether it is safe to clear the session. Update `STATE.md` before the closing block.

## Pull request gates

Every slice passes five gates in order: TDD (red first), code review, security review (plus an adversarial review
on auth, tenancy, IAM, infra, CI, secrets, input parsing, payments and migrations), verification, merge. The PR
description carries this line, and CI fails without it:

`Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓`

`✗` is not a valid value. List every unfixed finding as `accepted — <reason>`.
