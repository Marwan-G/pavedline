#!/usr/bin/env python3
"""Fail when the migrated database breaks the tenant-isolation rules.

Reads the live catalog (never the migration files). Scans every schema the runtime role has USAGE on.

Tables (not on the allow-list): `tenant_id NOT NULL`; ENABLE and FORCE ROW LEVEL SECURITY; and the
policies must be exactly the canonical form on both USING and WITH CHECK:

    (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::<type>)

Why exact: permissive policies are OR'd, so one extra open policy, or `true OR ...`, defeats the rest,
and a catalog expression cannot be proven safe by pattern. A restrictive policy may be anything (it can
only narrow). A custom permissive policy needs an allow-list line `policy:<table>.<policy>  # reason`.
Each policy must apply to PUBLIC or only to the runtime role, and at least one FOR ALL policy must exist.

Views: every view needs `security_invoker=true` (otherwise it runs as its owner and bypasses RLS);
a materialized view cannot, so it fails unless listed `view:<schema>.<name>  # reason`.

Roles: the runtime role must not own any relation (table, view, sequence, index...), function, or
schema; must not be a member of the owner role; must not have BYPASSRLS or be a superuser.

Allow-list file, one entry per line, a reason after `#` is required:
  `<table>` (a global table; `<schema>.<table>` outside public)
  `policy:<table>.<policy>` · `view:<schema>.<name>`

Run (from the repository root):
  uv run --project services/api python scripts/rls_check.py \\
      --database-url "$DATABASE_OWNER_URL" --global-tables services/api/db/global_tables.txt

Exit codes: 0 ok, 1 problems found (one line each), 2 usage or connection error.
"""

import argparse
import pathlib
import re
import sys
from typing import cast

import psycopg

SETTING = "current_setting('app.tenant_id'"
DEFAULT_GLOBAL_TABLES = pathlib.Path(__file__).resolve().parent.parent / "services/api/db/global_tables.txt"
CANONICAL = re.compile(
    r"^\(tenant_id = (?:\(NULLIF\(current_setting\('app\.tenant_id'::text, true\), ''::text\)\)::\w+"
    r"|NULLIF\(current_setting\('app\.tenant_id'::text, true\), ''::text\))\)$"
)
SKIP_SCHEMAS = ("pg_catalog", "information_schema")
Conn = psycopg.Connection[tuple[object, ...]]


def read_allow_list(path: pathlib.Path) -> tuple[set[str], list[str]]:
    names: set[str] = set()
    problems: list[str] = []
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, _, reason = line.partition("#")
        name = name.strip()
        if not reason.strip():
            problems.append(f"{path}:{number}: allow-list entry {name!r} has no reason after '#'")
        names.add(name)
    return names, problems


def qualified(schema: str, name: str) -> str:
    return name if schema == "public" else f"{schema}.{name}"


def check_policies(conn: Conn, oid: object, label: str, runtime_oid: object, allowed: set[str]) -> list[str]:
    problems: list[str] = []
    rows = conn.execute(
        "SELECT polname, polcmd, polpermissive, polroles, pg_get_expr(polqual, polrelid), "
        "pg_get_expr(polwithcheck, polrelid) FROM pg_policy WHERE polrelid = %s ORDER BY polname",
        (oid,),
    ).fetchall()
    has_all = False
    for name, cmd, permissive, roles, using, check in rows:
        entry = f"policy:{label}.{name}"
        if roles not in ([0], [runtime_oid]):
            problems.append(f"{label}: policy {name} applies to roles other than PUBLIC or the runtime role")
        if not permissive or entry in allowed:
            continue
        using_ok = cmd == "a" or (using is not None and CANONICAL.match(str(using)) is not None)
        check_ok = cmd in ("r", "d") or (check is not None and CANONICAL.match(str(check)) is not None)
        if not (using_ok and check_ok):
            problems.append(
                f"{label}: permissive policy {name} is not the canonical tenant policy "
                f"(USING and WITH CHECK must be tenant_id = NULLIF({SETTING}, true), '')::<type>); "
                f"fix it, or list {entry} in the allow-list with a reason"
            )
        elif cmd == "*":
            has_all = True
    if not has_all and not any(f"policy:{label}.{r[0]}" in allowed for r in rows):
        problems.append(f"{label}: no canonical FOR ALL tenant policy found")
    return problems


