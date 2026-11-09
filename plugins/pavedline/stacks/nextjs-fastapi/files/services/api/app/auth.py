"""Token verification (JWKS). The tenant comes from the verified token, never from the request."""

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import jwt
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.errors import ApiError
from app.settings import Settings

ALGORITHMS = ["RS256", "ES256"]  # asymmetric only: never "none", never HMAC


class JwksClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


@dataclass(frozen=True)
class Claims:
    subject: str
    tenant_external_id: str | None


@dataclass(frozen=True)
class Principal:
    """A verified caller: who, and the tenant (our id) their token belongs to."""

    subject: str
    tenant_id: UUID


def unauthorized() -> ApiError:
    return ApiError(
        401,
        "unauthorized",
        "Missing or invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def claim_at(payload: dict[str, Any], path: str) -> Any:
    """Read a claim by dotted path ("org_id", or "o.id" for a nested claim)."""
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return value  # pyright: ignore[reportUnknownVariableType]


class TokenVerifier:
    def __init__(self, settings: Settings, jwks_client: JwksClient | None = None) -> None:
        self._issuer = settings.auth_issuer
        self._audience = settings.auth_audience
        self._tenant_claim = settings.auth_tenant_claim
        self._configured = bool(settings.auth_issuer and settings.auth_audience and settings.auth_jwks_url)
        if jwks_client is not None:
            self._jwks: JwksClient | None = jwks_client
        elif settings.auth_jwks_url:
            self._jwks = PyJWKClient(settings.auth_jwks_url, cache_keys=True, timeout=5)
        else:
            self._jwks = None

    async def verify(self, token: str) -> Claims:
        if not self._configured or self._jwks is None:
            raise unauthorized()  # fail closed: no auth configured means nobody gets in
        # The key lookup may fetch the JWKS over the network (blocking), so it runs in a thread.
        return await asyncio.to_thread(self._verify, token)

    def _verify(self, token: str) -> Claims:
        assert self._jwks is not None  # noqa: S101 - checked in verify()
        try:
            key = self._jwks.get_signing_key_from_jwt(token)
            payload: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except PyJWKClientConnectionError as exc:
            # the key set could not be fetched: our dependency is down, the caller's token is not at fault
            raise ApiError(503, "auth_unavailable", "Authentication is temporarily unavailable") from exc
        except jwt.PyJWTError as exc:
            raise unauthorized() from exc
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise unauthorized()
        tenant = claim_at(payload, self._tenant_claim)
        return Claims(subject, tenant if isinstance(tenant, str) and tenant else None)
