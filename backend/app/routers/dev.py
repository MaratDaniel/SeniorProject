"""Development-only helpers. This router is not mounted unless ADAL_ENV=dev."""

import re

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import SessionDep
from app.models import EmailOutbox
from app.schemas import OutboxOut

router = APIRouter(prefix="/api/dev", tags=["development"])
LINK = re.compile(r"https?://[^\s\"'<>]+")


@router.get("/outbox", response_model=list[OutboxOut])
async def outbox(session: SessionDep) -> list[OutboxOut]:
    rows = await session.scalars(select(EmailOutbox).order_by(EmailOutbox.id.desc()).limit(100))
    return [
        OutboxOut(id=r.id, to=r.to_address, subject=r.subject, body=r.body, links=LINK.findall(r.body), created_at=r.created_at)
        for r in rows
    ]
