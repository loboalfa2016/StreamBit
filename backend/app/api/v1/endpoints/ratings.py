from datetime import datetime, timezone
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_optional_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import check_rate_limit
from app.models.community import Rating
from app.models.movie import Movie
from app.models.user import User
from app.schemas.ratings import (
    MovieRatingSummaryResponse,
    RatingCreateRequest,
    RatingResponse,
)

router = APIRouter(prefix="/movies", tags=["Ratings"])


def _build_visitor_fingerprint(request: Request) -> str:
    visitor_id = request.headers.get("X-Visitor-Id", "").strip()
    if visitor_id:
        raw_identity = f"visitor:{visitor_id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        raw_identity = f"anon:{client_ip}:{user_agent}"

    salted = f"{settings.SECRET_KEY}:{raw_identity}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


async def _ensure_movie_exists(db: AsyncSession, movie_id: int) -> None:
    exists = (
        await db.execute(select(Movie.id).where(Movie.id == movie_id))
    ).scalar_one_or_none()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )


def _to_rating_response(rating: Rating) -> RatingResponse:
    return RatingResponse(
        id=rating.id,
        movie_id=rating.movie_id,
        score=rating.score,
        is_registered_user=rating.user_id is not None,
        created_at=rating.created_at,
        updated_at=rating.updated_at,
    )


@router.post(
    "/{movie_id}/ratings",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calificar una película (usuario registrado o visitante)",
)
async def rate_movie(
    movie_id: int,
    payload: RatingCreateRequest,
    request: Request,
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_movie_exists(db, movie_id)

    visitor_fp = None if current_user else _build_visitor_fingerprint(request)
    rate_key = (
        f"rating:user:{current_user.id}"
        if current_user
        else f"rating:visitor:{visitor_fp}"
    )
    if not check_rate_limit(rate_key, max_requests=20, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes de calificación. Intenta nuevamente en un minuto.",
        )

    identity_filter = (
        Rating.user_id == current_user.id
        if current_user
        else Rating.visitor_fingerprint == visitor_fp
    )
    existing = (
        await db.execute(
            select(Rating).where(Rating.movie_id == movie_id, identity_filter)
        )
    ).scalar_one_or_none()

    if existing:
        if not settings.ALLOW_RATING_EDIT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya registraste una calificación para esta película.",
            )
        existing.score = payload.score
        existing.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return _to_rating_response(existing)

    new_rating = Rating(
        movie_id=movie_id,
        user_id=current_user.id if current_user else None,
        visitor_fingerprint=visitor_fp,
        score=payload.score,
    )
    db.add(new_rating)
    await db.commit()
    await db.refresh(new_rating)
    return _to_rating_response(new_rating)


@router.get(
    "/{movie_id}/ratings/summary",
    response_model=MovieRatingSummaryResponse,
    summary="Obtener promedio y total de calificaciones de una película",
)
async def get_movie_rating_summary(
    movie_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_movie_exists(db, movie_id)

    avg_val, ratings_count = (
        await db.execute(
            select(func.avg(Rating.score), func.count(Rating.id)).where(
                Rating.movie_id == movie_id
            )
        )
    ).one()

    average_score = (
        round(float(avg_val), 2) if ratings_count > 0 and avg_val is not None else None
    )

    if current_user:
        identity_filter = Rating.user_id == current_user.id
    else:
        identity_filter = Rating.visitor_fingerprint == _build_visitor_fingerprint(request)

    my_rating = (
        await db.execute(
            select(Rating.score).where(Rating.movie_id == movie_id, identity_filter)
        )
    ).scalar_one_or_none()

    return MovieRatingSummaryResponse(
        movie_id=movie_id,
        average_score=average_score,
        ratings_count=ratings_count,
        my_rating=my_rating,
    )


@router.delete(
    "/{movie_id}/ratings/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar mi calificación de una película (idempotente)",
)
async def delete_my_rating(
    movie_id: int,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user:
        identity_filter = Rating.user_id == current_user.id
    else:
        identity_filter = Rating.visitor_fingerprint == _build_visitor_fingerprint(request)

    await db.execute(
        delete(Rating).where(Rating.movie_id == movie_id, identity_filter)
    )
    await db.commit()
    return None
