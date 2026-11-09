"""The three roles of the tenancy rules, proven against a real database."""

import psycopg
import pytest

from tests.conftest import Database


def connect(url: str) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(url, autocommit=True)


def test_runtime_role_attributes(database: Database) -> None:
    with connect(database.admin_dsn) as conn:
        rows = conn.execute(
            "SELECT rolname, rolsuper, rolbypassrls, rolinherit, rolcanlogin, rolcreaterole, rolcreatedb "
            "FROM pg_roles WHERE rolname IN ('app_owner','app_runtime','app_admin')"
        ).fetchall()
    by_name = {r[0]: r for r in rows}
    assert set(by_name) == {"app_owner", "app_runtime", "app_admin"}
    for name in ("app_runtime", "app_admin"):
        _, sup, bypass, inherit, login, createrole, createdb = by_name[name]
        assert not (sup or bypass or inherit or createrole or createdb), name
        assert login
    assert by_name["app_owner"][2] is True  # the migration owner is the only BYPASSRLS role
    assert by_name["app_owner"][1] is False


def test_runtime_role_cannot_become_the_owner(database: Database) -> None:
    with connect(database.runtime_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SET ROLE app_owner")


def test_runtime_role_owns_nothing_and_cannot_create(database: Database) -> None:
    with connect(database.admin_dsn) as conn:
        owned = conn.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
            "WHERE r.rolname = 'app_runtime'"
        ).fetchone()
    assert owned == (0,)
    with connect(database.runtime_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("CREATE TABLE leaked (id int)")


def test_runtime_role_cannot_alter_policies_or_tables(database: Database) -> None:
    with connect(database.runtime_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("ALTER TABLE idempotency_keys DISABLE ROW LEVEL SECURITY")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DROP POLICY tenant_isolation ON idempotency_keys")


def test_no_tenant_setting_fails_closed(database: Database) -> None:
    with connect(database.runtime_url) as conn:
        assert conn.execute("SELECT count(*) FROM idempotency_keys").fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # WITH CHECK fails: row violates policy
            conn.execute(
                "INSERT INTO idempotency_keys (tenant_id, principal, key, request_fingerprint, "
                "response_status, response_body) "
                "VALUES (gen_random_uuid(), 'p', 'k', 'f', 200, '{}')"
            )


def test_empty_tenant_setting_fails_closed(database: Database) -> None:
    """After a transaction ends, a pooled connection may report '' for the setting, not NULL."""
    with connect(database.runtime_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', '', false)")
        assert conn.execute("SELECT count(*) FROM idempotency_keys").fetchone() == (0,)


def test_runtime_cannot_write_tenants(database: Database) -> None:
    with connect(database.runtime_url) as conn:
        conn.execute("SELECT count(*) FROM tenants")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO tenants (external_id, name) VALUES ('x', 'x')")


def test_roles_sql_removes_a_drifted_membership_and_public_create(database: Database) -> None:
    from tests.conftest import ROLES_SQL

    with connect(database.admin_dsn) as conn:
        conn.execute("GRANT app_owner TO app_runtime")
        conn.execute("GRANT CREATE ON SCHEMA public TO PUBLIC")
        conn.execute(ROLES_SQL.read_text())  # type: ignore[arg-type]
        member = conn.execute("SELECT pg_has_role('app_runtime', 'app_owner', 'MEMBER')").fetchone()
        public_create = conn.execute(
            "SELECT has_schema_privilege('app_admin', 'public', 'CREATE')"
        ).fetchone()
    assert member == (False,)
    assert public_create == (False,)
