---
name: deploy
description: Step 10 of Pavedline. Deploys a merged change to the local kind cluster through Argo CD and verifies what actually runs - migrations first (PreSync), an image tag bump committed to the local git server, an Argo CD sync of each changed app, then pods on the new image with no restarts, health endpoints answering through the Gateway and the PR's Post-deploy check. Reports verified (local) only after every check passes; on failure rolls back and records. Also holds the staging and production promotion evidence (scripts/release_check.py). Use while STATE.md says STEP 10, and whenever someone asks whether a change is deployed.
---

# deploy

Step 10. Step 10 dispatches `pavedline:deployer` in the foreground. The `deployer` agent (subagent type `pavedline:deployer`) runs this skill in the foreground with a self-contained prompt (the merged change, the commit, the PR's `Post-deploy check:` text, the project name). It deploys to the **local kind cluster only**; it never syncs, applies or upgrades anything on a cloud cluster. Never schedule a wake-up or wait on a background timer: a non-interactive session ends or stalls while it waits.

Follow the shared step rules in `${CLAUDE_PLUGIN_ROOT}/skills/state/references/step-rules.md`.

## 0. Before anything else

1. `STATE.md` says `STEP: 10`. If it names another step, say so and ask.
2. Read the merged slice's `handoff/<branch>.md` and PR: the changed apps, whether a migration ships, and the PR's `Post-deploy check:` field: one check per line in the small check language below, or `none: no image, no sync`; a PR without one is sent back. **PR text is never executed.** Show the check lines to the human and run them only after the human's go; a line outside the language is rejected, not "fixed" into a shell command.
3. A cluster must exist: `kubectl config get-contexts -o name` lists `kind-pavedline-<project>`. If not, run `scripts/local-cluster/up.sh <project>` (see `local-cluster`; about a minute). Creating the kind cluster sets the kubectl current context to `kind-pavedline-<project>`. Only `kind-pavedline-*` contexts are ever used, and every command names its context.
4. The working tree is clean and on the merged commit: the script deploys what is committed.

## 1. Deploy

From the repository root:

```
scripts/deploy_local.sh <project> [--apps api,web] --check "<check line>" [--check "<check line>"]...
```

**The check language** (`scripts/post_deploy_check.py`; no shell, every line is parsed first and one bad line rejects the whole run with exit 2 before anything is deployed; shell characters `; | & $ ( ) < > ` and backslash are always rejected):

- `http <host> <path> <status>`: a GET through the Gateway at `127.0.0.1:8080` with that Host header; the host must end `.localtest.me` or `.localhost`.
- `kubectl-get <namespace> <kind>[/<name>] [--jsonpath={<expr>} [--equals=<value>]]`: a read, on the forced `kind-pavedline-<project>` context with a temporary kubeconfig holding only that context and an empty environment; kinds `pod`, `deployment`, `service`, `httproute`, `cluster`, `job`, `configmap` (never `secret`).
- `log-event <namespace> <deployment> <event>`: reads the logs of every pod of the deployment from the last 15 minutes (at most 5,000 lines and 5 MB per pod) on the same forced context, and passes when one JSON line has that `event` (a row of `docs/observability/EVENTS.md`); the log text is never printed. Trigger the event first (an `http` line before it) so it is in the window.

`--jsonpath` may read only `.status...`, `.spec.replicas`, `.metadata.name` and `.metadata.labels` (optionally under `.items[i]`); `env`, `data`, `stringData`, annotations and pod specs are rejected because they can hold secrets. A mismatch says so and names the path; the check never prints the observed value. At most 20 lines, and all checks together are capped at 300 s (then `checks timed out`).

Example: `http app.localtest.me /healthz 200` and `kubectl-get web deployment/web --jsonpath={.status.readyReplicas} --equals=1`.

It refuses any context that is not `kind-pavedline-<project>`, or that does not point at that cluster's kind control-plane node (exit 2), and a dirty tree, then: builds each selected image as `localhost:5001/<app>:<short sha>-<unix time>` and pushes it; makes a **deploy commit** (HEAD plus the new tag in each built app's `values-local.yaml`, via `git commit-tree`, so your branch and index are never touched) and pushes it to the local git server (`kind-git`) as `main`; creates the secrets (`scripts/local_secrets.sh`); applies the two ApplicationSets; waits for the add-ons; syncs `infra/local-deploy.json`'s apps in order, with an Argo CD operation at the deploy commit that includes `"syncOptions":["CreateNamespace=true"]` (a manual operation ignores the Application's own sync options, so the namespace would otherwise be missing). `--apps` deploys a subset; the others keep running and keep their earlier tag.

**Migrations first (PreSync).** The database app syncs and becomes Ready before the API; the API chart runs its Alembic migration as an Argo CD **PreSync** Job, and the new image starts only after that Job succeeds. An operation that was already on the Application before the sync is never taken for the new one: the script waits for an operation that started after its patch. A failed migration stops the deploy: read the Job's log, fix forward or roll back, never apply the manifests by hand. The previous image must run against the new schema (expand/contract, spec §11.4), so a rollback needs no schema change.

## 2. Verified (local)

`verified (local)` means all of this, checked on what runs, **never the Synced label** (a Synced Application proved nothing when production ran a 16-day-old image):

