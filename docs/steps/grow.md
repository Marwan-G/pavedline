# Grow (standing loop after launch)

Starts when `STATE.md` says `STEP: Grow — after launch` and you say go. Skills: `seo-foundation` (the baseline) and `content-ops` (the loop). Agent: `growth`. Uses Anthropic's `marketing` plugin (`seo-audit`, `content-creation`, `draft-content`, `performance-report`), optional: install it when the loop starts (`/pavedline:doctor` prints the command).

## What it is for

Keeping the site found and current after launch. The agent drafts; you publish.

## Cadence

Weekly: move the content calendar (`docs/growth/calendar.md`). Monthly: a Search Console review plus `seo-audit`, written to `docs/growth/YYYY-MM.md`. Quarterly: refresh, merge or remove old posts, check links and redirects. After each run `STATE.md` carries `GROW DUE: <date> — <what>`; a past date means it is due.

## The publish loop

Brief, draft, your edit and fact-check, SEO checklist, pull request, deploy through GitOps, request indexing. In that order.

## Your approval comes first

You approve each piece as its own question. The agent never writes `approved` or `published` except as a verbatim copy of your reply, and no pull request is opened before it; the pull request text quotes it. Search Console and Bing Webmaster Tools are your accounts and your steps, listed in `WAITING.md`.

## What the agent never does

Publish, push, merge, deploy or create an account. It has no shell; the owner session opens the pull request and writes `GROW DUE`. Staging stays `noindex`; only production is indexable.

## Output files

`docs/growth/calendar.md`, `docs/growth/briefs/<slug>.md`, `docs/growth/YYYY-MM.md`, the pull requests, and `STATE.md ▶ GROW DUE`.
