# Launch checklist

Blocking: "go live" is refused until `launch_check.py` exits 0. Tick an item only with evidence. An item may carry
`exception: decisions/NNNN-<slug>.md` at the end of the item (an ADR with `Status: accepted`) instead of a tick. Add product-specific items below; they
block too.

- [ ] Processor agreements signed
- [ ] Payment and SMS providers approved for live use
- [ ] Store approvals
- [ ] Legal pages live
- [ ] Compliance confirmed once more (step 0 intake)
- [ ] A restore tested in the cloud (`scripts/restore_drill.sh` against cloud staging)
- [ ] The load targets of the system design met
- [ ] An accessibility audit passed (automated plus one manual screen-reader pass)
- [ ] The three alerts tested: uptime of the public endpoints, a backup failed, a scheduled job failed or is late
- [ ] The observability decision recorded from `docs/observability/EVENTS.md` (install the observability extension, or accept the risk in an ADR); the "Alert later: yes" rows are the alert candidates
