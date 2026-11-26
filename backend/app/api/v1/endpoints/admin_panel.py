from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.audit_log import AdminAuditLog
from app.models.movie import Movie
from app.models.notifications import Notification
from app.models.user import User
from app.schemas.admin_panel import (
    AdminAuditLogListResponse,
    AdminBroadcastNotificationRequest,
    AdminMovieListItem,
    AdminMovieListResponse,
    AdminMovieUpdateRequest,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserStatusUpdateRequest,
)
from app.services.audit import record_admin_audit

router = APIRouter(prefix="/admin", tags=["Admin Panel"])


@router.get(
    "/movies",
    response_model=AdminMovieListResponse,
    summary="Listado administrativo de películas con búsqueda, filtros y paginación",
)
async def admin_list_movies(
    q: Optional[str] = Query(default=None, max_length=200),
    is_published: Optional[bool] = Query(default=None),
    is_available: Optional[bool] = Query(default=None),
    is_featured: Optional[bool] = Query(default=None),
    is_indie: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("view_catalog_admin")),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Movie.title.ilike(pattern), Movie.director.ilike(pattern)))
    if is_published is not None:
        filters.append(Movie.is_published.is_(is_published))
    if is_available is not None:
        filters.append(Movie.is_available.is_(is_available))
    if is_featured is not None:
        filters.append(Movie.is_featured.is_(is_featured))
    if is_indie is not None:
        filters.append(Movie.is_indie.is_(is_indie))

    total = (
        await db.execute(select(func.count(Movie.id)).where(*filters))
    ).scalar_one()

    stmt = (
        select(Movie)
        .where(*filters)
        .order_by(desc(Movie.created_at), desc(Movie.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return AdminMovieListResponse(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/movies/{movie_id}",
    response_model=AdminMovieListItem,
    summary="Actualizar estado operativo de una película en catálogo",
)
async def admin_update_movie(
    movie_id: int,
    payload: AdminMovieUpdateRequest,
    actor: User = Depends(require_permission("manage_catalog")),
    db: AsyncSession = Depends(get_db),
):
    movie = (
        await db.execute(select(Movie).where(Movie.id == movie_id))
    ).scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    updates = payload.model_dump(exclude_unset=True)
    changes: dict = {}
    for field, new_val in updates.items():
        old_val = getattr(movie, field)
        if old_val != new_val:
            changes[field] = {"old": old_val, "new": new_val}
        setattr(movie, field, new_val)

    await record_admin_audit(
        db=db,
        actor_user_id=actor.id,
        action="movie_admin_updated",
        resource_type="movie",
        resource_id=str(movie.id),
        details=changes,
        commit=False,
    )
    await db.commit()
    await db.refresh(movie)
    return movie


@router.get(
    "/users/search",
    response_model=AdminUserListResponse,
    summary="Buscar y filtrar usuarios en el panel administrativo",
)
async def admin_search_users(
    q: Optional[str] = Query(default=None, max_length=200),
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("view_users")),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.username.ilike(pattern), User.email.ilike(pattern)))
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    total = (
        await db.execute(select(func.count(User.id)).where(*filters))
    ).scalar_one()

    stmt = (
        select(User)
        .where(*filters)
        .order_by(User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return AdminUserListResponse(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserListItem,
    summary="Activar o desactivar una cuenta de usuario",
)
async def admin_update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    actor: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == actor.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta de administrador.",
        )

    target_user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    old_status = target_user.is_active
    target_user.is_active = payload.is_active

    await record_admin_audit(
        db=db,
        actor_user_id=actor.id,
        action="user_status_updated",
        resource_type="user",
        resource_id=str(target_user.id),
        details={"old_is_active": old_status, "new_is_active": payload.is_active},
        commit=False,
    )
    await db.commit()
    await db.refresh(target_user)
    return target_user


@router.post(
    "/notifications/broadcast",
    status_code=status.HTTP_201_CREATED,
    summary="Enviar notificación administrativa a usuarios seleccionados o activos",
)
async def admin_broadcast_notification(
    payload: AdminBroadcastNotificationRequest,
    actor: User = Depends(require_permission("manage_notifications")),
    db: AsyncSession = Depends(get_db),
):
    if payload.movie_id is not None:
        movie_exists = (
            await db.execute(select(Movie.id).where(Movie.id == payload.movie_id))
        ).scalar_one_or_none()
        if not movie_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Película no encontrada.",
            )

    user_filters = [User.is_active.is_(True)]
    if payload.target_user_ids is not None:
        user_filters.append(User.id.in_(payload.target_user_ids))

    recipient_ids = list(
        (await db.execute(select(User.id).where(*user_filters))).scalars().all()
    )

    notifications = [
        Notification(
            user_id=uid,
            type="admin_announcement",
            title=payload.title.strip(),
            message=payload.message.strip(),
            movie_id=payload.movie_id,
        )
        for uid in recipient_ids
    ]
    db.add_all(notifications)

    await record_admin_audit(
        db=db,
        actor_user_id=actor.id,
        action="admin_notification_sent",
        resource_type="notification",
        resource_id=str(payload.movie_id) if payload.movie_id else None,
        details={
            "title": payload.title.strip(),
            "recipients_count": len(recipient_ids),
            "targeted": payload.target_user_ids is not None,
        },
        commit=False,
    )
    await db.commit()
    return {"sent_count": len(recipient_ids)}


@router.get(
    "/audit-logs",
    response_model=AdminAuditLogListResponse,
    summary="Consultar bitácora de auditoría administrativa",
)
async def admin_list_audit_logs(
    action: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    actor_user_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("view_audit_logs")),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if action:
        filters.append(AdminAuditLog.action == action)
    if resource_type:
        filters.append(AdminAuditLog.resource_type == resource_type)
    if actor_user_id is not None:
        filters.append(AdminAuditLog.actor_user_id == actor_user_id)

    total = (
        await db.execute(select(func.count(AdminAuditLog.id)).where(*filters))
    ).scalar_one()

    stmt = (
        select(AdminAuditLog)
        .where(*filters)
        .order_by(desc(AdminAuditLog.created_at), desc(AdminAuditLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return AdminAuditLogListResponse(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
    )
