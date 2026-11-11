"""TOTP second factor (RFC 6238), encrypted secrets at rest, and one-time recovery codes."""

import hashlib
import hmac
import secrets
import time

import pyotp
import segno
from cryptography.fernet import Fernet

PERIOD_SECONDS = 30
ISSUER = "Adal"
RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i


class SecretBox:
    """Encrypts TOTP secrets so a database dump alone does not reveal them."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def seal(self, secret: str) -> bytes:
        return self._fernet.encrypt(secret.encode())

    def open(self, sealed: bytes) -> str:
        return self._fernet.decrypt(sealed).decode()


def new_secret() -> str:
    return pyotp.random_base32(length=32)


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def qr_svg(uri: str) -> str:
    return segno.make(uri, error="m").svg_inline(scale=5, border=2)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // PERIOD_SECONDS)


def match_step(secret: str, code: str, *, now: float | None = None, window: int = 1) -> int | None:
    """The time step the code belongs to (allowing one step of clock drift), or None.

    The caller stores the step and refuses any step that is not newer, so a code works once.
    """
    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    step_now = current_step(now)
    matched: int | None = None
    for step in range(step_now - window, step_now + window + 1):
        if hmac.compare_digest(totp.generate_otp(step), code):
            matched = step
    return matched


def code_for_step(secret: str, step: int) -> str:
    """Test and seed helper."""
    return pyotp.TOTP(secret).generate_otp(step)


def new_recovery_codes(count: int = 10) -> list[str]:
    def one() -> str:
        chars = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(8))
        return f"{chars[:4]}-{chars[4:]}"

    return [one() for _ in range(count)]


def looks_like_recovery_code(code: str) -> bool:
    cleaned = code.strip().lower().replace(" ", "")
    return len(cleaned) == 9 and cleaned[4] == "-"


def hash_recovery_code(code: str, key: bytes) -> str:
    normalized = code.strip().lower().replace(" ", "")
    return hmac.new(key, normalized.encode(), hashlib.sha256).hexdigest()


def recovery_key(jwt_secret: str) -> bytes:
    """A separate key derived for recovery-code hashing."""
    return hmac.new(jwt_secret.encode(), b"adal recovery codes v1", hashlib.sha256).digest()
