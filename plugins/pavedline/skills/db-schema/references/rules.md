# Schema rules and question areas

## Naming and types

snake_case, plural table names, singular column names; names are the glossary terms. Primary key: the type chosen in `domain-model` (default UUID v7). `timestamptz` for instants. `text` plus a check constraint, or a Postgres enum, for states (default: `text` with a check, because enum values are hard to remove). Money: integer minor units plus currency code, or `numeric`; **never float**.

## Constraints and integrity

Foreign keys everywhere a relation exists, with explicit `ON DELETE`. Not-null by default; unique constraints for natural keys (scoped by `tenant_id` on tenant tables); check constraints for states, ranges and the invariants listed in `DOMAIN.md`. Rules the database can enforce are enforced in the database, not only in code.

## Indexes

Index every foreign key and every column used in a `WHERE`, `JOIN` or `ORDER BY` of a query in the spec. On tenant tables `tenant_id` leads composite indexes. Partial indexes for soft-deleted tables. Say which query each index serves.

## Concurrency columns

From the concurrency decision: a `version` integer for optimistic locking; exclusion constraints (`EXCLUDE USING gist`) or unique constraints for overlapping-range contention; row locks inside one transaction. Session advisory locks are forbidden (PgBouncer transaction mode).

## Retention and deletion

From the retention decision: which tables carry `deleted_at` or an expiry, which job removes data, and what survives in backups.

## Migrations

Ordered, numbered, each with a `down`. expand/contract for anything in use. Large sums are read as text in code (`SUM(x)::text`, or `numeric` end to end) so they never overflow `bigint`. Tool choice (for example Alembic for a Python backend) is asked once and recorded.
