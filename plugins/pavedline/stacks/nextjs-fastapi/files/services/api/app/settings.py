"""Settings: read from the environment, validated at start. Nothing here ever holds a secret value in code."""

import base64
import binascii
from typing import Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Plain MAJOR.MINOR.PATCH; `$` in the Rust regex engine matches only at the very end (no trailing newline).
SEMVER = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"


MIN_SVIX_KEY_BYTES = 16  # Svix secrets decode to 24 to 64 bytes; shorter is not a real secret
MIN_STRIPE_SECRET_LENGTH = 16  # `whsec_` plus at least 10 characters


class Settings(BaseSettings):
    """Environment variables (case-insensitive): APP_ENV, DATABASE_URL, DATABASE_OWNER_URL,
    AUTH_ISSUER, AUTH_AUDIENCE, AUTH_JWKS_URL, AUTH_TENANT_CLAIM, LOG_LEVEL, DB_POOL_SIZE, DB_MAX_OVERFLOW,
    MAX_BODY_BYTES, MIN_APP_VERSION, WEBHOOK_CLERK_SECRET, WEBHOOK_STRIPE_SECRET,
    WEBHOOK_TOLERANCE_SECONDS,
    WEBHOOK_EVENT_RETENTION_DAYS."""

    # hide_input_in_errors: a ValidationError must never echo an environment value (a secret).
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False, hide_input_in_errors=True)

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

    # Signed webhooks (routes/webhooks.py). A provider's route exists only when its secret is set: `whsec_...`
    # from the Clerk (Svix) endpoint, `whsec_...` from the Stripe endpoint or `stripe listen`. Never in code.
    webhook_clerk_secret: SecretStr | None = None
    webhook_stripe_secret: SecretStr | None = None
    # A signed timestamp further than this from now (past or future) is refused. Never 0 (no check at all).
    webhook_tolerance_seconds: int = Field(default=300, ge=1, le=3600)
    # Days a claimed webhook event id is remembered (replay protection); the purge job deletes older ones.
    webhook_event_retention_days: int = Field(default=30, ge=1, le=365)

    log_level: str = "INFO"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    @field_validator("webhook_clerk_secret", "webhook_stripe_secret", mode="before")
    @classmethod
    def blank_secret_is_not_configured(cls, value: Any) -> Any:
        """A blank value (a Helm default, `${X:-}`) means "not configured": no route."""
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str) and not raw.strip():
            return None
        return value

    @field_validator("webhook_clerk_secret")
    @classmethod
    def svix_secret_is_well_formed(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            raw = value.get_secret_value().strip()
            try:
                key = base64.b64decode(raw.removeprefix("whsec_"), validate=True)
            except binascii.Error, ValueError:
                key = b""
            if not raw.startswith("whsec_") or len(key) < MIN_SVIX_KEY_BYTES:
                raise ValueError("WEBHOOK_CLERK_SECRET must be `whsec_` followed by base64")
            return SecretStr(raw)
        return value

    @field_validator("webhook_stripe_secret")
    @classmethod
    def stripe_secret_is_well_formed(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            raw = value.get_secret_value().strip()
            if not raw.startswith("whsec_") or len(raw) < MIN_STRIPE_SECRET_LENGTH:
                raise ValueError("WEBHOOK_STRIPE_SECRET must start with `whsec_`")
            return SecretStr(raw)
        return value

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
