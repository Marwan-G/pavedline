# LAUNCH.md items (step 12)

The blocking checklist is `docs/production/LAUNCH.md`. `launch_check.py` reads every `- [ ]` or `- [x]` line.

- Processor agreements signed.
- Payment and SMS providers approved for live use.
- Store approvals.
- Legal pages live.
- Compliance confirmed once more (step 0 intake).
- A restore tested in the cloud (`scripts/restore_drill.sh` against the cloud staging database).
- The load targets of the system design met.
- An accessibility audit passed (automated plus one manual screen-reader pass).
- The three alerts tested: uptime of the public endpoints, a backup failed, a scheduled job failed or is late.
- The observability decision recorded from `docs/observability/EVENTS.md` (install the observability extension, or accept the risk in an ADR); the rows marked "Alert later: yes" are the alert candidates, and the decision says which became alerts.

An item may end with `exception: decisions/NNNN-<slug>.md` instead of a tick; the ADR must exist, be non-empty and have `Status: accepted`. A line that looks like a checkbox but is not `- [ ] text` / `- [x] text` is an error, and so is a checklist item inside a code block or an HTML comment, or a code fence or comment that never closes: nothing can be hidden. A product may add items; they block too. "Go live" is refused until `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/launch_check.py` exits 0.
