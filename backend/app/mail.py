"""Outgoing email goes to an outbox table in the same transaction as its cause.

No mail is delivered in this version: in development the messages are read at
GET /api/dev/outbox. A delivery worker can later send rows where sent_at is null.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailOutbox

logger = logging.getLogger("adal.mail")


def queue_email(session: AsyncSession, *, to: str, subject: str, body: str) -> None:
    session.add(EmailOutbox(to_address=to, subject=subject, body=body))
    logger.info("email queued: %s", subject)  # never log the body: it can carry one-time links
