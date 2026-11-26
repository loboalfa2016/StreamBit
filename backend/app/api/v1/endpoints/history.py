from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.movie import Movie
from app.models.source import Source
from app.models.user import User
from app.models.watch_history import WatchHistory
from app.schemas.history import (
    PlaybackEventCreate,
    WatchHistoryItemResponse,
    WatchHistoryListResponse,
)

router = APIRouter(prefix="/me/history", tags=["History"])


@router.post(
    "/events",
    response_model=WatchHistoryItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Registrar evento de reproducción en el historial del usuario",
)
async def record_playback_event(
    payload: PlaybackEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie = (
        await db.execute(select(Movie).where(Movie.id == payload.movie_id))
    ).scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    if payload.source_id is not None:
        source = (
            await db.execute(select(Source).where(Source.id == payload.source_id))
        ).scalar_one_or_none()
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fuente de reproducción no encontrada.",
            )
        if source.movie_id != payload.movie_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fuente de reproducción no pertenece a la película indicada.",
            )

    # Regla de negocio: solo se marca completado si el evento es completed_verified
    # y cuenta con verificación explícita del proveedor. De lo contrario, se normaliza a "progress".
    verified_completion = payload.event == "completed_verified" and payload.provider_verified
    effective_event = (
        "progress"
        if payload.event == "completed_verified" and not payload.provider_verified
        else payload.event
    )

    now = datetime.now(timezone.utc)

    existing = (
        await db.execute(
            select(WatchHistory)
            .options(selectinload(WatchHistory.movie))
            .where(
                WatchHistory.user_id == current_user.id,
                WatchHistory.movie_id == payload.movie_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.last_event = effective_event
        if payload.source_id is not None:
            existing.source_id = payload.source_id
        if payload.position_seconds is not None:
            existing.position_seconds = payload.position_seconds
        if payload.duration_seconds is not None:
            existing.duration_seconds = payload.duration_seconds
        existing.is_completed_verified = verified_completion
        existing.last_watched_at = now
        entry = existing
    else:
        entry = WatchHistory(
            user_id=current_user.id,
            movie_id=payload.movie_id,
            source_id=payload.source_id,
            last_event=effective_event,
            position_seconds=payload.position_seconds,
            duration_seconds=payload.duration_seconds,
            is_completed_verified=verified_completion,
            started_at=now,
            last_watched_at=now,
        )
        db.add(entry)

    await db.commit()

    stmt = (
        select(WatchHistory)
        .options(selectinload(WatchHistory.movie))
        .where(WatchHistory.id == entry.id)
    )
    refreshed = (await db.execute(stmt)).scalar_one()
    return refreshed


@router.get(
    "",
    response_model=WatchHistoryListResponse,
    summary="Listar historial de visualización del usuario autenticado",
)
async def get_watch_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total = (
        await db.execute(
            select(func.count(WatchHistory.id)).where(
                WatchHistory.user_id == current_user.id
            )
        )
    ).scalar_one()

    stmt = (
        select(WatchHistory)
        .options(selectinload(WatchHistory.movie))
        .where(WatchHistory.user_id == current_user.id)
        .order_by(desc(WatchHistory.last_watched_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()

    return WatchHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una película del historial del usuario (idempotente)",
)
async def delete_movie_from_history(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(WatchHistory).where(
            WatchHistory.user_id == current_user.id,
            WatchHistory.movie_id == movie_id,
        )
    )
    await db.commit()
    return None


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Limpiar todo el historial del usuario autenticado (idempotente)",
)
async def clear_watch_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(WatchHistory).where(WatchHistory.user_id == current_user.id)
    )
    await db.commit()
    return None
