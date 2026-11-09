"""Test tokens and an in-process JWKS (no network)."""

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt import PyJWKClient
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from jwt.exceptions import PyJWKClientConnectionError

ISSUER = "https://issuer.test"
AUDIENCE = "acme-api"
JWKS_URL = "https://issuer.test/.well-known/jwks.json"
KID = "test-key-1"


class StaticJWKSClient(PyJWKClient):
    """The real PyJWKClient key lookup (by kid), fed from memory instead of the network."""

    def __init__(self, jwks: dict[str, Any]) -> None:
        super().__init__(JWKS_URL)
        self._jwks = jwks

    def fetch_data(self) -> Any:
        return self._jwks


class CountingJWKSClient(StaticJWKSClient):
    """Counts JWKS fetches, and can fail them like a network error."""

    def __init__(self, jwks: dict[str, Any], *, fail: bool = False) -> None:
        super().__init__(jwks)
        self.fetches = 0
        self.fail = fail

    def fetch_data(self) -> Any:
        self.fetches += 1
        if self.fail:
            raise PyJWKClientConnectionError("jwks endpoint unreachable")
        return self._jwks


class TokenFactory:
    def __init__(self) -> None:
        self.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.ec_key = ec.generate_private_key(ec.SECP256R1())
        jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(self.rsa_key.public_key()))
        jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
        ec_jwk: dict[str, Any] = json.loads(ECAlgorithm.to_jwk(self.ec_key.public_key()))
        ec_jwk.update({"kid": "test-key-ec", "alg": "ES256", "use": "sig"})
        self.jwks: dict[str, Any] = {"keys": [jwk, ec_jwk]}

    def jwks_client(self) -> StaticJWKSClient:
        return StaticJWKSClient(self.jwks)

    def counting_client(self, *, fail: bool = False) -> CountingJWKSClient:
        return CountingJWKSClient(self.jwks, fail=fail)

    def token(
        self,
        *,
        tenant: str | None = "org_default",
        subject: str = "user_1",
        issuer: str = ISSUER,
        audience: str = AUDIENCE,
        expires_in: int = 300,
        claim: str = "o.id",
        algorithm: str = "RS256",
        kid: str | None = None,
        key: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": now,
            "exp": now + expires_in,
        }
        if tenant is not None:
            node = payload
            *parents, leaf = claim.split(".")
            for part in parents:
                node = node.setdefault(part, {})
            node[leaf] = tenant
        if extra:
            payload.update(extra)
        if key is None:
            key = self.ec_key if algorithm == "ES256" else self.rsa_key
        if kid is None:
            kid = "test-key-ec" if algorithm == "ES256" else KID
        return jwt.encode(payload, key, algorithm=algorithm, headers={"kid": kid})
