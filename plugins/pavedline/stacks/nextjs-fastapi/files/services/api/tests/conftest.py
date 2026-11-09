"""Shared fixtures: a throwaway database per test session, tokens, and the two-tenant leak world.

`DATABASE_URL` must be an administrator (superuser) URL of a throwaway Postgres server. Tests create
their own databases on it, run `db/roles.sql`, migrate as `app_owner` and run the app as `app_runtime`.
Never point it at a real database.
"""

import os
import pathlib
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from app.main import create_app
from app.settings import Settings
from tests import leak_registry
from tests.tokens import AUDIENCE, ISSUER, JWKS_URL, TokenFactory

API_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = API_DIR.parent.parent / "scripts"
ROLES_SQL = API_DIR / "db" / "roles.sql"
WEBHOOK_OVERRIDES = (
    "max_body_bytes",
    "webhook_clerk_secret",
    "webhook_stripe_secret",
    "webhook_tolerance_seconds",
)
PASSWORDS = {"app_owner": "owner-pw", "app_runtime": "runtime-pw", "app_admin": "admin-pw"}


def admin_url() -> URL:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        pytest.fail("DATABASE_URL is required: an administrator URL of a throwaway Postgres server")
    return make_url(raw).set(drivername="postgresql")


def url_for(db: str, role: str) -> str:
    return (
        admin_url()
        .set(database=db, username=role, password=PASSWORDS[role])
        .render_as_string(hide_password=False)
    )


def admin_dsn(db: str | None = None) -> str:
    url = admin_url()
    if db:
        url = url.set(database=db)
    return url.render_as_string(hide_password=False)


def install_roles() -> None:
    with psycopg.connect(admin_dsn(), autocommit=True) as conn:
        conn.execute(ROLES_SQL.read_text())  # type: ignore[arg-type]
        for role, password in PASSWORDS.items():
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
            )


@dataclass(frozen=True)
class Database:
    name: str

    @property
    def owner_url(self) -> str:
        return url_for(self.name, "app_owner")

    @property
    def runtime_url(self) -> str:
        return url_for(self.name, "app_runtime")

    @property
    def admin_dsn(self) -> str:
        return admin_dsn(self.name)


def create_database() -> Database:
    install_roles()
    name = "pl_" + uuid.uuid4().hex[:12]
    with psycopg.connect(admin_dsn(), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER app_owner").format(sql.Identifier(name)))
    return Database(name)


def drop_database(db: Database) -> None:
    with psycopg.connect(admin_dsn(), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db.name)))


def alembic_config(owner_url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.attributes["owner_url"] = owner_url
    return cfg


def migrate_up(db: Database) -> None:
    command.upgrade(alembic_config(db.owner_url), "head")


def migrate_down(db: Database) -> None:
    command.downgrade(alembic_config(db.owner_url), "base")


@pytest.fixture(scope="session")
def database() -> Iterator[Database]:
    db = create_database()
    migrate_up(db)
    yield db
    drop_database(db)


@pytest.fixture
def fresh_database() -> Iterator[Database]:
    """A migrated database private to one test (for tests that damage the schema)."""
    db = create_database()
    migrate_up(db)
    yield db
    drop_database(db)


@pytest.fixture(scope="session")
def tokens() -> TokenFactory:
    return TokenFactory()


def make_settings(db: Database, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "database_url": db.runtime_url,
        "auth_issuer": ISSUER,
        "auth_audience": AUDIENCE,
        "auth_jwks_url": JWKS_URL,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
async def app_factory(database: Database, tokens: TokenFactory) -> AsyncIterator[Callable[..., Any]]:
    """Build apps wired to the test database and the in-process JWKS; disposed after the test."""
    made: list[Any] = []

    def build(**kwargs: Any) -> Any:
        overrides = {k: kwargs.pop(k) for k in WEBHOOK_OVERRIDES if k in kwargs}
        app = create_app(make_settings(database, **overrides), jwks_client=tokens.jwks_client(), **kwargs)
        made.append(app)
        return app

    yield build
    for app in made:
        await app.state.engine.dispose()


@pytest.fixture
async def app(app_factory: Callable[..., Any]) -> Any:
    return app_factory()


@pytest.fixture
async def client(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def client_for(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@dataclass(frozen=True)
class World:
    """Two tenants, each with seeded data, and a token for each."""

    db: Database
    tenant_a: uuid.UUID
    tenant_b: uuid.UUID
    ext_a: str
    ext_b: str
    token_a: str
    token_b: str
    ids_a: dict[str, Any]
    ids_b: dict[str, Any]

    def headers(self, which: str = "a") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_a if which == 'a' else self.token_b}"}


def make_tenant(db: Database, tokens: TokenFactory, label: str) -> tuple[uuid.UUID, str]:
    ext = f"org_{label}_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(db.owner_url) as conn:
        row = conn.execute(
            "INSERT INTO tenants (external_id, name) VALUES (%s, %s) RETURNING id", (ext, label)
        ).fetchone()
        assert row is not None
    return row[0], ext


@pytest.fixture
def world(database: Database, tokens: TokenFactory) -> World:
    tenant_a, ext_a = make_tenant(database, tokens, "a")
    tenant_b, ext_b = make_tenant(database, tokens, "b")
    with psycopg.connect(database.owner_url) as conn:
        ids_a = leak_registry.seed(conn, tenant_a)
        ids_b = leak_registry.seed(conn, tenant_b)
        conn.commit()
    return World(
        db=database,
        tenant_a=tenant_a,
        tenant_b=tenant_b,
        ext_a=ext_a,
        ext_b=ext_b,
        token_a=tokens.token(tenant=ext_a, subject="user_a"),
        token_b=tokens.token(tenant=ext_b, subject="user_b"),
        ids_a=ids_a,
        ids_b=ids_b,
    )


def run_script(name: str, *args: str, cwd: pathlib.Path = API_DIR) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPTS_DIR / name), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
        timeout=120,
    )