def check(
    conn: Conn, schemas: list[str] | None, runtime_role: str, owner_role: str, allowed: set[str]
) -> list[str]:
    problems: list[str] = []
    role = conn.execute(
        "SELECT oid, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = %s", (runtime_role,)
    ).fetchone()
    if role is None:
        return [f"the runtime role {runtime_role} does not exist"]
    runtime_oid, bypass, superuser = role
    if bypass:
        problems.append(f"the runtime role {runtime_role} has BYPASSRLS")
    if superuser:
        problems.append(f"the runtime role {runtime_role} is a superuser")
    member = conn.execute("SELECT pg_has_role(%s, %s, 'MEMBER')", (runtime_role, owner_role)).fetchone()
    if member and member[0]:
        problems.append(f"the runtime role {runtime_role} is a member of {owner_role}")

    usable = [
        str(r[0])
        for r in conn.execute(
            "SELECT nspname FROM pg_namespace WHERE has_schema_privilege(%s, oid, 'USAGE') "
            "AND nspname <> ALL(%s) AND nspname NOT LIKE 'pg_toast%%' AND nspname NOT LIKE 'pg_temp%%' "
            "ORDER BY nspname",
            (runtime_role, list(SKIP_SCHEMAS)),
        ).fetchall()
    ]
    scan = usable if schemas is None else schemas

    for nsp in conn.execute(
        "SELECT nspname FROM pg_namespace WHERE nspowner = %s", (runtime_oid,)
    ).fetchall():
        problems.append(f"the runtime role {runtime_role} owns schema {nsp[0]}")
    for fn in conn.execute(
        "SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE p.proowner = %s",
        (runtime_oid,),
    ).fetchall():
        problems.append(f"the runtime role {runtime_role} owns function {fn[0]}.{fn[1]}")
    for rel in conn.execute(
        "SELECT n.nspname, c.relname, c.relkind FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relowner = %s",
        (runtime_oid,),
    ).fetchall():
        problems.append(
            f"the runtime role {runtime_role} owns {rel[0]}.{rel[1]} (relkind {rel[2]}); the owner role must"
        )

    seen: set[str] = set()
    for schema in scan:
        tables = conn.execute(
            "SELECT c.oid, c.relname, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r', 'p') ORDER BY c.relname",
            (schema,),
        ).fetchall()
        for oid, relname, enabled, forced in tables:
            label = qualified(schema, str(relname))
            seen.add(label)
            if label in allowed:
                continue
            col = conn.execute(
                "SELECT attnotnull FROM pg_attribute WHERE attrelid = %s AND attname = 'tenant_id' "
                "AND NOT attisdropped",
                (oid,),
            ).fetchone()
            if col is None:
                problems.append(
                    f"{label}: no tenant_id column (add one, or list the table as global with a reason)"
                )
            elif not col[0]:
                problems.append(f"{label}: tenant_id is nullable; it must be NOT NULL")
            if not enabled:
                problems.append(f"{label}: ROW LEVEL SECURITY is not ENABLEd")
            if not forced:
                problems.append(
                    f"{label}: ROW LEVEL SECURITY is not FORCEd (ALTER TABLE ... FORCE ROW LEVEL SECURITY)"
                )
            problems += check_policies(conn, oid, label, runtime_oid, allowed)
        views = conn.execute(
            "SELECT c.relname, c.relkind, c.reloptions FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('v', 'm') ORDER BY c.relname",
            (schema,),
        ).fetchall()
        for relname, kind, options in views:
            entry = f"view:{schema}.{relname}"
            if entry in allowed:
                continue
            if kind == "m":
                problems.append(
                    f"{schema}.{relname}: a materialized view cannot be security_invoker and "
                    f"bypasses RLS; remove it or list {entry} in the allow-list with a reason"
                )
            elif "security_invoker=true" not in [str(o) for o in cast("list[object]", options or [])]:
                problems.append(
                    f"{schema}.{relname}: view without security_invoker=true runs as its owner and "
                    "bypasses RLS (CREATE VIEW ... WITH (security_invoker = true))"
                )
    if schemas is None:
        for entry in sorted(allowed):
            if not entry.startswith(("policy:", "view:")) and entry not in seen:
                problems.append(f"the allow-list names {entry!r}, which is not a table in a scanned schema")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if the migrated database breaks the tenant-isolation rules.",
    )
    parser.add_argument("--database-url", required=True, help="PostgreSQL URL (the owner role is enough)")
    parser.add_argument(
        "--global-tables",
        type=pathlib.Path,
        default=DEFAULT_GLOBAL_TABLES,
        help="allow-list file (global tables, custom policies, views); a reason is required per line "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--schema",
        action="append",
        help="limit the scan to this schema (repeatable). Default: every schema the runtime role can use",
    )
    parser.add_argument("--runtime-role", default="app_runtime", help="runtime role (default: %(default)s)")
    parser.add_argument("--owner-role", default="app_owner", help="owner role (default: %(default)s)")
    args = parser.parse_args(argv)

    try:
        allowed, problems = read_allow_list(args.global_tables)
    except OSError as exc:
        print(f"cannot read {args.global_tables}: {exc}", file=sys.stderr)
        return 2
    try:
        with psycopg.connect(args.database_url, connect_timeout=10) as conn:
            problems += check(conn, args.schema, args.runtime_role, args.owner_role, allowed)
    except psycopg.Error as exc:
        print(f"cannot check the database: {type(exc).__name__}", file=sys.stderr)
        return 2
    for problem in problems:
        print(problem)
    if problems:
        print(f"rls_check: {len(problems)} problem(s)")
        return 1
    print("rls_check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
