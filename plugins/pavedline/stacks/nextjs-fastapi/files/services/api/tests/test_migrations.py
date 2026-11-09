import psycopg

from tests.conftest import Database, create_database, drop_database, migrate_down, migrate_up


def tables(dsn: str) -> set[str]:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
    return {r[0] for r in rows}


def test_up_down_up() -> None:
    db = create_database()
    try:
        migrate_up(db)
        assert {"tenants", "idempotency_keys", "alembic_version"} <= tables(db.admin_dsn)
        migrate_down(db)
        assert tables(db.admin_dsn) == {"alembic_version"}
        migrate_up(db)
        assert {"tenants", "idempotency_keys"} <= tables(db.admin_dsn)
    finally:
        drop_database(db)


def test_every_table_is_owned_by_the_owner_role(database: Database) -> None:
    with psycopg.connect(database.admin_dsn) as conn:
        rows = conn.execute(
            "SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    assert rows
    assert {owner for _, owner in rows} == {"app_owner"}
