import psycopg
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.webhook_events import DEFAULT_RETENTION_DAYS, purge_expired_webhook_events
from app.settings import Settings, async_database_url
from tests.conftest import Database


async def test_purge_deletes_only_expired_rows_and_retention_is_configurable(database: Database) -> None:
    assert DEFAULT_RETENTION_DAYS == 30
    assert Settings(app_env="test", database_url="postgresql://u:p@h/d").webhook_event_retention_days == 30  # pyright: ignore[reportCallIssue]
    with psycopg.connect(database.owner_url) as conn:
        conn.execute("DELETE FROM webhook_events WHERE provider = 'purge_test'")
        for event_id, days in (("old", 31), ("mid", 10), ("new", 0)):
            conn.execute(
                "INSERT INTO webhook_events (provider, event_id, received_at) "
                "VALUES ('purge_test', %s, now() - make_interval(days => %s))",
                (event_id, days),
            )
        conn.commit()
    engine = create_async_engine(
        async_database_url(database.runtime_url), connect_args={"prepare_threshold": None}
    )
    try:
        assert await purge_expired_webhook_events(engine) >= 1
        assert _left(database) == {"mid", "new"}
        assert await purge_expired_webhook_events(engine, retention_days=5) >= 1
        assert _left(database) == {"new"}
    finally:
        await engine.dispose()


def _left(db: Database) -> set[str]:
    with psycopg.connect(db.owner_url) as conn:
        rows = conn.execute("SELECT event_id FROM webhook_events WHERE provider = 'purge_test'").fetchall()
    return {r[0] for r in rows}


class _Result:
    rowcount = 0


class _Conn:
    def __init__(self, seen: list[object]) -> None:
        self.seen = seen

    async def __aenter__(self) -> _Conn:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def begin(self) -> _Conn:
        return self

    async def execute(self, _statement: object, params: dict[str, str]) -> _Result:
        self.seen.append(params["ttl"])
        return _Result()


class _Engine:
    def __init__(self) -> None:
        self.seen: list[object] = []

    def connect(self) -> _Conn:
        return _Conn(self.seen)


async def test_retention_comes_from_the_settings_at_the_call_site() -> None:
    engine = _Engine()
    settings = Settings(  # pyright: ignore[reportCallIssue]
        app_env="test", database_url="postgresql://u:p@h/d", webhook_event_retention_days=7
    )
    await purge_expired_webhook_events(engine, settings=settings)  # pyright: ignore[reportArgumentType]
    await purge_expired_webhook_events(engine, settings=settings, retention_days=3)  # pyright: ignore[reportArgumentType]
    await purge_expired_webhook_events(engine)  # pyright: ignore[reportArgumentType]
    assert engine.seen == ["7 days", "3 days", f"{DEFAULT_RETENTION_DAYS} days"]
