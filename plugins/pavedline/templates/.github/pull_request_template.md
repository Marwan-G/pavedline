## What and why

<!-- One or two plain sentences. -->

## Gates

<!-- Replace every ? with ✓ and the numbers with what really happened (adversarial: ✓ or n/a). Until then the gates-line check fails on purpose. -->
Gates: TDD ? · review ? (n found, m fixed) · security ? · adversarial ✓|n/a · verification ?

Post-deploy check: <!-- one check per line, read-only, in this language (never a shell command; the deployer shows these lines to the human and runs them only after the human's go): `http <host> <path> <status>` (host ends .localtest.me) or `kubectl-get <namespace> <kind>[/<name>] [--jsonpath={.status.phase} --equals=Running]` or `log-event <namespace> <deployment> <event>` (an event of docs/observability/EVENTS.md); or "none: no image, no sync" -->

<!-- Diagram drift: if code changed but ARCHITECTURE.dot needs no update, add a line made of the words
"diagram unchanged", a colon and the reason. Do not write that phrase unless you mean it: it switches the check off. -->
