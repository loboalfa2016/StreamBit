from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AdminAuditLog


async def record_admin_audit(
    db: AsyncSession,
    actor_user_id: int,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    commit: bool = True,
) -> AdminAuditLog:
    entry = AdminAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.add(entry)
    if commit:
        await db.commit()
        await db.refresh(entry)
    return entry