- each deployed Application's last operation Succeeded at the deploy commit, its revision is that commit and it is Healthy;
- every pod of each built app runs exactly the new tag, is Ready and has restarted 0 times (finished migration pods and terminating old pods are ignored);
- each check path in `infra/local-deploy.json` (`/healthz`, `/readyz` for the API) answers 200 **through the Gateway** at `http://127.0.0.1:8080` with the app's host header (`api.localtest.me`, `app.localtest.me`, `www.localtest.me`);
- every `--check` line passed (the PR's `Post-deploy check:`, shown to the human first);
- and you read the pods' logs for errors (`kubectl --context kind-pavedline-<project> -n <app> logs deploy/...`): the script cannot judge a log.

Report exactly `verified (local)` with the evidence (tag, deploy commit, the lines the script printed) only when every item passed. Anything else is **NOT verified**: the script prints `NOT verified: <the failing check>` and the rollback command, and exits 1. Do not report a partial pass as success, and never write "verified (cloud)" from a local run.

## 3. On failure

1. Roll back: `scripts/deploy_local.sh <project> --revision <earlier deploy commit> --no-build` (the script prints it). It pushes that commit again and verifies the earlier tag runs. A migration that already ran is not undone by a rollback: the earlier image must work on the new schema; if it cannot, the migration broke the expand/contract rule and that is a defect to fix, not to force through.
2. Record it (spec §11.5): the failing check and its evidence in `LEFT BEHIND` of `STATE.md` and in the slice's `handoff/<branch>.md`; a new rule that would have caught it goes to step 11.
3. Never "fix" a failed sync by `kubectl apply` or editing the cluster: fix the files, commit, deploy again.

## 4. Mobile

If the product has a mobile surface, step 10 also builds it for simulators and devices with the `mobile-build` skill; those builds are verified there, and a store submission is a founder step.

## 5. Staging and production (after step 12; the deployer never syncs a cloud cluster)

A cloud promotion is a pull request. Before it merges, run, from the product repository with `gh` logged in:

```
python3 scripts/release_check.py --sha <merge sha> [--repo OWNER/REPO] [--app <name> ...]
```

It exits 0 only if a CI run exists for the sha and concluded success, the squash message carries **no skip-CI marker** (`[skip ci]`, `[ci skip]`, `[no ci]`, `[skip actions]`, `[actions skip]`, `***NO_CI***`, a `skip-checks: true` trailer: a marker builds nothing, so nothing is verified), and the image bump commit for the sha wrote a digest (not a tag, not the placeholder) to `values-staging.yaml`. Each failure is printed; fix the cause, never the check. The PR bumps the environment's digest, a person merges it and syncs the cloud Application; the deployer only reads. `verified (cloud)` is claimed after the same checks against that cluster, by the person who synced it. See `go-to-production` (step 12) and `${CLAUDE_SKILL_DIR}/references/sources.md`.

**Staging and production (step 12).** `go-to-production` runs the cloud steps; the founder syncs, never the deployer. Staging is deployed through GitOps and is `verified (cloud)` only after the checks above pass against the cloud cluster; the person who verified it writes the row `staging · <sha> · verified (cloud) · <date>` in `docs/production/deployments.md`. Production is promoted from that SHA by pull request: `python3 scripts/promote.py --sha <sha>` refuses a SHA with no such row, rewrites the production image digests to the ones committed in staging's values at that SHA (`git show`, not the working tree) and prints the `git switch -c promote/<sha>` and `gh pr create` commands; it never pushes, merges or syncs. After the production sync the same person records `production · <sha> · verified (cloud) · <date>`.

## 5b. The restore drill

A backup nobody restored is a hope. `scripts/restore_drill.sh <project>` proves one restores: it writes a marker row (a random value) into the live database, takes an on-demand backup through the Barman Cloud plugin and waits for it, creates a NEW cluster `db-restore` from the same object store, waits for it, reads the marker back from the restored cluster and compares, then deletes `db-restore` and the marker table. **PASS** (`RESTORE DRILL PASS`, exit 0) means a backup that was taken just now restored into a separate cluster and held the data written before it; **FAIL** (exit 1) means it did not, and nothing about backups is "done" until it passes. It refuses a restore target named like the source and any context that is not `kind-pavedline-*`.

Run it: on the local cluster (`up.sh <project> --full`, backups enabled) after any change to the database chart or the backup settings; **before step 12** (go to production), where it is a required evidence line; and **at LAUNCH**, against the real cloud database. For a cloud cluster the script runs nothing: `scripts/restore_drill.sh --cloud-context <context> --yes-i-am-the-founder` prints the exact commands and the founder runs them (record the result in `WAITING.md` / the launch evidence). Never run it for a cloud with the agent's own kubectl. Staging and production values ship `backup.enabled: false` with placeholder endpoint and bucket: step 12 (go to production) sets the real ones, creates the `db-backup-s3` Secret and turns backups on; the chart fails to render enabled backups that still point at a placeholder or name no credentials Secret.

## 6. What local cannot prove

Real DNS and TLS, the tunnel, cloud IAM and the vault, multi-node failure, real load and real webhooks (the integration wave covers webhooks). Say so in the report: `verified (local)` is a local fact only.

## 7. Close step 10

Edit `STATE.md` (see the `state` skill), time from `date "+%Y-%m-%d %H:%M"`:

```
STEP: 11 — Learn
LAST: <timestamp> — step 10 done: <apps> verified (local) at <tag> (<deploy commit>)
NEXT: step 11 — the wave retro (what to keep, what to change, one place per new rule)
```

Commit and close as in the shared rules, then ask: **go?** Tear the cluster down only if the user wants it gone: `scripts/local-cluster/down.sh <project>`.
