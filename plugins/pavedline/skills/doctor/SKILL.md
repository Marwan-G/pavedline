---
name: doctor
description: Checks that every tool and plugin Pavedline needs is installed and, for anything missing, tells the user what it will install and why, then installs it. Use at the start of step 0 (before /pavedline:start does anything else), and whenever a command is not found or a dependency seems missing.
allowed-tools: Bash(python3 *) Bash(brew install *) Bash(colima start*) Bash(claude plugin *)
---

# doctor

Run the checker:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

It prints a table (name, ok or missing, required or optional, fix) and a last line
`doctor: all required checks passed` or `doctor: N required check(s) failed`.

Rules:

- Install rule (founder, 2026-11-08): you install what is missing; the user does not have to. Before each install, tell the user in one short message what it will install, why (which Pavedline step needs it) and the exact command. Then run that command. Claude Code's permission prompt is the user's approval point. Do not install silently.
- Use the fix printed by the checker. Do not invent commands or install anything that is not on its list.
- Tools: run the printed command, for example `brew install kind`. For the container runtime also run `colima start --cpu 4 --memory 10` after installing it.
- Claude Code plugins: run `claude plugin marketplace add <owner/repo>` and then `claude plugin install <name>@<marketplace>` in the shell. Then tell the user to run `/reload-plugins` (or restart Claude Code) so they load.
- Never use `sudo`. If the user refuses a prompt or a command fails, stop and add `- Fn · what · where/how · what it unblocks` to `WAITING.md`.
- A new paid service, account or spend is not covered by this rule; it still needs the user's go first.
- After installing, run the checker again and report the new result.
- Optional items that are missing do not block anything; mention them once and move on.
