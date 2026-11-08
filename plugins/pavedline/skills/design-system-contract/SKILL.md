---
name: design-system-contract
description: Step 7 of Pavedline. Builds the design system and every screen in Figma and records it in docs/design/DESIGN.md and docs/design/tokens.json - tokens in light and dark, type, spacing, components named exactly as in code, a FigJam flow, one frame set per surface, every screen in every state, the tenant-lifecycle and release screens, accessibility annotations, Code Connect (or a name table). Then the blind design-verifier gate and the founder's visual approval. Use while STATE.md says STEP 7.
---

# design-system-contract

Step 7. The designer builds in Figma; this skill is the contract between Figma and code. Outputs: `docs/design/DESIGN.md`, `docs/design/tokens.json`, the Figma file (private), the gate verdict in `docs/reviews/07-figma-review.md`, and one decision per answered question. Create `docs/design/` and `docs/reviews/` when missing. All Figma writing goes to the plugin's `designer` agent (subagent type `pavedline:designer`, never a general-purpose agent) with a self-contained prompt (files to read, the Figma file, what to build, report format); the `designer` is the only agent that writes to Figma. Run it in the foreground and never schedule a wake-up or wait on a background timer: a non-interactive session ends or stalls while it waits. Vendor and version facts go to the `researcher` agent (subagent type `pavedline:researcher`).

## 0. Before anything else

- If the Figma login is missing, stop and add it to `WAITING.md` (what: connect the Figma plugin and log in; where: `/mcp`, then the Figma sign-in; unblocks: step 7). Do not design offline.
- Check the plan and seat with the Figma `whoami` tool. Code Connect is documented for a Full or Dev seat on a Professional or higher plan, but the MCP mapping tool refused a Professional plan in a real run (it said mappings need an Organization or Enterprise plan; `${CLAUDE_SKILL_DIR}/references/sources.md`). So: try the mapping once; if it is refused, use the name table and say why. Do not promise Code Connect to the founder in advance.
- A Figma file is a new resource: follow the ask-before-adding rule (what it is, what it will do, why nothing in use does it, its verified cost) and create ONE new private file only after the founder says so. Never put its link, file key or node ids in anything outside `docs/design/DESIGN.md` (node ids may also appear in `docs/reviews/07-figma-review.md`).

## 1. Read first, in order

`CLAUDE.md`, `PRODUCT.md`, `STATE.md`, `WAITING.md`, every file in `decisions/`, `GLOSSARY.md`, `docs/spec/SPEC.md`, `docs/architecture/SYSTEM-DESIGN.md`, `TENANCY-LIFECYCLE.md`, `DEPLOYMENT.md`, `docs/data/DOMAIN.md` and `SCHEMA.md`, `docs/api/openapi.yaml`, and any existing `docs/design/`. If `STATE.md` says `STEP: 7 — Figma`, continue; if it says an earlier step, say so and ask. Surfaces come from decision 0005 (a dropped surface gets no frames). Ask only what is undecided.

An area already answered by a decision is shown as `decided in NNNN` and not re-asked; only its undecided detail is asked.

## 2. Questions (one area at a time; options, recommended default, what it changes; wait)

"Default" is valid; "not needed" only with a recorded reason. None is skipped or merged; before closing compare the areas with the decisions written. Areas, in order, details in `${CLAUDE_SKILL_DIR}/references/areas.md`: Figma account and file · brand and style direction (`ui-ux-pro-max` is a reference for this, never copied; `impeccable` is optional critique, use it only if installed) · tokens and themes · type and spacing · component set · surfaces and navigation · FigJam flows · accessibility targets · the code naming rule. Record each answer as a decision (`decisions/0000-template.md`, numbered after the highest existing, with a "Stale outputs" section). Within a round the founder may answer `default for the rest of this round`; each area still gets its own decision record. A new service or plugin: ask-before-adding.

**One fill-in turn.** Before building, compare the decisions for gaps and contradictions; the `designer` resolves each gap with the recommended default and lists it. Show all fill-ins as ONE numbered list for one approval turn ("default" approves all); a fill-in that changes an existing decision is asked on its own.

