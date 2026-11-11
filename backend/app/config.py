"""Settings, read from ADAL_* environment variables (and backend/.env in development).

Secrets have no defaults on purpose: the app refuses to start without them.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADAL_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Production behaviour unless told otherwise.
    env: Literal["dev", "test", "prod"] = "prod"

    database_url: str
    redis_url: str | None = None
    jwt_secret: SecretStr
    mfa_encryption_key: SecretStr

    # The browser origin of the front end. Links in emails point here.
    frontend_url: str = "http://localhost:5173"
    # Extra exact origins allowed for CORS and WebSockets. Empty means same-origin only.
    cors_origins: list[str] = []
    cookie_secure: bool = True

    media_dir: str = "media"
    max_upload_bytes: int = 5 * 1024 * 1024

    access_token_minutes: int = 15
    refresh_token_days: int = 7
    mfa_ticket_minutes: int = 5

    sniping_window_seconds: int = 120
    sniping_extension_seconds: int = 120
    transaction_expiry_hours: int = 48

    scheduler_enabled: bool = True
    scheduler_interval_seconds: float = 1.0

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("ADAL_JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("mfa_encryption_key")
    @classmethod
    def _fernet_key(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value().encode())
        except ValueError as exc:
            raise ValueError("ADAL_MFA_ENCRYPTION_KEY must be a Fernet key (python -m app.cli init-env makes one)") from exc
        return value

    @model_validator(mode="after")
    def _check_origins(self) -> "Settings":
        for origin in [self.frontend_url, *self.cors_origins]:
            parts = urlsplit(origin)
            if parts.scheme not in ("http", "https") or not parts.hostname or parts.path not in ("", "/"):
                raise ValueError(f"not an exact origin: {origin!r}")
            if self.env == "prod" and (parts.scheme != "https" or parts.hostname in LOCAL_HOSTS):
                raise ValueError(f"production origins must be https and not local: {origin!r}")
        return self

    @property
    def allowed_origins(self) -> frozenset[str]:
        origins = {self.frontend_url.rstrip("/"), *(o.rstrip("/") for o in self.cors_origins)}
        if self.env == "dev":
            origins |= {"http://localhost:5173", "http://127.0.0.1:5173"}
        return frozenset(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
