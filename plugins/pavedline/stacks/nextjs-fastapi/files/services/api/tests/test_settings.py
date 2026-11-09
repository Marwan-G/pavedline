import pytest
from pydantic import ValidationError

from app.settings import Settings, async_database_url


def test_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app_runtime:pw@db:5432/app")
    monkeypatch.setenv("AUTH_TENANT_CLAIM", "org_id")
    monkeypatch.setenv("MAX_BODY_BYTES", "2048")
    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.app_env == "development"
    assert settings.auth_tenant_claim == "org_id"
    assert settings.max_body_bytes == 2048
    assert settings.database_owner_url is None


def test_production_requires_the_auth_settings() -> None:
    with pytest.raises(ValidationError) as err:
        Settings(app_env="production", database_url="postgresql://a:b@h/d")
    for name in ("auth_issuer", "auth_audience", "auth_jwks_url"):
        assert name in str(err.value)


def test_production_with_auth_settings_is_valid() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql://a:b@h/d",
        auth_issuer="https://issuer.test",
        auth_audience="acme-api",
        auth_jwks_url="https://issuer.test/jwks.json",
    )
    assert settings.auth_tenant_claim == "o.id"  # Clerk session token v2
    assert settings.max_body_bytes == 1024 * 1024


def test_unknown_environment_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="staging", database_url="postgresql://a:b@h/d")  # pyright: ignore[reportArgumentType]


def test_driver_is_added_to_the_url() -> None:
    assert async_database_url("postgresql://u:p@h/d").startswith("postgresql+psycopg://")
    assert async_database_url("postgres://u:p@h/d").startswith("postgresql+psycopg://")
    assert async_database_url("postgresql+psycopg://u:p@h/d").startswith("postgresql+psycopg://")