## 3. Build, in this order

Use the Figma plugin's skills, loading each before its tool: `figma-use` (before every `use_figma` write), `figma-generate-library` (variables, components), `figma-generate-design` (screens from the records), `figma-use-figjam` (flows), `figma-code-connect` (the mapping). Open a session for the file first; search the existing library before drawing.

1. **Tokens.** Colour, type and spacing variables in light and dark; no hard-coded value where a variable exists. Export them to `docs/design/tokens.json` (same names, both modes).
2. **Components.** Figma name = code name: a component is named exactly as the component the code will have (`PascalCase`, glossary words), with variants for every state it has. Record the rule in `DESIGN.md`.
3. **Screens.** One frame set per surface (decision 0005); every screen in every state: empty, loading, error, partial, success, no permission, and offline on mobile; mobile and desktop layouts. Screens show real fields from `DOMAIN.md` and `openapi.yaml`; labels use `GLOSSARY.md` words. Plus the required screens in `${CLAUDE_SKILL_DIR}/references/screens.md`: suspended tenant, export, delete, impersonation banner and legal pages (from `TENANCY-LIFECYCLE.md`), and the "please update" screen (blocking, below the API's minimum app version; from the release rules). A screen the records do not need is not drawn.
4. **FigJam flow.** A FigJam board (`figma-use-figjam`) in the same team as the design file, never left in drafts; the main journeys, including sign-up to first value and the tenant lifecycle.
5. **Accessibility annotations** on every screen: contrast pairs, focus order, touch targets, text scaling, screen-reader labels.
6. **Code Connect.** Try to map each component to its code name with `figma-code-connect` (React for this stack). If the account or tool refuses (plan or seat), write the Figma-name to code-name table in `DESIGN.md` and say plainly that Code Connect was not available and the refusal text.

## 4. Write `DESIGN.md`

`docs/design/DESIGN.md`: the Figma file name, node links for tokens, each component, each surface's frames, the FigJam flow and every required screen; the naming rule; the token files; theme and accessibility targets; the Code Connect status or the name table; open design questions marked as questions. Check: every screen in the records is linked; every component has a code name; `tokens.json` names match the Figma variables; every word is in `GLOSSARY.md`.

## 5. The gate

1. Run the checks of section 4, plus: every surface has its frames, every screen has all states, every required screen that applies exists.
2. Dispatch the `design-verifier` agent (subagent type `pavedline:design-verifier`), **blind**, once. Give it the file paths (`GLOSSARY.md`, `DOMAIN.md`, `openapi.yaml`, `decisions/`, `DESIGN.md`, `tokens.json`) and the Figma node ids to read. Never give it your summary or the designer's.
3. It ends `DESIGN VERDICT: APPROVE` or `DESIGN VERDICT: REJECT — <reason>`. Write the verdict and every finding to `docs/reviews/07-figma-review.md` (a finding may cite node ids; that file is the only other place they may appear); on REJECT the file lists the findings, so a fresh session resumes from it. A `REJECT` means rework and a narrow re-check, never arguing past it. Record each finding as fixed or accepted with a reason.
4. Only after `DESIGN VERDICT: APPROVE`, show the founder the screens and ask for approval: then the founder approves the visual. The design-verifier never approves a visual (taste, layout and brand feel are the founder's call), and the founder's approval never replaces the verdict.

## 6. Re-entry

Any step can be reopened. A changed answer is a new decision superseding the old (`supersedes NNNN`); stale outputs go to `STATE.md ▶ STALE` with the number.

## 7. Close step 7

After `DESIGN VERDICT: APPROVE` and the founder's approval, edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 8 — Plan
LAST: <timestamp> — step 7 done: DESIGN.md, tokens.json, Figma file; design-verifier APPROVE, see docs/reviews/07-figma-review.md
NEXT: step 8 — plan the first wave (ships in a later release)
```

Commit. Print the closing block (done, changed, next, waiting on you, clear-safe). Say plainly that step 8 ships in a later release, so Pavedline stops here for now. Ask: **go?**
