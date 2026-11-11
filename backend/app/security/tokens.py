"""Signed JWTs for access and MFA tickets; random opaque tokens (stored hashed) for refresh and email links."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

ALGORITHM = "HS256"


class TokenError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # "token_expired" or "invalid_token"


def _encode(claims: dict[str, Any], secret: str, lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + lifetime, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_access_token(*, user_id: int, role: str, secret: str, minutes: int) -> str:
    return _encode({"sub": str(user_id), "role": role, "typ": "access"}, secret, timedelta(minutes=minutes))


def create_mfa_ticket(*, user_id: int, secret: str, minutes: int) -> str:
    """Proof that the password step passed. Worth nothing without the second factor."""
    return _encode({"sub": str(user_id), "typ": "mfa"}, secret, timedelta(minutes=minutes))


def decode_token(token: str, *, secret: str, expected_type: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],  # fixed list: no "alg: none", no algorithm confusion
            options={"require": ["exp", "iat", "sub", "typ", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid_token") from exc
    if claims.get("typ") != expected_type:
        raise TokenError("invalid_token")
    return claims


def new_opaque_token() -> tuple[str, str]:
    """A random token for the client and its SHA-256 digest for the database."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_opaque_token(raw)


def hash_opaque_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
