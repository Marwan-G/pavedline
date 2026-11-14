"""The async engine. It connects as the runtime role through the pooler (transaction mode)."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.settings import Settings, async_database_url


def make_engine(settings: Settings) -> AsyncEngine:
    """Create the engine; it does not connect until first use.

    `prepare_threshold=None` turns off server-side prepared statements, which a transaction-mode
    pooler may not keep between transactions. `hide_parameters=True` keeps bound values (personal
    data, tokens) out of database error messages, so they never reach a log line.
    """
    return create_async_engine(
        async_database_url(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"prepare_threshold": None, "connect_timeout": 5},
    )
