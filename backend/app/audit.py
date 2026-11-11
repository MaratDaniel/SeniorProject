"""Audit log writes (FR-38). Entries go into the same transaction as the action they describe."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def record(
    session: AsyncSession,
    action: str,
    *,
    actor_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    ip: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            action=action,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            data=data or {},
        )
    )
