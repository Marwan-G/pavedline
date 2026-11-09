# pavedline-cockpit

An optional, separate plugin for [Pavedline](../../README.md). Nothing in `pavedline` depends on it.

It is a Claude Code mod: a pane beside the chat that shows, for the project you are in,

- `STEP`, `WAVE` and `NEXT` from `STATE.md`,
- the open slice (the first `SLICES IN FLIGHT` entry) and the `Gates:` line of its `handoff/<branch>.md`,
- the open items of `WAITING.md` (the count and the first three).

The pane redraws when a turn ends. It is read-only: it reads those files and nothing else, never writes, never runs a shell, never uses the network. Outside a Pavedline project it shows `no Pavedline project here`.

## Install

Needs Claude Code 2.1.287 or later in the terminal (mods are not drawn in `claude -p`).

```
claude plugin install pavedline-cockpit@pavedline
```

## Status as text

- `/pavedline-status` (the mod's command) and `/pavedline-cockpit:status` (the skill) print the same summary. Use the skill under `claude -p`, where the pane draws nothing.

## Develop

```
node --test hooks/        # none; parsing is tested from tests/test_cockpit.py
claude plugin test plugins/pavedline-cockpit
claude plugin validate plugins/pavedline-cockpit --strict
```

Sources: [SOURCES.md](SOURCES.md).
