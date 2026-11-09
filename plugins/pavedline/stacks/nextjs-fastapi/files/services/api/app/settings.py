"""Settings: read from the environment, validated at start. Nothing here ever holds a secret value in code."""

from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Plain MAJOR.MINOR.PATCH; `$` in the Rust regex engine matches only at the very end (no trailing newline).
SEMVER = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"


class Settings(BaseSettings):
    """Environment variables (case-insensitive): APP_ENV, DATABASE_URL, DATABASE_OWNER_URL,
    AUTH_ISSUER, AUTH_AUDIENCE, AUTH_JWKS_URL, AUTH_TENANT_CLAIM, LOG_LEVEL, DB_POOL_SIZE, DB_MAX_OVERFLOW,
    MAX_BODY_BYTES, MIN_APP_VERSION."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "production"]

    # The runtime role (app_runtime): what the service connects as. Never the owner.
    database_url: str
    # The owner role (app_owner): migrations only. The service itself never reads it.
    database_owner_url: str | None = None

    auth_issuer: str | None = None
    auth_audience: str | None = None
    auth_jwks_url: str | None = None
    # The claim holding the tenant (organisation) id; a dotted path reaches into nested claims.
    # Default `o.id`: Clerk session token v2 nests the organisation under `o` (v2 is Clerk's default since
    # 2025-04-14). Clerk's v1 tokens used a flat `org_id`: set AUTH_TENANT_CLAIM=org_id for those.
    # Confirm on a decoded development token at the first auth slice.
    auth_tenant_claim: str = "o.id"
    # Requests with a larger body are refused with 413 before parsing and before authentication.
    max_body_bytes: int = 1024 * 1024
    # Oldest mobile app version the API still serves (plain MAJOR.MINOR.PATCH). Sent on every response as
    # `X-Min-App-Version`; an app below it shows a blocking "please update" screen. Raise it only after the
    # store release is live; the API keeps serving every version at or above it (release rule, DEPLOYMENT.md).
    min_app_version: str = Field(default="0.0.0", pattern=SEMVER)

    log_level: str = "INFO"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    @model_validator(mode="after")
    def require_auth_in_production(self) -> Self:
        if self.app_env == "production":
            missing = [
                name for name in ("auth_issuer", "auth_audience", "auth_jwks_url") if not getattr(self, name)
            ]
            if missing:
                raise ValueError("production requires: " + ", ".join(missing))
        return self


def async_database_url(url: str) -> str:
    """The SQLAlchemy URL (psycopg 3 driver) for a plain `postgresql://` connection string."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    raise ValueError("DATABASE_URL must be a postgresql:// URL")
