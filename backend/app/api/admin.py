import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.permissions import require_permission, ROLE_PERMISSIONS
from app.models.user import User
from app.models.sync_log import SyncLog
from app.schemas.user import UserResponse, UserRoleUpdate
from app.services.audit import record_admin_audit
from app.services.tmdb_sync import sync_movies_from_tmdb

logger = logging.getLogger("streambit.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:read")),
):
    """Lectura de usuarios: permitido para Administrador principal y Analista."""
    stmt = select(User).order_by(User.id.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_in: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_permission("users:manage_roles")),
):
    """Cambio de roles: exclusivo del Administrador principal, con registro en logs."""
    if user_id == current_admin.id and role_in.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes quitarte tu propio rol de administrador.",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    old_role = target_user.role
    target_user.role = role_in.role
    await record_admin_audit(
        db=db,
        actor_user_id=current_admin.id,
        action="user_role_updated",
        resource_type="user",
        resource_id=str(target_user.id),
        details={"old_role": old_role, "new_role": target_user.role},
        commit=False,
    )
    await db.commit()
    await db.refresh(target_user)

    logger.info(
        "EVENT=ROLE_UPDATED admin_id=%s target_user_id=%s old_role=%s new_role=%s",
        current_admin.id,
        target_user.id,
        old_role,
        target_user.role,
    )
    return target_user


@router.get("/permissions/me", status_code=status.HTTP_200_OK)
async def read_my_admin_permissions(
    current_user: User = Depends(require_permission("admin:read")),
):
    """Consulta de permisos efectivos del rol administrativo actual."""
    return {
        "user": current_user.username,
        "role": current_user.role,
        "permissions": sorted(ROLE_PERMISSIONS.get(current_user.role, set())),
    }


@router.get("/analytics/summary", status_code=status.HTTP_200_OK)
async def analytics_summary(
    current_user: User = Depends(require_permission("analytics:read")),
):
    """Endpoint de solo lectura para Analista y Administrador principal."""
    return {
        "message": "Acceso de lectura autorizado a métricas y analítica.",
        "role": current_user.role,
    }


@router.post("/sync/movies", status_code=status.HTTP_200_OK)
async def trigger_manual_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    """Ejecución manual de sincronización de metadatos (Admin y Gestor de catálogo)."""
    log = await sync_movies_from_tmdb(db, trigger="manual")
    return {
        "id": log.id,
        "provider": log.provider,
        "trigger": log.trigger,
        "status": log.status,
        "created_count": log.created_count,
        "updated_count": log.updated_count,
        "error_message": log.error_message,
        "executed_at": log.executed_at,
    }


@router.get("/sync/logs", status_code=status.HTTP_200_OK)
async def list_sync_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("admin:read")),
):
    """Historial de ejecuciones de sincronización (solo lectura)."""
    stmt = select(SyncLog).order_by(SyncLog.executed_at.desc()).limit(20)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "provider": l.provider,
            "trigger": l.trigger,
            "status": l.status,
            "created_count": l.created_count,
            "updated_count": l.updated_count,
            "error_message": l.error_message,
            "executed_at": l.executed_at,
        }
        for l in logs
    ]