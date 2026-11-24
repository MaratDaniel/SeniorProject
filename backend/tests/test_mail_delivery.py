"""The worker delivers account and marketplace messages from the committed outbox."""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import func, select, update

from app.mail_worker import MailSettings, deliver_one
from app.main import create_app
from app.models import EmailOutbox, Transaction
from tests.conftest import PASSWORD, make_auction, move_end
from tests.test_close_and_checkout import DELIVERY, scheduler, sold_auction

pytestmark = pytest.mark.anyio


async def test_account_templates_and_retries(client, app, settings, monkeypatch) -> None:
    recipient = "resend-owner@example.com"
    other_recipient = "resend-other@example.com"
    mail = MailSettings(database_url=settings.database_url, resend_api_key="test-key", mail_test_recipient=recipient)
    sessionmaker = app.state.sessionmaker
    calls = []

    async def send(params, options):
        calls.append((params, options))
        if len(calls) == 1:
            raise httpx.ReadTimeout("simulated timeout")
        return {"id": f"email-{len(calls)}"}

    monkeypatch.setattr("app.mail_worker.resend.Emails.send_async", send)
    for email in (other_recipient, recipient):
        response = await client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "role": "buyer"})
        assert response.status_code == 201

    assert await deliver_one(sessionmaker, mail)
    assert not await deliver_one(sessionmaker, mail)

    async with sessionmaker() as session, session.begin():
        await session.execute(update(EmailOutbox).where(EmailOutbox.to_address == recipient).values(next_attempt_at=func.now()))
    assert await deliver_one(sessionmaker, mail)
    assert calls[0] == calls[1]
    assert calls[1][0]["to"] == [recipient]
    verification = calls[1][0]
    assert "template" not in verification
    assert verification["subject"] == "Confirm your email for Adal"
    verify_link = next(line for line in verification["text"].splitlines() if "/verify-email?token=" in line)
    assert f'href="{verify_link}"' in verification["html"]
    verify_url = urlsplit(verify_link)
    assert verify_url.path == "/verify-email"
    verification_token = parse_qs(verify_url.query)["token"][0]
    assert (await client.post("/api/auth/verify-email", json={"token": verification_token})).json() == {"verified": True}

    assert (await client.post("/api/auth/password/forgot", json={"email": recipient})).status_code == 202
    assert await deliver_one(sessionmaker, mail)
    assert calls[2][1] != calls[1][1]
    reset = calls[2][0]
    assert "template" not in reset
    assert reset["subject"] == "Reset your Adal password"
    reset_link = next(line for line in reset["text"].splitlines() if "/reset-password?token=" in line)
    assert f'href="{reset_link}"' in reset["html"]
    reset_url = urlsplit(reset_link)
    assert reset_url.path == "/reset-password"
    reset_token = parse_qs(reset_url.query)["token"][0]
    assert (await client.post("/api/auth/password/reset", json={"token": reset_token, "password": "a new example password"})).status_code == 204

    async with sessionmaker() as session:
        sent = list(await session.scalars(select(EmailOutbox).where(EmailOutbox.to_address == recipient).order_by(EmailOutbox.id)))
        assert [(row.provider_id, row.attempts) for row in sent] == [("email-2", 2), ("email-3", 1)]
        assert all(row.sent_at is not None for row in sent)
    assert not await deliver_one(sessionmaker, mail)


async def test_unrestricted_delivery_sends_account_and_marketplace_email(client, app, accounts, settings, monkeypatch) -> None:
    buyer, seller = await accounts("buyer"), await accounts("seller")
    newcomer = "resend-newcomer@example.com"
    mail = MailSettings(
        database_url=settings.database_url,
        resend_api_key="test-key",
        mail_from="Adal <accounts@notify.example.com>",
    )
    sessionmaker = app.state.sessionmaker
    calls = []

    async def send(params, options):
        calls.append(params)
        return {"id": f"marketplace-email-{len(calls)}"}

    monkeypatch.setattr("app.mail_worker.resend.Emails.send_async", send)
    registered = await client.post("/api/auth/register", json={"email": newcomer, "password": PASSWORD, "role": "buyer"})
    assert registered.status_code == 201
    auction_id = await sold_auction(app, seller, buyer)
    async with sessionmaker() as session:
        tx_id = await session.scalar(select(Transaction.id).where(Transaction.auction_id == auction_id))
    complete = await client.post(
        f"/api/transactions/{tx_id}/confirm", headers=buyer.headers, json={"code": buyer.code(), "delivery": DELIVERY}
    )
    assert complete.status_code == 200
    unsold = await make_auction(app, seller)
    await move_end(app, unsold, -1)
    assert unsold in await scheduler(app).close_due()

    while await deliver_one(sessionmaker, mail):
        pass
    assert [item["subject"] for item in calls if item["to"] == [newcomer]] == ["Confirm your email for Adal"]
    buyer_mail = {item["subject"]: item["text"] for item in calls if item["to"] == [buyer.email]}
    assert set(buyer_mail) == {"You won: Brass balance", "Purchase complete: Brass balance"}
    assert f"/checkout/{tx_id}" in buyer_mail["You won: Brass balance"]
    assert {item["subject"] for item in calls if item["to"] == [seller.email]} == {
        "Sold: Brass balance", "Ready to deliver: Brass balance", "No sale: Brass balance",
    }

    configured_app = create_app(settings.model_copy(update={"env": "dev", "mail_from": mail.mail_from}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=configured_app), base_url="http://test") as dev_client:
        assert (await dev_client.get("/api/dev/outbox")).status_code == 404

    test_settings = settings.model_copy(update={"env": "dev", "mail_from": "Adal <onboarding@resend.dev>"})
    assert test_settings.dev_mailbox_enabled
