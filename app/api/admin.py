import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.permissions import require_roles
from app.models.user import User
from app.schemas.user import UserResponse, UserRoleUpdate

logger = logging.getLogger("streambit.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
):
    stmt = select(User).order_by(User.id.asc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_in: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
):
    if user_id == current_admin.id and role_in.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes quitarte tu propio rol de administrador."
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    old_role = target_user.role
    target_user.role = role_in.role
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


@router.get("/moderation-check", status_code=status.HTTP_200_OK)
async def moderation_area(
    current_staff: User = Depends(require_roles("admin", "moderator")),
):
    return {
        "message": "Acceso autorizado al área de moderación.",
        "user": current_staff.username,
        "role": current_staff.role,
    }