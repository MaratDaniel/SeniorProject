"""Request dependencies: settings, sessions, the current user and the role gates.

Deny by default: every route that changes data depends on one of the gates below,
and the role is always read from the database, not trusted from the token.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.engine.base import StrategyRegistry
from app.errors import ApiError
from app.models import Role, User
from app.realtime.broker import Broker
from app.security.ratelimit import RateLimiter
from app.security.tokens import TokenError, decode_token

_bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.sessionmaker


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


def get_broker(request: Request) -> Broker:
    return request.app.state.broker


def get_strategies(request: Request) -> StrategyRegistry:
    return request.app.state.strategies


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def current_user_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    if credentials is None:
        return None
    settings: Settings = request.app.state.settings
    try:
        claims = decode_token(credentials.credentials, secret=settings.jwt_secret.get_secret_value(), expected_type="access")
    except TokenError as exc:
        message = "Your session has expired." if exc.code == "token_expired" else "Sign in again."
        raise ApiError(401, exc.code, message, headers={"WWW-Authenticate": "Bearer"}) from exc
    async with request.app.state.sessionmaker() as session:
        user = await session.get(User, int(claims["sub"]))
    if user is None:
        raise ApiError(401, "invalid_token", "Sign in again.", headers={"WWW-Authenticate": "Bearer"})
    return user


async def current_user(user: Annotated[User | None, Depends(current_user_optional)]) -> User:
    if user is None:
        raise ApiError(401, "not_authenticated", "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    return user


def ensure_verified(user: User) -> None:
    if user.email_verified_at is None:
        raise ApiError(403, "email_not_verified", "Confirm your email address first. We sent you a link.")


async def seller_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != Role.SELLER:
        raise ApiError(403, "forbidden", "Only seller accounts can list items.")
    ensure_verified(user)
    if not user.mfa_enabled:
        raise ApiError(403, "mfa_setup_required", "Turn on two-step sign-in before you sell.")
    return user


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != Role.ADMIN:
        raise ApiError(403, "forbidden", "Administrators only.")
    if not user.mfa_enabled:
        raise ApiError(403, "mfa_setup_required", "Turn on two-step sign-in first.")
    return user


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SessionmakerDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
LimiterDep = Annotated[RateLimiter, Depends(get_limiter)]
BrokerDep = Annotated[Broker, Depends(get_broker)]
StrategiesDep = Annotated[StrategyRegistry, Depends(get_strategies)]
OptionalUser = Annotated[User | None, Depends(current_user_optional)]
CurrentUser = Annotated[User, Depends(current_user)]
SellerUser = Annotated[User, Depends(seller_user)]
AdminUser = Annotated[User, Depends(admin_user)]
