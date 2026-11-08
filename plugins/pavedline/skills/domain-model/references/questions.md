# Domain-model questions

Ask in this order, one area at a time. Each answer is one decision.

## Identifiers

Public and internal ids. Options: UUID v7 (time-ordered, default), UUID v4, bigint identity plus a public opaque id. Changes: index locality, what the API exposes, how ids are generated in code.

## Deletion and history

Hard delete, soft delete (a `deleted_at` column) or append-only history, per entity group. Default: soft delete for records a person might want back, append-only for audit and money, hard delete where retention (decision on retention and deletion) says data must really go. Changes: every query filter, unique constraints, export and deletion jobs.

## Money and quantities

Which entities carry amounts; currency handling. Default: integer minor units plus an ISO 4217 currency code, or `numeric`; **never float**. Changes: column types, API field types, rounding rules.

## Time

Which timestamps are instants (stored UTC, `timestamptz`) and which are local wall-clock values with a zone (date plus time plus IANA zone name). Take the rule from the time-and-scheduling decision; do not re-ask it. Changes: column pairs, slot generation, tests around DST.

## Audit and ownership

Which entities record who created or changed them; which actions go to the insert-only audit log (from the security decision). Changes: columns, triggers or application writes, the log table.

## Lifecycles and states

For each entity with states, confirm the states and legal transitions against the spec and the glossary. Changes: check constraints, API enums, the screens in step 7.

## Reference and global data

What is global (plans, countries, templates) versus tenant-owned; who may change global data. Changes: the allow-list the tenant-isolation check reads in `multi-tenancy`.

## Entry points before the tenant is known

Which requests must find their tenant before it is set on the transaction (public sign-up or invite pages, auth-provider and payment webhooks, email-delivery events). Default: a small global lookup table keyed by the public handle or provider id, written at tenant creation and deleted at tenant deletion, with no personal data. Changes: the global allow-list, the webhook handlers, deletion.

## People and logins

How a person in the domain (a staff member, an agent, a driver) relates to a login, and whether one login can belong to several tenants. Default: optional one-to-one link from the person to a membership; "own records" follows the link, never the role. Changes: ownership columns, permissions, auth mapping.

## Plan limits

Every limit a plan sets (seats, sites, records) as numbers, and whether archived records count. Default: archived do not count. Changes: a `plans` global table, quota errors in the API.
