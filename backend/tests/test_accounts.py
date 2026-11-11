"""Sign-up, verification, sign-in with TOTP, lockout and sessions (FR-1 to FR-6, UC-1)."""

import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.models import RefreshToken
from app.security.totp import code_for_step, current_step
from tests.conftest import PASSWORD

pytestmark = pytest.mark.anyio


async def latest_link(client: AsyncClient, app, email: str, path: str) -> str:  # type: ignore[no-untyped-def]
    async with app.state.sessionmaker() as session:
        body = (await session.execute(text("SELECT body FROM email_outbox WHERE to_address = :e ORDER BY id DESC LIMIT 1"), {"e": email})).scalar_one()
    match = re.search(rf"{path}\?token=([\w-]+)", body)
    assert match, body
    return match.group(1)


async def test_register_verify_login_and_me(client: AsyncClient, app) -> None:  # type: ignore[no-untyped-def]
    email = "Newcomer@Example.com"
    created = await client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "role": "buyer"})
    assert created.status_code == 201, created.text
    assert created.json()["user"] == created.json()["user"] | {"email": "newcomer@example.com", "email_verified": False, "mfa_enabled": False}

    again = await client.post("/api/auth/register", json={"email": "newcomer@example.com", "password": PASSWORD, "role": "buyer"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "email_taken"

    token = await latest_link(client, app, "newcomer@example.com", "/verify-email")
    assert (await client.post("/api/auth/verify-email", json={"token": token})).json() == {"verified": True}
    reused = await client.post("/api/auth/verify-email", json={"token": token})
    assert reused.status_code == 400 and reused.json()["error"]["code"] == "invalid_token"

    login = await client.post("/api/auth/login", json={"email": "NEWCOMER@example.com", "password": PASSWORD})
    assert login.status_code == 200 and login.json()["status"] == "ok"
    assert "adal_refresh" in login.headers["set-cookie"] and "HttpOnly" in login.headers["set-cookie"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["email_verified"] is True


async def test_weak_password_and_unknown_fields_are_refused(client: AsyncClient) -> None:
    short = await client.post("/api/auth/register", json={"email": "a@example.com", "password": "short", "role": "buyer"})
    assert short.status_code == 422 and short.json()["error"]["code"] == "weak_password"
    admin = await client.post("/api/auth/register", json={"email": "b@example.com", "password": PASSWORD, "role": "admin"})
    assert admin.status_code == 422  # nobody signs up as an administrator
    extra = await client.post("/api/auth/register", json={"email": "c@example.com", "password": PASSWORD, "role": "buyer", "mfa_enabled": True})
    assert extra.status_code == 422  # unknown fields are rejected, not silently bound


async def test_mfa_setup_then_login_needs_a_fresh_code(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    buyer = await accounts("buyer", mfa=False)
    setup = await client.post("/api/auth/mfa/setup", headers=buyer.headers)
    assert setup.status_code == 200 and setup.json()["qr_svg"].lstrip().startswith("<svg")
    secret = setup.json()["secret"]
    wrong = await client.post("/api/auth/mfa/enable", headers=buyer.headers, json={"code": "000000"})
    assert wrong.status_code == 400
    enabled = await client.post("/api/auth/mfa/enable", headers=buyer.headers, json={"code": code_for_step(secret, current_step())})
    assert enabled.status_code == 200 and len(enabled.json()["recovery_codes"]) == 10
    recovery = enabled.json()["recovery_codes"][0]

    first = await client.post("/api/auth/login", json={"email": buyer.email, "password": PASSWORD})
    assert first.json()["status"] == "mfa_required"
    # The code used to enable MFA is spent: replaying it fails.
    replay = await client.post("/api/auth/login/mfa", json={"mfa_ticket": first.json()["mfa_ticket"], "code": code_for_step(secret, current_step())})
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "invalid_code"
    fresh = await client.post("/api/auth/login/mfa", json={"mfa_ticket": first.json()["mfa_ticket"], "code": code_for_step(secret, current_step() + 1)})
    assert fresh.status_code == 200 and fresh.json()["status"] == "ok"

    second = await client.post("/api/auth/login", json={"email": buyer.email, "password": PASSWORD})
    by_recovery = await client.post("/api/auth/login/mfa", json={"mfa_ticket": second.json()["mfa_ticket"], "code": recovery})
    assert by_recovery.status_code == 200
    third = await client.post("/api/auth/login", json={"email": buyer.email, "password": PASSWORD})
    used_twice = await client.post("/api/auth/login/mfa", json={"mfa_ticket": third.json()["mfa_ticket"], "code": recovery})
    assert used_twice.status_code == 401  # a recovery code works once


async def test_five_wrong_passwords_lock_the_account(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    buyer = await accounts("buyer", mfa=False)
    codes = []
    for _ in range(5):
        response = await client.post("/api/auth/login", json={"email": buyer.email, "password": "not the password"})
        codes.append(response.json()["error"]["code"])
    assert codes == ["invalid_credentials"] * 4 + ["account_locked"]
    right = await client.post("/api/auth/login", json={"email": buyer.email, "password": PASSWORD})
    assert right.status_code == 423  # even the right password waits out the lock


async def test_unknown_email_looks_like_a_wrong_password(client: AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_credentials"
    resend = await client.post("/api/auth/resend-verification", json={"email": "nobody@example.com"})
    assert resend.status_code == 202


async def test_refresh_rotates_and_a_stolen_old_token_ends_every_session(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    buyer = await accounts("buyer", mfa=False)
    login = await client.post("/api/auth/login", json={"email": buyer.email, "password": PASSWORD})
    old_cookie = client.cookies.get("adal_refresh")
    rotated = await client.post("/api/auth/refresh")
    assert rotated.status_code == 200 and client.cookies.get("adal_refresh") != old_cookie
    assert login.json()["access_token"] != rotated.json()["access_token"]

    # The old token comes back later than the grace period: treat it as theft.
    async with app.state.sessionmaker() as session, session.begin():
        await session.execute(
            text("UPDATE refresh_tokens SET revoked_at = revoked_at - interval '5 minutes' WHERE user_id = :u AND revoked_reason = 'rotated'"),
            {"u": buyer.id},
        )
    client.cookies.set("adal_refresh", old_cookie)
    stolen = await client.post("/api/auth/refresh")
    assert stolen.status_code == 401
    async with app.state.sessionmaker() as session:
        live = (await session.scalars(select(RefreshToken).where(RefreshToken.user_id == buyer.id, RefreshToken.revoked_at.is_(None)))).all()
    assert live == []


async def test_bad_tokens_are_refused(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_token"
    assert (await client.get("/api/auth/me")).json()["error"]["code"] == "not_authenticated"
