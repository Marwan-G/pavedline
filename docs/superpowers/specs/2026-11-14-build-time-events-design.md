# Build-time events: design

Date: 2026-11-14. Status: approved by the founder 2026-11-14 (option 2; "ok, push and merge").

## Intent

During the build, record which events the product must log, so that when the founder chooses observability tools at step 12 there is a reference, not a codebase to reread. The tools stay out of scope until step 12. Only the events, and the JSON log lines that carry them, are built now.

## Goals

- One register of events, `docs/observability/EVENTS.md`, written slice by slice as the code is built.
- Every API log line is one JSON object with fixed base fields, so any tool chosen later can read it.
- The register stays true: a script fails CI when the code emits an event the register does not list.
- The register is the input to the observability decision at step 12.

## Non-goals

- No tracing, metrics or log tool, collector or vendor. Each is a new service under ask-before-adding, decided at step 12.
- No OpenTelemetry now. `request_id` already ties one request together locally.
- No browser, site or mobile error tracking now: that is a tool choice at step 12. The register says so.
- No logging of request or response bodies.

## Anti-goals (failure even if it works)

- Secrets or personal data in a log line.
- A register that lists what someone meant to log, not what the code logs.
- A new runtime dependency for logging.

## The parts

### 1. The spec

In `docs/superpowers/specs/2026-11-07-pavedline-design.md`, the two "observability excluded" lines (out of scope, and the summary) become:

> Observability tools are out of scope except the three alerts. The events are defined during the build in `docs/observability/EVENTS.md`, and the tools are chosen at step 12.

### 2. The register template

`docs/observability/EVENTS.md` ships with the API stack (`stacks/nextjs-fastapi/files/`, the `api` surface in `pack.yaml`), so it is copied at step 6 together with the code its seed rows name. *(Ruling while building: the design first said step 0, but the seed rows point to the API's files, which exist only after step 6.)* It holds:

- **Base fields**, on every line: `ts` (UTC, ISO 8601), `level`, `event`, `message`, `logger`, `request_id` (on a request), `tenant_id` (once known).
- **Rules:**
  - Event names are `area.what_happened`, in lowercase snake case (`job.created`, `auth.token_rejected`).
  - The levels are `debug`, `info`, `warning` and `error`. `error` means someone must look.
  - An event carries ids, codes and counts, never secrets, tokens, passwords or personal data such as emails, names, addresses or phone numbers.
  - Fields whose names look secret are redacted by the logger anyway.
- **The table**, one row per event: Event · Level · Where (file) · Extra fields · What it means · Alert later? (yes/no, and why) · Slice.
- **Not covered yet:** web, site and mobile. These are a tool choice at step 12.
- **Seed rows** for what the API template already logs, renamed as events:
  - `request.unhandled_error` (error), from `app/errors.py`;
  - `db.data_error` (warning), from `app/errors.py`;
  - `webhook.accepted` (info), from `app/routes/webhooks.py`;
  - `health.readiness_failed` (warning), from `app/routes/health.py`.

### 3. JSON logging in the API template

In `stacks/nextjs-fastapi/files/services/api/`, using the standard library only:

- A new `app/logging.py` holds four things:
  - `configure_logging(level)`, which replaces `logging.basicConfig` in `main.py`. A JSON formatter writes one object per line to stdout.
  - Context variables for `request_id` and `tenant_id`. `RequestIdMiddleware` sets `request_id`. `tenant_id` is set where the `Principal` is resolved, and wherever a job runs `SET LOCAL app.tenant_id`.
  - `log_event(logger, level, event, **fields)`, the one way to emit an event.
  - Redaction. A field whose name contains `token`, `password`, `secret`, `authorization`, `cookie`, `api_key` or `key` becomes `"[redacted]"`. Exception tracebacks are kept, under `exc`.
- The four existing log calls become `log_event` calls with the seed names.
- New tests in `tests/test_logging.py`:
  - each line parses as JSON and has the base fields;
  - a caller's `X-Request-ID` appears;
  - `tenant_id` appears on an authenticated request;
  - a secret-named field is redacted;
  - an unhandled error emits `request.unhandled_error` with `request_id`;
  - no line contains the request body.

### 4. The register check

`scripts/events_check.py` lives in the stack files, standard library only. It finds every `log_event(..., "<name>"` in `services/api/app`, compares the names with the table in `docs/observability/EVENTS.md`, and handles them like this:

- It **fails** on an event the code emits that has no row.
- It **warns** on a row the code never emits.
- It **fails** on a duplicate name, or a name that breaks the naming rule.

It runs in `ci-api.yml` and in the builder's gate 4. *(My call: a script keeps the register true; the reviewer alone would not.)*

### 5. The steps

- **Step 6 (`system-architecture`):** the observability-seam area records "JSON logs on stdout with the base fields of `EVENTS.md`; tools at step 12". There is still one question, with no vendor.
- **Step 8 (`plan-graph`):** each slice gets an `Events:` line with the event names it adds, or `none`. Failure paths and key business moments are named there.
- **Step 9 (`quality-gates`, `builder`, `reviewer`):**
  - The builder emits the slice's events through `log_event` and adds their rows.
  - Gate 2 checks that every planned event is emitted and registered, and that every new error path logs one.
  - Gate 3 checks that no event field carries a secret or personal data.
  - Gate 4 runs `events_check.py`.
- **Step 10 (`deploy`):** a new line in the check language, `log-event <namespace> <deployment> <event>`. It reads the deployment's recent pod logs (read-only, on the forced local context) and passes when one JSON line has that `event`. A slice's PR names its key event as a post-deploy check. *(My call.)*
- **Step 11 (`lessons`):** a problem that was hard to find in the logs becomes a new event row. That is one of the homes a lesson can go to.
- **Step 12 (`go-to-production`, `launch.md`):** `EVENTS.md` is the input to the observability decision. Rows marked "alert later: yes" are the alert candidates, and the decision record says which became alerts.
- **`rules-index.md`:** event names and the base fields have one home, `EVENTS.md`.

## Acceptance

- The new API tests pass, and the existing stack tests still pass.
- `events_check.py` passes on the template and fails on a planted unregistered event.
- The deploy check language parses and rejects `log-event` lines as it does other lines. A test covers a good line and a bad one.
- The Pavedline skill tests cover the new step text.
- The sanitize scan is clean.
- The `starter` and `local-cluster` CI jobs are green.

## Delivery

One PR on Pavedline, from branch `feat/build-time-events`, through all five gates. It includes the adversarial review, because the change touches what lands in logs, which is sensitive-data handling. The PR is shown to the founder before merging.

## Calls I made (check these)

1. A script check of the register, on top of the reviewer.
2. Event names as `area.what_happened`.
3. The redaction list in part 3.
4. Web, site and mobile left to step 12.
5. Standard library only: no `structlog` and no `python-json-logger`.
6. The `log-event` post-deploy check.
