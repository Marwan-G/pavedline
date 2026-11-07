---
name: start
description: Starts a new Pavedline product (step 0). Checks the machine, asks the platform questions one at a time, copies the project templates and records each answer as a decision. Run it once, in the repository of the new product, by typing /pavedline:start.
disable-model-invocation: true
allowed-tools: Bash(python3 *) Bash(date *) Bash(git rev-parse *) Bash(git init*) Bash(git add *) Bash(git commit *)
---

# start

Step 0 of Pavedline. You run it in the repository of the new product. Follow the steps in order. Do not skip ahead and do not batch questions.

## 1. Check the machine

Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

Relay each fix exactly as printed. If the last line says a required check failed, stop here and tell the user to fix it and run `/pavedline:start` again. Never install anything without the user's go.

## 2. Say the privacy line

Print this line verbatim, before the first question:

Pavedline collects nothing. Every answer stays in your own repository.

## 3. Ask the questions, one at a time

Ask one question, wait for the answer, then ask the next. State the default with each question; the user can answer "default". Keep the order.

1. **What are you building?** One paragraph: who it serves, the problem, the one thing it must do well. No options.
2. **Multi-tenant?** Follow the `architecture-intake` skill for this question.
3. **Compliance.** Follow the `compliance` skill. It uses its own exact wording.
4. **Solo or team?** Default: solo. Team means parallel sessions in their own worktrees, and approvals move to GitHub pull requests.
5. **Surfaces.** Follow the `architecture-intake` skill (default: all four).
6. **Database: in Kubernetes (CNPG) or a managed service?** Follow the `architecture-intake` skill.
7. **Local runtime.** Follow the `architecture-intake` skill.

Say plainly, once, before or after the questions: the cloud provider is NOT asked now. It is chosen at step 12, when the product is ready for production. Production accounts (cloud, domain, app stores) are asked just in time, when a step needs them. Figma is asked at step 7.

Do not ask anything else at step 0. If the user volunteers more, note it in the matching decision and move on.

## 4. Create the project files

First check the target is a git repository:

```
git rev-parse --is-inside-work-tree
```

If it is not, ask the user before running `git init`. Never initialise silently. If the user says no, stop and explain that Pavedline keeps its records in git.

Propose the project name: a short kebab-case slug (letters, digits, hyphens) made from answer 1. Show it and let the user confirm or change it. It also names the local cluster `pavedline-<project>`. Take the mode from answer 4 (`solo` or `team`). Then run, from the repository root:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/start_project.py" --target . --name <name> --mode <solo|team>
```

The script never overwrites. If it exits 1 and lists `conflict:` lines, write nothing yourself. Show the conflicts and ask the user whether to move those files aside or to start elsewhere, then stop.

## 5. Record the answers

- Write answer 1 into `PRODUCT.md`, replacing the placeholder paragraph. One paragraph only.
- Write exactly one decision record per question, seven in all, in `decisions/`, in the format of `decisions/0000-template.md`, numbered in question order: `0001` product statement (question 1, also in `PRODUCT.md`), `0002` multi-tenancy (question 2; the isolation model, if asked, goes in the same record), `0003` compliance (question 3; one record for yes or no, written as the `compliance` skill says), `0004` solo or team, `0005` surfaces, `0006` database, `0007` local runtime. File name: `NNNN-short-title.md`. Status `accepted`, date from `date +%F`, "Stale outputs" `none`.
- In each Consequences section say what the answer means for later steps (see the `architecture-intake` skill).

## 6. Point STATE.md at step 1

Edit `STATE.md` (see the `state` skill for the rules) and set these lines. Take the timestamp from `date "+%Y-%m-%d %H:%M"`, never from memory.

```
STEP: 1 — Market + SEO research
LAST: <timestamp> — step 0 done: PRODUCT.md and decisions 0001–0007 written
NEXT: step 1 — ask which competitors and sites the founder already has in mind, then start the market and SEO research
```

Commit the new files in one commit. If the repository already has commits by someone else, ask the user for a go before committing.

## 7. Close and wait for the go

End with a short summary:

- what was created (files and the decisions, one line each);
- anything only the user can do (for example installing a tool `doctor` reported missing): add each to `WAITING.md` as `- Fn · what · where/how · what it unblocks` and list it here;
- the next step: market and SEO research.

Then ask: **go?** Step 1 starts only when the user says go. Do not start it on your own.
