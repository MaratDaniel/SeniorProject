"""Accounts: sign-up, email verification, sign-in with TOTP, sessions, password reset (FR-1 to FR-6)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import Settings
from app.db import db_now
from app.deps import CurrentUser, LimiterDep, SessionDep, SettingsDep, client_ip
from app.errors import ApiError
from app.mail import queue_email
from app.models import EmailToken, RecoveryCode, RefreshToken, Role, TokenPurpose, User
from app.schemas import (
    AuthOk,
    CodeIn,
    EmailIn,
    LoginIn,
    LoginMfaIn,
    MfaRequired,
    MfaSetupOut,
    RecoveryCodesOut,
    RefreshOut,
    RegisterIn,
    ResetPasswordIn,
    TokenIn,
    UserEnvelope,
    UserOut,
)
from app.security.passwords import hash_password, needs_rehash, password_problem, verify_password
from app.security.tokens import (
    TokenError,
    create_access_token,
    create_mfa_ticket,
    decode_token,
    hash_opaque_token,
    new_opaque_token,
)
from app.security.totp import (
    SecretBox,
    hash_recovery_code,
    looks_like_recovery_code,
    match_step,
    new_recovery_codes,
    new_secret,
    provisioning_uri,
    qr_svg,
    recovery_key,
)
from app.views import user_out

router = APIRouter(prefix="/api/auth", tags=["accounts"])

REFRESH_COOKIE = "adal_refresh"
COOKIE_PATH = "/api/auth"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT = timedelta(minutes=15)
ROTATION_GRACE = timedelta(seconds=60)
VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=1)


# ---------- helpers ----------


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _box(settings: Settings) -> SecretBox:
    return SecretBox(settings.mfa_encryption_key.get_secret_value())


def _invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "That email and password do not match.")


def _locked(until: datetime) -> ApiError:
    return ApiError(
        423,
        "account_locked",
        "Too many failed attempts. The account is locked for a few minutes.",
        {"locked_until": until.isoformat().replace("+00:00", "Z")},
    )


def _cookie_header(settings: Settings, value: str | None) -> str:
    """A Set-Cookie header for the refresh token (value None clears it)."""
    scratch = Response()
    if value is None:
        scratch.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, secure=settings.cookie_secure, httponly=True, samesite="strict")
    else:
        scratch.set_cookie(
            REFRESH_COOKIE,
            value,
            max_age=settings.refresh_token_days * 86400,
            path=COOKIE_PATH,
            secure=settings.cookie_secure,
            httponly=True,
            samesite="strict",
        )
    return scratch.headers["set-cookie"]


async def _start_session(session: AsyncSession, user: User, settings: Settings, response: Response, now: datetime) -> str:
    raw, digest = new_opaque_token()
    session.add(RefreshToken(user_id=user.id, token_hash=digest, expires_at=now + timedelta(days=settings.refresh_token_days)))
    response.headers.append("set-cookie", _cookie_header(settings, raw))
    return create_access_token(
        user_id=user.id, role=user.role, secret=settings.jwt_secret.get_secret_value(), minutes=settings.access_token_minutes
    )


def _register_failure(user: User, now: datetime) -> bool:
    """Count a failed password or code. Returns True when this failure locks the account."""
    user.failed_logins += 1
    if user.failed_logins >= MAX_FAILED_ATTEMPTS:
        user.failed_logins = 0
        user.locked_until = now + LOCKOUT
        return True
    return False


async def _new_email_token(session: AsyncSession, user: User, purpose: TokenPurpose, ttl: timedelta, now: datetime) -> str:
    raw, digest = new_opaque_token()
    session.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=digest, expires_at=now + ttl))
    return raw


async def _consume_email_token(session: AsyncSession, raw: str, purpose: TokenPurpose) -> EmailToken:
    token = (
        await session.execute(
            select(EmailToken)
            .where(EmailToken.token_hash == hash_opaque_token(raw), EmailToken.purpose == purpose)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if token is None or token.used_at is not None:
        raise ApiError(400, "invalid_token", "This link is not valid. Request a new one.")
    now = await db_now(session)
    if token.expires_at <= now:
        raise ApiError(400, "token_expired", "This link has expired. Request a new one.")
    token.used_at = now
    return token


def _verification_email(settings: Settings, raw: str) -> tuple[str, str]:
    link = f"{settings.frontend_url.rstrip('/')}/verify-email?token={raw}"
    return "Confirm your email for Adal", f"Confirm your email address to start bidding and selling:\n\n{link}\n\nThe link works for 24 hours.\n"


async def _lock_user(session: AsyncSession, user_id: int) -> User | None:
    return (
        await session.execute(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


# ---------- sign-up and verification ----------


@router.post("/register", status_code=201, response_model=UserEnvelope)
async def register(body: RegisterIn, request: Request, session: SessionDep, settings: SettingsDep, limiter: LimiterDep) -> UserEnvelope:
    ip = client_ip(request)
    limiter.check(f"register:{ip}", 10, 3600)
    email = _normalize_email(str(body.email))
    problem = password_problem(body.password, email)
    if problem:
        raise ApiError(422, "weak_password", problem, {"fields": {"password": problem}})
    password_hash = await hash_password(body.password)
    try:
        async with session.begin():
            if await session.scalar(select(User.id).where(User.email == email)) is not None:
                raise ApiError(409, "email_taken", "An account with this email already exists.")
            user = User(email=email, password_hash=password_hash, role=body.role)
            session.add(user)
            await session.flush()
            now = await db_now(session)
            raw = await _new_email_token(session, user, TokenPurpose.VERIFY_EMAIL, VERIFY_TTL, now)
            subject, text = _verification_email(settings, raw)
            queue_email(session, to=email, subject=subject, body=text)
            audit.record(session, "auth.registered", actor_id=user.id, target_type="user", target_id=user.id, ip=ip, data={"role": body.role})
    except IntegrityError as exc:  # two sign-ups with one email at the same moment
        raise ApiError(409, "email_taken", "An account with this email already exists.") from exc
    return UserEnvelope(user=user_out(user))


@router.post("/verify-email")
async def verify_email(body: TokenIn, request: Request, session: SessionDep) -> dict[str, bool]:
    async with session.begin():
        token = await _consume_email_token(session, body.token, TokenPurpose.VERIFY_EMAIL)
        user = await _lock_user(session, token.user_id)
        assert user is not None
        if user.email_verified_at is None:
            user.email_verified_at = token.used_at
        audit.record(session, "auth.email_verified", actor_id=user.id, target_type="user", target_id=user.id, ip=client_ip(request))
    return {"verified": True}


@router.post("/resend-verification", status_code=202)
async def resend_verification(body: EmailIn, request: Request, session: SessionDep, settings: SettingsDep, limiter: LimiterDep) -> dict:
    email = _normalize_email(str(body.email))
    limiter.check(f"resend-ip:{client_ip(request)}", 10, 3600)
    limiter.check(f"resend:{email}", 3, 3600)
    async with session.begin():
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None and user.email_verified_at is None:
            raw = await _new_email_token(session, user, TokenPurpose.VERIFY_EMAIL, VERIFY_TTL, await db_now(session))
            subject, text = _verification_email(settings, raw)
            queue_email(session, to=email, subject=subject, body=text)
    return {}  # the same answer whether or not the account exists


# ---------- sign-in ----------


@router.post("/login", response_model=AuthOk | MfaRequired)
async def login(
    body: LoginIn, request: Request, response: Response, session: SessionDep, settings: SettingsDep, limiter: LimiterDep
) -> AuthOk | MfaRequired:
    ip = client_ip(request)
    email = _normalize_email(body.email)
    limiter.check(f"login-ip:{ip}", 20, 60)
    limiter.check(f"login:{email}", 10, 60)
    error: ApiError | None = None
    result: AuthOk | MfaRequired | None = None
    async with session.begin():
        # Lock the account row: concurrent guesses for one account are counted one at a time.
        user = (
            await session.execute(select(User).where(User.email == email).with_for_update().execution_options(populate_existing=True))
        ).scalar_one_or_none()
        now = await db_now(session)
        password_ok = await verify_password(user.password_hash if user else None, body.password)
        if user is None:
            audit.record(session, "auth.login_failed", ip=ip, data={"reason": "unknown_email"})
            error = _invalid_credentials()
        elif user.locked_until is not None and user.locked_until > now:
            audit.record(session, "auth.login_blocked", actor_id=user.id, target_type="user", target_id=user.id, ip=ip)
            error = _locked(user.locked_until)
        elif not password_ok:
            locked_now = _register_failure(user, now)
            audit.record(session, "auth.login_failed", actor_id=user.id, target_type="user", target_id=user.id, ip=ip, data={"reason": "password"})
            if locked_now:
                audit.record(session, "auth.locked", actor_id=user.id, target_type="user", target_id=user.id, ip=ip)
                error = _locked(user.locked_until)  # type: ignore[arg-type]
            else:
                error = _invalid_credentials()
        else:
            user.failed_logins = 0
            user.locked_until = None
            if needs_rehash(user.password_hash):
                user.password_hash = await hash_password(body.password)
            if user.mfa_enabled:
                ticket = create_mfa_ticket(user_id=user.id, secret=settings.jwt_secret.get_secret_value(), minutes=settings.mfa_ticket_minutes)
                audit.record(session, "auth.password_ok", actor_id=user.id, target_type="user", target_id=user.id, ip=ip)
                result = MfaRequired(mfa_ticket=ticket)
            else:
                access = await _start_session(session, user, settings, response, now)
                audit.record(session, "auth.login", actor_id=user.id, target_type="user", target_id=user.id, ip=ip, data={"mfa": False})
                result = AuthOk(access_token=access, user=user_out(user))
    if error is not None:
        raise error  # after the commit, so failure counters and audit entries are kept
    assert result is not None
    return result


@router.post("/login/mfa", response_model=AuthOk)
async def login_mfa(
    body: LoginMfaIn, request: Request, response: Response, session: SessionDep, settings: SettingsDep, limiter: LimiterDep
) -> AuthOk:
    ip = client_ip(request)
    limiter.check(f"mfa-ip:{ip}", 20, 60)
    try:
        claims = decode_token(body.mfa_ticket, secret=settings.jwt_secret.get_secret_value(), expected_type="mfa")
    except TokenError as exc:
        raise ApiError(401, "ticket_expired", "Sign in again to get a new code prompt.") from exc
    user_id = int(claims["sub"])
    limiter.check(f"mfa:{user_id}", 10, 60)
    error: ApiError | None = None
    result: AuthOk | None = None
    async with session.begin():
        user = await _lock_user(session, user_id)
        now = await db_now(session)
        if user is None or not user.mfa_enabled or user.mfa_secret_enc is None:
            error = ApiError(401, "ticket_expired", "Sign in again to get a new code prompt.")
        elif user.locked_until is not None and user.locked_until > now:
            error = _locked(user.locked_until)
        else:
            method = "recovery_code" if looks_like_recovery_code(body.code) else "totp"
            if method == "recovery_code":
                used = await session.execute(
                    update(RecoveryCode)
                    .where(
                        RecoveryCode.user_id == user.id,
                        RecoveryCode.code_hash == hash_recovery_code(body.code, recovery_key(settings.jwt_secret.get_secret_value())),
                        RecoveryCode.used_at.is_(None),
                    )
                    .values(used_at=func.clock_timestamp())
                )
                ok = used.rowcount == 1  # atomic: a recovery code works once
            else:
                step = match_step(_box(settings).open(user.mfa_secret_enc), body.code)
                ok = step is not None and (user.mfa_last_step is None or step > user.mfa_last_step)
                if ok:
                    user.mfa_last_step = step  # this code (and every older one) is now spent
            if ok:
                user.failed_logins = 0
                access = await _start_session(session, user, settings, response, now)
                audit.record(session, "auth.login", actor_id=user.id, target_type="user", target_id=user.id, ip=ip, data={"mfa": method})
                result = AuthOk(access_token=access, user=user_out(user))
            else:
                locked_now = _register_failure(user, now)
                audit.record(session, "auth.mfa_failed", actor_id=user.id, target_type="user", target_id=user.id, ip=ip, data={"method": method})
                error = _locked(user.locked_until) if locked_now else ApiError(401, "invalid_code", "That code is not right or has expired.")  # type: ignore[arg-type]
    if error is not None:
        raise error
    assert result is not None
    return result


# ---------- sessions ----------


@router.post("/refresh", response_model=RefreshOut)
async def refresh(request: Request, response: Response, session: SessionDep, settings: SettingsDep) -> RefreshOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    no_session = ApiError(401, "no_session", "Sign in to continue.")
    if not raw:
        raise no_session
    keep_cookie = False
    result: RefreshOut | None = None
    async with session.begin():
        token = (
            await session.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(raw)).with_for_update())
        ).scalar_one_or_none()
        now = await db_now(session)
        if token is None or token.expires_at <= now:
            pass
        elif token.revoked_at is not None:
            if token.revoked_reason == "rotated" and now - token.revoked_at <= ROTATION_GRACE:
                keep_cookie = True  # two tabs refreshed at once; the other request already holds the new cookie
            else:
                # A rotated token came back long after: assume it was stolen and end every session of the user.
                await session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.user_id == token.user_id, RefreshToken.revoked_at.is_(None))
                    .values(revoked_at=now, revoked_reason="reuse")
                )
                audit.record(session, "auth.refresh_reuse", actor_id=token.user_id, target_type="user", target_id=token.user_id, ip=client_ip(request))
        else:
            user = await session.get(User, token.user_id)
            if user is not None:
                token.revoked_at = now
                token.revoked_reason = "rotated"
                access = await _start_session(session, user, settings, response, now)
                result = RefreshOut(access_token=access, user=user_out(user))
    if result is None:
        raise ApiError(401, "no_session", "Sign in to continue.", headers=None if keep_cookie else {"set-cookie": _cookie_header(settings, None)})
    return result


@router.post("/logout", status_code=204)
async def logout(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        async with session.begin():
            revoked = await session.scalars(
                update(RefreshToken)
                .where(RefreshToken.token_hash == hash_opaque_token(raw), RefreshToken.revoked_at.is_(None))
                .values(revoked_at=func.clock_timestamp(), revoked_reason="logout")
                .returning(RefreshToken.user_id)
            )
            user_id = revoked.first()
            if user_id is not None:
                audit.record(session, "auth.logout", actor_id=user_id, target_type="user", target_id=user_id, ip=client_ip(request))
    response = Response(status_code=204)
    response.headers.append("set-cookie", _cookie_header(settings, None))
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return user_out(user)


# ---------- two-step sign-in ----------


@router.post("/mfa/setup", response_model=MfaSetupOut)
async def mfa_setup(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> MfaSetupOut:
    secret = new_secret()
    async with session.begin():
        locked = await _lock_user(session, user.id)
        assert locked is not None
        if locked.mfa_enabled:
            raise ApiError(409, "mfa_already_enabled", "Two-step sign-in is already on.")
        locked.mfa_pending_secret_enc = _box(settings).seal(secret)
    uri = provisioning_uri(secret, user.email)
    return MfaSetupOut(secret=secret, otpauth_uri=uri, qr_svg=qr_svg(uri))


@router.post("/mfa/enable", response_model=RecoveryCodesOut)
async def mfa_enable(body: CodeIn, request: Request, user: CurrentUser, session: SessionDep, settings: SettingsDep, limiter: LimiterDep) -> RecoveryCodesOut:
    limiter.check(f"mfa-enable:{user.id}", 10, 60)
    codes = new_recovery_codes()
    key = recovery_key(settings.jwt_secret.get_secret_value())
    async with session.begin():
        locked = await _lock_user(session, user.id)
        assert locked is not None
        if locked.mfa_enabled:
            raise ApiError(409, "mfa_already_enabled", "Two-step sign-in is already on.")
        if locked.mfa_pending_secret_enc is None:
            raise ApiError(409, "no_pending_setup", "Start the setup again.")
        step = match_step(_box(settings).open(locked.mfa_pending_secret_enc), body.code)
        if step is None:
            raise ApiError(400, "invalid_code", "That code is not right. Check the time on your phone and try again.")
        locked.mfa_secret_enc = locked.mfa_pending_secret_enc
        locked.mfa_pending_secret_enc = None
        locked.mfa_enabled = True
        locked.mfa_last_step = step
        await session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == locked.id))
        session.add_all([RecoveryCode(user_id=locked.id, code_hash=hash_recovery_code(c, key)) for c in codes])
        audit.record(session, "auth.mfa_enabled", actor_id=locked.id, target_type="user", target_id=locked.id, ip=client_ip(request))
    return RecoveryCodesOut(recovery_codes=codes)


# ---------- password reset ----------


@router.post("/password/forgot", status_code=202)
async def forgot_password(body: EmailIn, request: Request, session: SessionDep, settings: SettingsDep, limiter: LimiterDep) -> dict:
    email = _normalize_email(str(body.email))
    limiter.check(f"forgot-ip:{client_ip(request)}", 10, 3600)
    limiter.check(f"forgot:{email}", 3, 3600)
    async with session.begin():
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None:
            raw = await _new_email_token(session, user, TokenPurpose.RESET_PASSWORD, RESET_TTL, await db_now(session))
            link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw}"
            queue_email(
                session,
                to=email,
                subject="Reset your Adal password",
                body=f"Choose a new password here:\n\n{link}\n\nThe link works for one hour. If you did not ask for this, ignore this email.\n",
            )
            audit.record(session, "auth.reset_requested", actor_id=user.id, target_type="user", target_id=user.id, ip=client_ip(request))
    return {}


@router.post("/password/reset", status_code=204)
async def reset_password(body: ResetPasswordIn, request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    password_hash: str | None = None
    async with session.begin():
        token = await _consume_email_token(session, body.token, TokenPurpose.RESET_PASSWORD)
        user = await _lock_user(session, token.user_id)
        assert user is not None
        problem = password_problem(body.password, user.email)
        if problem:
            raise ApiError(422, "weak_password", problem, {"fields": {"password": problem}})
        password_hash = await hash_password(body.password)
        user.password_hash = password_hash
        user.failed_logins = 0
        user.locked_until = None
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=token.used_at, revoked_reason="reset")
        )
        audit.record(session, "auth.password_reset", actor_id=user.id, target_type="user", target_id=user.id, ip=client_ip(request))
    response = Response(status_code=204)
    response.headers.append("set-cookie", _cookie_header(settings, None))
    return response


__all__ = ["router", "REFRESH_COOKIE", "Role"]
