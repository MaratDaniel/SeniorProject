"""Argon2id password hashing (OWASP A02). Hashing runs in a worker thread so it never blocks the event loop."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from starlette.concurrency import run_in_threadpool

MIN_LENGTH = 10
MAX_LENGTH = 128

_hasher = PasswordHasher()  # Argon2id with the library's RFC 9106 defaults
# Verified against when the email is unknown, so both paths take the same time.
_TIMING_EQUALIZER = _hasher.hash("timing-equalizer, never a real password")


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hasher.hash, password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    target = password_hash or _TIMING_EQUALIZER

    def _verify() -> bool:
        try:
            return _hasher.verify(target, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    matched = await run_in_threadpool(_verify)
    return matched and password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str, email: str) -> str | None:
    """A reason the password is unacceptable, or None."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    if password.strip().lower() in {email.lower(), email.split("@")[0].lower()}:
        return "Do not use your email address as the password."
    return None
