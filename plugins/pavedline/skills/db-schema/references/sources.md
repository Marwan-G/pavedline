# Sources (checked on the web 2026-11-08)

Re-check before relying on any of these; they are facts at a date, not rules.

| Fact | Value | URL | Date |
|---|---|---|---|
| PostgreSQL current docs | PostgreSQL 18.6 documentation is the "current" release; a release candidate of 19 is announced | https://www.postgresql.org/docs/current/ddl-rowsecurity.html | 2026-11-08 |
| bigint range | -9223372036854775808 to +9223372036854775807 | https://www.postgresql.org/docs/current/datatype-numeric.html | 2026-11-08 |
| Floating point | `real` and `double precision` are inexact; "for monetary amounts" use `numeric` | https://www.postgresql.org/docs/current/datatype-numeric.html | 2026-11-08 |
| Postgres best practices (reference) | Supabase `supabase-postgres-best-practices` skill, MIT, used as a reference; nothing copied | https://github.com/supabase/agent-skills | 2026-11-08 |

Not confirmed from these pages: the result type of `sum(bigint)` (known only from general knowledge; the rule "read sums as text" does not depend on it), and the expand/contract pattern, which is a widely used practice and not a vendor fact.
