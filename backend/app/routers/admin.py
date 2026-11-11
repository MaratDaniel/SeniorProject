"""Administrator views. The full dashboard is spring 2027; the MVP exposes the audit log."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.deps import AdminUser, SessionDep
from app.models import AuditLog
from app.schemas import AuditOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit", response_model=list[AuditOut])
async def audit_log(_: AdminUser, session: SessionDep, limit: int = Query(default=100, ge=1, le=1000)) -> list[AuditOut]:
    rows = await session.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
    return [
        AuditOut(id=r.id, at=r.at, actor_id=r.actor_id, action=r.action, target_type=r.target_type, target_id=r.target_id, data=r.data)
        for r in rows
    ]
