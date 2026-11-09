import pathlib

import psycopg

from tests.conftest import Database, run_script


def rls(db: Database, *extra: str) -> tuple[int, str]:
    r = run_script("rls_check.py", "--database-url", db.admin_dsn, *extra)
    return r.returncode, r.stdout + r.stderr


def test_the_starter_passes(database: Database) -> None:
    code, out = rls(database)
    assert code == 0, out


def execute_as_admin(db: Database, *statements: str) -> None:
    with psycopg.connect(db.admin_dsn, autocommit=True) as conn:
        for s in statements:
            conn.execute(s)  # type: ignore[arg-type]


def test_fails_on_a_table_without_force_rls(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE TABLE widgets (id int PRIMARY KEY, tenant_id uuid NOT NULL)",
        "ALTER TABLE widgets ENABLE ROW LEVEL SECURITY",
        "CREATE POLICY tenant_isolation ON widgets "
        "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)",
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "widgets" in out and "FORCE" in out


def test_fails_on_a_table_without_rls_at_all(fresh_database: Database) -> None:
    execute_as_admin(fresh_database, "CREATE TABLE things (id int PRIMARY KEY, tenant_id uuid NOT NULL)")
    code, out = rls(fresh_database)
    assert code == 1
    assert "things" in out and "ENABLE" in out


def test_fails_on_a_missing_or_nullable_tenant_id(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE TABLE no_tenant (id int PRIMARY KEY)",
        "CREATE TABLE null_tenant (id int PRIMARY KEY, tenant_id uuid)",
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "no_tenant" in out and "null_tenant" in out


def test_fails_on_a_policy_that_ignores_the_setting(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE TABLE open_table (id int PRIMARY KEY, tenant_id uuid NOT NULL)",
        "ALTER TABLE open_table ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE open_table FORCE ROW LEVEL SECURITY",
        "CREATE POLICY everyone ON open_table USING (true) WITH CHECK (true)",
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "open_table" in out and "policy" in out.lower()


def test_a_global_table_needs_to_be_listed_with_a_reason(
    fresh_database: Database, tmp_path: pathlib.Path
) -> None:
    execute_as_admin(fresh_database, "CREATE TABLE countries (code text PRIMARY KEY)")
    code, out = rls(fresh_database)
    assert code == 1 and "countries" in out
    listed = tmp_path / "global.txt"
    listed.write_text(
        "tenants  # the tenant directory\nalembic_version  # migration bookkeeping\n"
        "countries  # reference data shared by every tenant\n"
    )
    code, out = rls(fresh_database, "--global-tables", str(listed))
    assert code == 0, out
    listed.write_text("tenants  # x\nalembic_version  # y\ncountries\n")
    code, out = rls(fresh_database, "--global-tables", str(listed))
    assert code == 1 and "reason" in out


def test_fails_when_the_runtime_role_owns_a_table(fresh_database: Database) -> None:
    execute_as_admin(fresh_database, "ALTER TABLE tenants OWNER TO app_runtime")
    code, out = rls(fresh_database)
    assert code == 1
    assert "app_runtime" in out and "owns" in out


def test_fails_when_the_runtime_role_can_bypass_rls(fresh_database: Database) -> None:
    execute_as_admin(fresh_database, "ALTER ROLE app_runtime BYPASSRLS")
    try:
        code, out = rls(fresh_database)
        assert code == 1
        assert "BYPASSRLS" in out
    finally:
        execute_as_admin(fresh_database, "ALTER ROLE app_runtime NOBYPASSRLS")


def test_usage_error_exits_2() -> None:
    r = run_script("rls_check.py", "--database-url", "postgresql://nobody@127.0.0.1:1/none")
    assert r.returncode == 2


CANON = (
    "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
    "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
)


def tenant_table(name: str, *policies: str, schema: str = "public") -> list[str]:
    return [
        f"CREATE TABLE {schema}.{name} (id int PRIMARY KEY, tenant_id uuid NOT NULL)",
        f"ALTER TABLE {schema}.{name} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {schema}.{name} FORCE ROW LEVEL SECURITY",
        *policies,
    ]


def test_fails_on_an_extra_permissive_policy_that_is_open(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        *tenant_table(
            "leaky",
            f"CREATE POLICY tenant_isolation ON leaky {CANON}",
            "CREATE POLICY open_read ON leaky FOR SELECT USING (true)",
        ),
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "leaky" in out and "open_read" in out


def test_fails_on_a_policy_with_a_constant_true_or(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        *tenant_table(
            "ortable",
            "CREATE POLICY tenant_isolation ON ortable "
            "USING (true OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)",
        ),
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "ortable" in out and "tenant_isolation" in out


def test_fails_on_a_policy_without_with_check(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        *tenant_table(
            "nocheck",
            "CREATE POLICY tenant_isolation ON nocheck "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)",
        ),
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "nocheck" in out


def test_a_custom_policy_needs_an_allow_list_entry_with_a_reason(
    fresh_database: Database, tmp_path: pathlib.Path
) -> None:
    execute_as_admin(
        fresh_database,
        *tenant_table(
            "custom",
            "CREATE POLICY tenant_isolation ON custom "
            "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND id > 0) "
            "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)",
        ),
    )
    code, out = rls(fresh_database)
    assert code == 1 and "custom" in out
    listed = tmp_path / "g.txt"
    listed.write_text(
        "tenants  # x\nalembic_version  # y\npolicy:custom.tenant_isolation  # extra id filter, reviewed\n"
    )
    code, out = rls(fresh_database, "--global-tables", str(listed))
    assert code == 0, out


def test_fails_on_a_plain_view(fresh_database: Database) -> None:
    execute_as_admin(fresh_database, "CREATE VIEW all_keys AS SELECT * FROM idempotency_keys")
    code, out = rls(fresh_database)
    assert code == 1
    assert "all_keys" in out and "security_invoker" in out


def test_a_security_invoker_view_passes(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE VIEW safe_keys WITH (security_invoker = true) AS SELECT * FROM idempotency_keys",
    )
    code, out = rls(fresh_database)
    assert code == 0, out


def test_fails_on_a_materialized_view(fresh_database: Database) -> None:
    execute_as_admin(fresh_database, "CREATE MATERIALIZED VIEW mv_keys AS SELECT * FROM idempotency_keys")
    code, out = rls(fresh_database)
    assert code == 1
    assert "mv_keys" in out and "materialized" in out.lower()


def test_fails_on_a_tenant_table_in_another_schema(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE SCHEMA other",
        "CREATE TABLE other.stash (id int PRIMARY KEY, tenant_id uuid NOT NULL)",
        "GRANT USAGE ON SCHEMA other TO app_runtime",
        "GRANT SELECT ON other.stash TO app_runtime",
    )
    code, out = rls(fresh_database)
    assert code == 1
    assert "other.stash" in out


def test_a_schema_the_runtime_role_cannot_use_is_ignored(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE SCHEMA hidden",
        "CREATE TABLE hidden.stash (id int PRIMARY KEY)",
    )
    code, out = rls(fresh_database)
    assert code == 0, out


def test_fails_when_the_runtime_role_is_a_member_of_the_owner(fresh_database: Database) -> None:
    execute_as_admin(fresh_database, "GRANT app_owner TO app_runtime")
    try:
        code, out = rls(fresh_database)
        assert code == 1
        assert "member" in out and "app_owner" in out
    finally:
        execute_as_admin(fresh_database, "REVOKE app_owner FROM app_runtime")


def test_fails_when_the_runtime_role_owns_a_sequence_function_or_schema(fresh_database: Database) -> None:
    execute_as_admin(
        fresh_database,
        "CREATE SEQUENCE s1 OWNED BY NONE",
        "ALTER SEQUENCE s1 OWNER TO app_runtime",
    )
    code, out = rls(fresh_database)
    assert code == 1 and "s1" in out
    execute_as_admin(
        fresh_database,
        "ALTER SEQUENCE s1 OWNER TO app_owner",
        "CREATE FUNCTION f1() RETURNS int LANGUAGE sql AS 'SELECT 1'",
        "ALTER FUNCTION f1() OWNER TO app_runtime",
    )
    code, out = rls(fresh_database)
    assert code == 1 and "f1" in out
    execute_as_admin(
        fresh_database,
        "ALTER FUNCTION f1() OWNER TO app_owner",
        "CREATE SCHEMA mine AUTHORIZATION app_runtime",
    )
    code, out = rls(fresh_database)
    assert code == 1 and "mine" in out
