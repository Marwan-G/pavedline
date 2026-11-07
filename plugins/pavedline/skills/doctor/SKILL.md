---
name: doctor
description: Checks that every tool and plugin Pavedline needs is installed and prints the exact command to fix anything missing. Use at the start of step 0 (before /pavedline:start does anything else), and whenever a command is not found or a dependency seems missing.
allowed-tools: Bash(python3 *)
---

# doctor

Run the checker:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

It prints a table (name, ok or missing, required or optional, fix) and a last line
`doctor: all required checks passed` or `doctor: N required check(s) failed`.

Rules:

- Relay each fix exactly as printed. Do not reword, merge or invent commands.
- Never run an install command without the user's explicit go. Installing software is the user's choice.
- After the user installs something, run the checker again and report the new result.
- Optional items that are missing do not block anything; mention them once and move on.
