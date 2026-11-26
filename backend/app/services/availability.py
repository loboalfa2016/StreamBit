from typing import Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie import Movie
from app.models.source import Source
from app.models.availability_log import MovieAvailabilityLog
from app.services.notifications import notify_movie_became_available


def _status_label(is_available: bool) -> str:
    return "Disponible" if is_available else "Próximamente"


async def count_valid_sources(db: AsyncSession, movie_id: int) -> int:
    """Cuenta las fuentes activas y verificadas para una película."""
    stmt = select(func.count(Source.id)).where(
        Source.movie_id == movie_id,
        Source.is_active.is_(True),
        Source.is_verified.is_(True),
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def recalculate_movie_availability(
    db: AsyncSession,
    movie_id: int,
    reason: str,
    changed_by_user_id: Optional[int] = None,
) -> Tuple[Optional[Movie], int, bool, Optional[MovieAvailabilityLog]]:
    """
    Recalcula la disponibilidad real de una película:
    - Disponible: si tiene al menos 1 fuente activa y verificada.
    - Próximamente: si no tiene fuentes válidas.
    Registra un log en movie_availability_logs solo si el estado cambió.
    """
    result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        return None, 0, False, None

    valid_sources_count = await count_valid_sources(db, movie_id)
    new_is_available = valid_sources_count > 0
    previous_is_available = bool(movie.is_available)

    if new_is_available == previous_is_available:
        return movie, valid_sources_count, False, None

    movie.is_available = new_is_available
    log_entry = MovieAvailabilityLog(
        movie_id=movie.id,
        previous_is_available=previous_is_available,
        new_is_available=new_is_available,
        previous_status=_status_label(previous_is_available),
        new_status=_status_label(new_is_available),
        reason=reason,
        changed_by_user_id=changed_by_user_id,
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(movie)
    await db.refresh(log_entry)

    if not previous_is_available and new_is_available:
        await notify_movie_became_available(db, movie, event_ref=str(log_entry.id))

    return movie, valid_sources_count, True, log_entry


async def get_movie_availability_logs(
    db: AsyncSession,
    movie_id: int,
    limit: int = 50,
) -> list[MovieAvailabilityLog]:
    """Devuelve el historial de cambios de disponibilidad de una película."""
    stmt = (
        select(MovieAvailabilityLog)
        .where(MovieAvailabilityLog.movie_id == movie_id)
        .order_by(MovieAvailabilityLog.changed_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())