"""The example contract and schema pass the pack's checks."""

import pathlib

from tests.conftest import API_DIR, Database, run_script

CONTRACT = API_DIR.parent.parent / "docs" / "api" / "openapi.yaml"


def test_contract_check_passes_feature_complete() -> None:
    r = run_script(
        "contract_check.py", "--app", "app.main:create_app", "--contract", str(CONTRACT), "--feature-complete"
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_contract_check_fails_when_a_field_is_removed(tmp_path: pathlib.Path) -> None:
    broken = tmp_path / "openapi.yaml"
    broken.write_text(
        CONTRACT.read_text().replace(
            "        currency: {type: string, pattern: '^[A-Z]{3}$'}\n        created_at",
            "        created_at",
        )
    )
    r = run_script("contract_check.py", "--app", "app.main:create_app", "--contract", str(broken))
    assert r.returncode == 1
    assert "currency" in r.stdout


def test_rls_check_passes_with_the_items_table(database: Database) -> None:
    r = run_script("rls_check.py", "--database-url", database.admin_dsn)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "items" not in r.stdout  # no problem mentions it


def test_items_table_is_forced_rls(database: Database) -> None:
    import psycopg

    with psycopg.connect(database.admin_dsn) as conn:
        row = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'items'"
        ).fetchone()
    assert row == (True, True)
