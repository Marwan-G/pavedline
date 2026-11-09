# Step 9: Build (per slice)

Starts when `STATE.md` says `STEP: 9` and you say go. Skill: `quality-gates`. Agents: `builder`, `reviewer`, `adversary`.

## What it is for

Building one approved slice of the wave through five gates, in order: TDD, code review, security review (plus an adversarial review when the slice touches risky ground), verification, merge. The builder works alone in its own git worktree; reviewers read the diff and the scanner output, never the builder's summary.

## What you will be asked

Normally nothing: the wave is already approved. You are asked before a new service is added, and when a reviewer rejects something the orchestrator cannot settle.

## Output files

The slice's branch and pull request, `handoff/<branch>.md` while the slice is open, and the gates line in the PR description: `Gates: TDD ✓ · review ✓ (n found, m fixed) · security ✓ · adversarial ✓|n/a · verification ✓`. Every unfixed finding is listed as `accepted — <reason>`.

## Checks and gate

The five gates, each with its own evidence. The orchestrator re-runs the verification commands itself; the full test suite runs once, at the merge gate, on a branch rebased on the default branch. `scripts/pr_checks.py` rejects a PR without the gates line, and two warning hooks remind you (a PR body without the line; a changed folder whose `ARCHITECTURE.dot` is untouched).

## Who approves

The reviewers' verdicts gate the merge; you approve the wave before and read the result after.

## Re-entry

A reject means rework and one narrow re-check. A fixed HIGH finding needs a full new review. A small change (a bug fix or a copy edit) skips steps 1 to 8.

## Hand-off

After the wave's last slice merges, `STATE.md` is set to `STEP: 10 — Deploy`.

Next: [step 10](10-deploy.md) deploys the merged change to the local cluster.
