# Events

The events the product logs. This file is written during the build, slice by slice, and it is the input of the observability decision at step 12. No log, trace or metrics tool is chosen before then.

`scripts/events_check.py` keeps this file true: CI fails when the code emits an event that has no row here.

## The line

Every log line of the API is one JSON object on stdout (`app/events.py`). The base fields:

| Field | What it is |
|---|---|
| `ts` | UTC time, ISO 8601, milliseconds |
| `level` | `debug`, `info`, `warning` or `error` (`error` means someone must look) |
| `event` | the event name below; a log line that is not an event says `log.message` |
| `message` | a short human sentence |
| `logger` | the module that logged it |
| `request_id` | on a request: the `X-Request-ID` the caller sees in the response |
| `tenant_id` | once the tenant is known (after the token is verified, or inside a tenant transaction) |
| `exc` | the traceback, on an error with an exception |

## Rules

- Emit an event only through `log_event(logger, level, "area.what_happened", **fields)`; add its row here in the same pull request.
- Names are `area.what_happened`, lowercase snake case, for example `job.created` or `auth.token_rejected`.
- Fields carry ids, codes and counts. Never secrets, tokens, passwords, request or response bodies, or personal data (email, name, address, phone). A field whose name looks secret is redacted to `[redacted]` anyway.
- **Alert later** says whether the event should page someone once a tool exists, and why. It is a candidate for step 12, not an alert today.

## Events

| Event | Level | Where | Fields | What it means | Alert later | Slice |
|---|---|---|---|---|---|---|
| `request.unhandled_error` | error | `services/api/app/errors.py` | `exc` | a request failed with a bug; the caller got a 500 with the `request_id` | yes: any is a defect | stack |
| `db.data_error` | warning | `services/api/app/errors.py` | `error_type` | the database refused a value from the request; the caller got a 422 | no: client input | stack |
| `webhook.accepted` | info | `services/api/app/routes/webhooks.py` | `provider` | a signed webhook was verified and claimed once | no; a sudden stop may matter | stack |
| `health.readiness_failed` | warning | `services/api/app/routes/health.py` | `error_type` | the database did not answer the readiness probe | yes, if it lasts minutes | stack |

## Not covered yet

The web app, the website and the mobile app: their errors are collected by a tool chosen at step 12.
