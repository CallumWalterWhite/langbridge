from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from langbridge.packages.common.langbridge_common.config import settings


class RuntimeAuthError(ValueError):
    pass


class RuntimeAuthService:
    _TOKEN_USE = "runtime_access"

    def __init__(self) -> None:
        self._secret = settings.EDGE_RUNTIME_JWT_SECRET or settings.JWT_SECRET
        self._alg = settings.JWT_ALG
        self._token_ttl = max(60, int(settings.EDGE_RUNTIME_TOKEN_TTL_SECONDS))

    @staticmethod
    def hash_registration_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_registration_token(self) -> str:
        return secrets.token_urlsafe(32)

    def issue_runtime_access_token(
        self,
        *,
        tenant_id: uuid.UUID,
        ep_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self._token_ttl)
        payload = {
            "sub": self._TOKEN_USE,
            "tenant_id": str(tenant_id),
            "ep_id": str(ep_id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self._secret, algorithm=self._alg)
        return token, expires_at

    def verify_runtime_access_token(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[self._alg])
        except JWTError as exc:
            raise RuntimeAuthError("Invalid runtime token.") from exc

        if claims.get("sub") != self._TOKEN_USE:
            raise RuntimeAuthError("Invalid runtime token subject.")
        if "tenant_id" not in claims or "ep_id" not in claims:
            raise RuntimeAuthError("Runtime token missing required claims.")
        return claims

    @staticmethod
    def parse_runtime_claims(claims: dict[str, Any]) -> tuple[uuid.UUID, uuid.UUID]:
        try:
            tenant_id = uuid.UUID(str(claims["tenant_id"]))
            ep_id = uuid.UUID(str(claims["ep_id"]))
        except (KeyError, ValueError) as exc:
            raise RuntimeAuthError("Runtime token claims are invalid.") from exc
        return tenant_id, ep_id
