"""Deliver queued account and marketplace emails through Resend."""

import asyncio
import logging
from datetime import timedelta
from email.utils import parseaddr

import httpx
import resend
from pydantic import EmailStr, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from resend.exceptions import ResendError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import db_now, make_engine, make_sessionmaker
from app.mail import LOCAL_TEMPLATE_PREFIX, render_account_email
from app.models import EmailOutbox, TokenPurpose

logger = logging.getLogger("adal.mail_worker")
MAX_ATTEMPTS = 6


class MailSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADAL_", env_file=".env", env_ignore_empty=True, extra="ignore", hide_input_in_errors=True
    )

    database_url: str
    resend_api_key: SecretStr
    mail_from: str = "Adal <onboarding@resend.dev>"
    mail_test_recipient: EmailStr | None = None
    # Previously queued hosted-template messages retain their original request on retry.
    resend_verify_template: str = "adal-verify-email"
    resend_reset_template: str = "adal-reset-password"

    @model_validator(mode="after")
    def _validate_test_sender(self) -> "MailSettings":
        sender_domain = parseaddr(self.mail_from)[1].rpartition("@")[2].lower()
        if sender_domain == "resend.dev" and self.mail_test_recipient is None:
            raise ValueError("Set ADAL_MAIL_TEST_RECIPIENT to your Resend account email when using the test sender.")
        return self


async def deliver_one(sessionmaker: async_sessionmaker[AsyncSession], settings: MailSettings) -> bool:
    legacy_templates = {
        TokenPurpose.VERIFY_EMAIL: settings.resend_verify_template,
        TokenPurpose.RESET_PASSWORD: settings.resend_reset_template,
    }
    async with sessionmaker() as session, session.begin():
        query = select(EmailOutbox).where(
            EmailOutbox.delivery_key.is_not(None),
            EmailOutbox.sent_at.is_(None),
            EmailOutbox.failed_at.is_(None),
            EmailOutbox.next_attempt_at <= func.clock_timestamp(),
        )
        if settings.mail_test_recipient is not None:
            query = query.where(EmailOutbox.to_address == settings.mail_test_recipient.lower())
        message = await session.scalar(
            query.order_by(EmailOutbox.next_attempt_at, EmailOutbox.id).limit(1).with_for_update(skip_locked=True)
        )
        if message is None:
            return False

        now = await db_now(session)
        if message.expires_at is None or message.expires_at <= now:
            message.failed_at = now
            logger.info("email expired before delivery; outbox_id=%s", message.id)
            return True

        params: resend.Emails.SendParams = {"from": settings.mail_from, "to": [message.to_address]}
        if message.template is None:
            params.update(subject=message.subject, text=message.body)
        elif message.template.startswith(LOCAL_TEMPLATE_PREFIX):
            assert message.template_link is not None
            purpose = TokenPurpose(message.template.removeprefix(LOCAL_TEMPLATE_PREFIX))
            params.update(subject=message.subject, text=message.body, html=render_account_email(message.body, message.template_link, purpose))
        else:
            assert message.template_link is not None
            params["template"] = {"id": legacy_templates[message.template], "variables": {"ACTION_URL": message.template_link}}

        message.attempts += 1
        retry_after = 0
        try:
            response = await resend.Emails.send_async(
                params,
                {"idempotency_key": f"adal-account/{message.delivery_key}"},
            )
        except ResendError as exc:
            code = str(exc.code)
            retryable = code == "429" or (code.isdecimal() and 500 <= int(code) < 600)
            header = next((value for key, value in exc.headers.items() if key.lower() == "retry-after"), "0")
            retry_after = int(header) if header.isdecimal() else 0
            logger.warning("Resend rejected email; outbox_id=%s status=%s", message.id, code)
        except (httpx.TransportError, TimeoutError):
            retryable = True
            logger.warning("Resend request did not complete; outbox_id=%s", message.id)
        else:
            message.provider_id = response["id"]
            message.sent_at = await db_now(session)
            logger.info("Resend accepted email; outbox_id=%s provider_id=%s", message.id, message.provider_id)
            return True

        next_attempt = await db_now(session) + timedelta(seconds=max(15 * 2 ** (message.attempts - 1), retry_after))
        if retryable and message.attempts < MAX_ATTEMPTS and next_attempt < message.expires_at:
            message.next_attempt_at = next_attempt
        else:
            message.failed_at = await db_now(session)
        return True


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = MailSettings()
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    resend.api_key = settings.resend_api_key.get_secret_value()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resend.default_async_http_client = resend.HTTPXClient(client=client)
            while True:
                try:
                    if await deliver_one(sessionmaker, settings):
                        continue
                except SQLAlchemyError as exc:
                    logger.warning("outbox database operation failed; error=%s", type(exc).__name__)
                await asyncio.sleep(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
