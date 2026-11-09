---
max_turns: 20
timeout_seconds: 600
tags: [start]
expected_outcome: "In the eval sandbox the machine check fails (no container runtime), so step 0 stops before asking or copying anything and says what is missing."
allowed_tools: [Bash, Read, Glob, Grep, Skill]
---
/pavedline:start

I am building a small invoicing tool for acme: it serves small shops, the problem is chasing late invoices, and it must list overdue items first.
