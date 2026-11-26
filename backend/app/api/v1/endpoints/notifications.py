from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.movie import Movie
from app.models.notifications import MovieAvailabilityAlert, Notification
from app.models.user import User
from app.schemas.notifications import (
    AvailabilityAlertResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    NotificationResponse,
)

router = APIRouter(prefix="/me", tags=["Notifications"])


@router.put(
    "/availability-alerts/{movie_id}",
    response_model=AvailabilityAlertResponse,
    status_code=status.HTTP_200_OK,
    summary="Activar aviso de disponibilidad para una película (idempotente)",
)
async def subscribe_availability_alert(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie_exists = (
        await db.execute(select(Movie.id).where(Movie.id == movie_id))
    ).scalar_one_or_none()
    if not movie_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    existing = (
        await db.execute(
            select(MovieAvailabilityAlert).where(
                MovieAvailabilityAlert.user_id == current_user.id,
                MovieAvailabilityAlert.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    alert = MovieAvailabilityAlert(user_id=current_user.id, movie_id=movie_id)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete(
    "/availability-alerts/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar aviso de disponibilidad para una película (idempotente)",
)
async def unsubscribe_availability_alert(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(MovieAvailabilityAlert).where(
            MovieAvailabilityAlert.user_id == current_user.id,
            MovieAvailabilityAlert.movie_id == movie_id,
        )
    )
    await db.commit()
    return None


@router.get(
    "/availability-alerts",
    response_model=list[AvailabilityAlertResponse],
    summary="Listar avisos de disponibilidad activos del usuario",
)
async def list_availability_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MovieAvailabilityAlert)
        .where(MovieAvailabilityAlert.user_id == current_user.id)
        .order_by(desc(MovieAvailabilityAlert.created_at))
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="Consultar bandeja de notificaciones del usuario",
)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    only_unread: bool = Query(default=False),
    notif_type: Optional[Literal["movie_available", "comment_reply"]] = Query(
        default=None, alias="type"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [Notification.user_id == current_user.id]
    if only_unread:
        filters.append(Notification.is_read.is_(False))
    if notif_type is not None:
        filters.append(Notification.type == notif_type)

    total = (
        await db.execute(select(func.count(Notification.id)).where(*filters))
    ).scalar_one()

    unread_count = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False),
            )
        )
    ).scalar_one()

    stmt = (
        select(Notification)
        .where(*filters)
        .order_by(desc(Notification.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())

    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/notifications/read-all",
    summary="Marcar todas las notificaciones no leídas como leídas",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    await db.commit()
    return {"updated": result.rowcount or 0}


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Marcar una notificación propia como leída",
)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada.",
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notification)

    return notification


@router.get(
    "/notifications/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Consultar preferencias de notificación del usuario",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch(
    "/notifications/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Actualizar preferencias de notificación del usuario",
)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.notify_availability is not None:
        current_user.notify_availability = payload.notify_availability
    if payload.notify_comment_replies is not None:
        current_user.notify_comment_replies = payload.notify_comment_replies

    await db.commit()
    await db.refresh(current_user)
    return current_user
