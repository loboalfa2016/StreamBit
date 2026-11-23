from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.movie import Movie
from app.models.user import User
from app.schemas.availability import (
    AvailabilityEvaluateRequest,
    AvailabilityLogResponse,
    MovieAvailabilityResponse,
)
from app.services.availability import (
    get_movie_availability_logs,
    recalculate_movie_availability,
)

router = APIRouter(prefix="/admin/movies", tags=["Admin - Disponibilidad"])


@router.post(
    "/{movie_id}/availability/evaluate",
    response_model=MovieAvailabilityResponse,
    status_code=status.HTTP_200_OK,
)
async def evaluate_movie_availability(
    movie_id: int,
    payload: AvailabilityEvaluateRequest = AvailabilityEvaluateRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    """
    Evalúa las fuentes activas y verificadas de la película y actualiza su estado
    ('Disponible' o 'Próximamente') conservando trazabilidad si hubo cambio.
    """
    movie, valid_count, changed, log_entry = await recalculate_movie_availability(
        db=db,
        movie_id=movie_id,
        reason=payload.reason or "Evaluación manual de disponibilidad",
        changed_by_user_id=current_user.id,
    )
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada",
        )

    return MovieAvailabilityResponse(
        movie_id=movie.id,
        title=movie.title,
        is_available=movie.is_available,
        availability_status=movie.availability_status,
        valid_sources_count=valid_count,
        status_changed=changed,
        log=log_entry,
    )


@router.get(
    "/{movie_id}/availability/logs",
    response_model=list[AvailabilityLogResponse],
    status_code=status.HTTP_200_OK,
)
async def list_movie_availability_logs(
    movie_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    """Consulta el historial de cambios de disponibilidad de una película."""
    result = await db.execute(select(Movie.id).where(Movie.id == movie_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada",
        )

    return await get_movie_availability_logs(db=db, movie_id=movie_id, limit=limit)