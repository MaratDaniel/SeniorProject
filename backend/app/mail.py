"""Queue outgoing email in the same transaction as the event that caused it."""

from datetime import datetime, timedelta
from html import escape
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailOutbox, TokenPurpose

LOCAL_TEMPLATE_PREFIX = "local:"


def render_account_email(body: str, link: str, purpose: TokenPurpose) -> str:
    """Render the app's plain-text copy as HTML with a labeled account link."""
    action = "Confirm your email" if purpose == TokenPurpose.VERIFY_EMAIL else "Reset your password"
    paragraphs = []
    for paragraph in body.strip().split("\n\n"):
        if paragraph == link:
            content = f'<a href="{escape(link)}" style="color:#226143;font-weight:bold">{action}</a>'
        else:
            content = escape(paragraph).replace("\n", "<br>")
        paragraphs.append(f'<p style="font-size:16px;line-height:24px;color:#19251c">{content}</p>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        '<body style="font-family:Arial,Helvetica,sans-serif">'
        f'<h1 style="font-size:24px;line-height:32px;color:#19251c">{action}</h1>'
        f'{"".join(paragraphs)}</body></html>'
    )


def queue_email(
    session: AsyncSession,
    *,
    to: str,
    subject: str,
    body: str,
    now: datetime,
    ttl: timedelta = timedelta(hours=24),
    purpose: TokenPurpose | None = None,
    link: str | None = None,
) -> None:
    """Queue a plain-text notification or an account message with a local HTML template."""
    session.add(
        EmailOutbox(
            to_address=to,
            subject=subject,
            body=body,
            template=f"{LOCAL_TEMPLATE_PREFIX}{purpose.value}" if purpose is not None else None,
            template_link=link,
            expires_at=now + min(ttl, timedelta(hours=24)),  # Resend keeps delivery keys for 24 hours
            delivery_key=uuid4().hex,
            next_attempt_at=now,
        )
    )


def queue_account_email(
    session: AsyncSession,
    *,
    to: str,
    subject: str,
    body: str,
    purpose: TokenPurpose,
    link: str,
    now: datetime,
    ttl: timedelta,
) -> None:
    """Keep the same plain-text copy for the dev mailbox and for delivery."""
    queue_email(session, to=to, subject=subject, body=body, now=now, ttl=ttl, purpose=purpose, link=link)
