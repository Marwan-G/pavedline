"""Alembic environment. Migrations run as the owner role, from DATABASE_OWNER_URL, with explicit SQL."""

import os

from alembic import context
from sqlalchemy import create_engine

from app.settings import async_database_url


def owner_url() -> str:
    url = context.config.attributes.get("owner_url") or os.environ.get("DATABASE_OWNER_URL")
    if not url:
        raise RuntimeError("DATABASE_OWNER_URL is required: migrations run as the owner role")
    return async_database_url(url)  # the same psycopg 3 driver, used synchronously here


def run_migrations_online() -> None:
    engine = create_engine(owner_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported: run them against the database")
run_migrations_online()
