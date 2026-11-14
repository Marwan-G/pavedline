# Shared step rules (the guided step skills)

Every guided step skill (`system-design`, `domain-model`, `db-schema`, `api-contract`, `system-architecture`, `threat-model`, `multi-tenancy`, `backend-evaluate`, `design-system-contract`, `plan-graph`, and the build-side steps such as `deploy` and `lessons`) follows these rules; the parts that name decisions and questions apply where the skill asks any. A skill adds only what is specific to it: its areas, its outputs, its gate and its close.

## Read first

Read the records in the order of the `state` skill: `CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `docs/business/VISION.md` if it exists (the founder's full vision: input, not a decision), then the files the skill names. If `STATE.md` names an earlier step than the skill's own, say so and ask. Ask only what is undecided: never re-ask an answer an earlier step or decision already gave.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked. A choice named by the founder in `docs/business/VISION.md` is proposed as the answer and checked, not compared; it is recorded as a decision once the founder confirms it.

## Agents

Design work goes to the `architect` agent (subagent type `pavedline:architect`), vendor and version facts to the `researcher` agent (subagent type `pavedline:researcher`), each with a self-contained prompt: the files to read, the document to write, the report format. Run agents in the foreground and never wait on a background task or timer: a non-interactive session stalls or ends while it waits.

## How to ask

One area at a time, in the order of the skill's areas file (where the skill has one): say what it decides, give the options, state the recommended default and what it changes, then wait. "Default" is a valid answer; "Not needed" is valid only with a recorded reason. No area may be skipped silently or merged into another area: ask every area in the order of the list, and before closing a round compare the areas of the skill with the decisions written, then ask any area that has none.

Ask through the question dialog (`AskUserQuestion`), so the founder always sees where they are and what to do next. The header shows the place as `Area n/N`, for example `Area 3/9` or `Area 10/10` (the dialog allows at most 12 characters). The dialog has 2 to 4 options. The recommended default is the first, labelled "(Recommended)", and each option's description says what it changes. Claude Code adds "Other" for the founder's own words: "default" and `default for the rest of this round` are typed there. After an answer, record it and ask the next area in the same turn. The fill-in list and a gate or step approval are shown as text first, then asked in the dialog ("Approve all (Recommended)" or "Change some"; "Go (Recommended)" or "Not yet"). An open question with no options, or a run with no dialog, is asked in plain text, ending with one line: `Reply with an option, "default" or your own answer. Next: <the next area or step>.` Never end a turn on a question without the dialog or that line.

One decision per answer: record each as a decision (format of `decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record. A step's own gate or approval question is never answered by `default for the rest of this round`, which covers only area questions.

## Preferences and rules live in the repository

A preference or rule the founder states (for example "never push without asking") goes into a decision (ADR) or `STATE.md`, never only into the agent's auto-memory: a fresh clone, or another machine, must see it.

## Ask before adding

A new service or billable resource, even a free one, follows the ask-before-adding rule: say what it is, what it will do, why nothing already in use does it and its verified cost, then wait for the founder to approve. Costs are checked on the web at expected usage (the skill's `references/sources.md`) and never designed to a free tier. Add each approved service to `SERVICES.md`.

## One fill-in turn

Before writing outputs, compare the decisions for gaps and contradictions; the `architect` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

## Tenant naming (step 5)

The tenant column is always named `tenant_id` and the setting `app.tenant_id`, even when the glossary calls the tenant something else (an organisation, a workspace, an account): the glossary records the mapping, and Pavedline's CI schema check looks for these names.

## Re-entry

Any of steps 1 to 7 can be reopened. A changed answer is a new decision that supersedes the old one (`Status: superseded by NNNN` on the old file; the new one says `supersedes NNNN`). List the downstream outputs it makes stale in its "Stale outputs" section and add each to `STATE.md ▶ STALE` with the decision number; they stay there until updated.

## Closing a step

The step's last skill closes it. Edit `STATE.md` as the skill's close shows (time from `date "+%Y-%m-%d %H:%M"`), commit, print the closing block (done, changed, next, waiting on you, clear-safe) and ask: **go?** The founder approves each decision; do not move on without that.
