# Run

How to build, test and run {{PROJECT_NAME}}. Keep each command copy-pasteable and verified; fill in as the stack is
chosen (step 4) and as slices land.

| Task | Command |
|---|---|
| Install dependencies | (fill in) |
| Run the tests | (fill in) |
| Start the local cluster | (fill in) |
| Run the app locally | (fill in) |

## Alerts

Three alerts run in the cluster (`infra/k8s/addons/alerts/`): a public endpoint is down, the last database backup failed
or is too old, a scheduled job failed or is late. They ship **off**. At step 12 (go to production) the founder chooses
where alerts go (the notify URL) and an external dead-man's switch (the heartbeat URL: it alerts when the all-green
pings stop), both stored in the Secret `alerts-targets`, never in Git; **the founder receives the alerts**. Record the
chosen service and where the Secret lives here. Endpoints, jobs and thresholds are values in
`infra/k8s/addons/alerts/values.yaml`.

## Secret rotation

What: every secret listed in `SERVICES.md` (provider keys, registry and CI tokens, the Renovate token).
Who: the owner named there. Where it is recorded: the date and the owner in `SERVICES.md` and a line in `STATE.md`;
never the value. Steps: create the new secret in the vault, let the cluster pick it up, verify the service, revoke the
old one, record it. A secret that may have leaked is rotated at once.

## Break-glass

What: emergency access that bypasses the normal path (GitOps, the vault, the hooks), for an outage the normal path
cannot fix. Who: only the founder grants and uses it. Where it is recorded: before use, a line in `WAITING.md`; after
use, an ADR (what, why, when, who) and the access is revoked. Never a standing credential, never in git or chat; the
procedure names where the sealed credential is kept, not its value.
