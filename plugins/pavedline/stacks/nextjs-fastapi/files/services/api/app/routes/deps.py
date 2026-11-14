"""Request dependencies: the engine, the verified principal, the Idempotency-Key header."""

from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth import Principal, TokenVerifier, unauthorized
from app.db.tenant import resolve_tenant
from app.errors import ApiError
from app.events import tenant_id_var
from app.services.idempotency import MAX_KEY_LENGTH

bearer = HTTPBearer(auto_error=False)


def get_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    return engine


def get_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.verifier
    return verifier


DbEngine = Annotated[AsyncEngine, Depends(get_engine)]


async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
    engine: DbEngine,
) -> Principal:
    """401 without a valid token; 403 when the token has no known tenant. The tenant is the verified
    token's claim, never a header, query parameter or body field."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    claims = await verifier.verify(credentials.credentials)
    if claims.tenant_external_id is None:
        raise ApiError(403, "forbidden", "The token does not belong to a tenant")
    tenant_id = await resolve_tenant(engine, claims.tenant_external_id)
    if tenant_id is None:
        raise ApiError(403, "forbidden", "The token does not belong to a known tenant")
    tenant_id_var.set(str(tenant_id))  # the rest of this request's log lines carry the tenant
    return Principal(claims.subject, tenant_id)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """The Idempotency-Key header of an operation that creates or changes state: 400 when missing."""
    if idempotency_key is None or not idempotency_key.strip():
        raise ApiError(400, "idempotency_key_required", "The Idempotency-Key header is required")
    if len(idempotency_key) > MAX_KEY_LENGTH or not idempotency_key.isprintable():
        raise ApiError(
            400,
            "idempotency_key_invalid",
            f"Idempotency-Key must be printable, at most {MAX_KEY_LENGTH} characters",
        )
    return idempotency_key


IdempotencyKey = Annotated[str, Depends(require_idempotency_key)]
