# Sources (checked on the web 2026-11-08)

Re-check before relying on any of these; they are facts at a date, not rules.

| Fact | Value | URL | Date |
|---|---|---|---|
| Owner bypass and FORCE | "Table owners normally bypass row security as well, though a table owner can choose to be subject to row security with ALTER TABLE ... FORCE ROW LEVEL SECURITY." | https://www.postgresql.org/docs/current/ddl-rowsecurity.html | 2026-11-08 |
| BYPASSRLS | "Superusers and roles with the BYPASSRLS attribute always bypass the row security system when accessing a table." | https://www.postgresql.org/docs/current/ddl-rowsecurity.html | 2026-11-08 |
| Policies are owner-controlled | Enabling and disabling row security and adding policies is the table owner's privilege only | https://www.postgresql.org/docs/current/ddl-rowsecurity.html | 2026-11-08 |
| SET LOCAL | "The effects of SET LOCAL last only till the end of the current transaction, whether committed or not." | https://www.postgresql.org/docs/current/sql-set.html | 2026-11-08 |
| PgBouncer transaction mode | does not support SET/RESET, LISTEN, PREPARE/DEALLOCATE (as listed) or session-level advisory locks | https://www.pgbouncer.org/features.html | 2026-11-08 |
| Adapted skill | `saas-multi-tenant`, sickn33, MIT, Copyright (c) 2026 Antigravity User | https://github.com/sickn33/agentic-awesome-skills/tree/main/skills/saas-multi-tenant | 2026-11-08 |
| Supabase Postgres practices | `supabase-postgres-best-practices`, MIT, Copyright (c) 2026 Supabase; reference only | https://github.com/supabase/agent-skills | 2026-11-08 |

Not confirmed from these pages: the `set_config(name, value, true)` form's equivalence to `SET LOCAL` (the SET page only says set_config "provides equivalent functionality"; the third argument is documented in the functions chapter, section 9.28.1, not fetched).
