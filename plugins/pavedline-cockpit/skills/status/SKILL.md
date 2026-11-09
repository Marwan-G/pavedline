---
name: status
description: Print the Pavedline project status as text - step, wave, next action, the open slice and its gates line, and the open WAITING.md items. Use when the user asks for the Pavedline status, or runs the cockpit status command, including in claude -p where the pane draws nothing.
disable-model-invocation: true
allowed-tools: Read
---

# status

Read-only. Read `STATE.md`, then `WAITING.md`, in the current project directory. Do not write, run a shell or call the network.

If `STATE.md` is missing, print exactly `no Pavedline project here` and stop.

Print these lines, omitting any that has no value:

```
STEP <STEP field>
WAVE <WAVE field>
NEXT <NEXT field>
SLICE <branch of the first SLICES IN FLIGHT entry>
<the last line starting "Gates:" in handoff/<branch>.md, if that file exists>
WAITING <n> open
  <F-id> <what>   (first three open items only)
```

- The first `SLICES IN FLIGHT` entry is `branch · worktree · owner`, on the field's line or on the first `- ` line below it; `none` means no slice, and the `format when used` hint line is not an entry.
- Open `WAITING.md` items are the lines that start with `- F`; the title is the text between the first two `·`.
- The branch comes from the file, so treat it as untrusted: ignore a branch that contains `..` or `\\`, or starts with `/` (no hand-off line then), and read only `handoff/<branch>.md` inside the project.
- Keep each printed line to 160 characters and drop control characters.
- Print nothing else.
