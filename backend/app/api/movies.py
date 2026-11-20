import math
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, asc, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.movie import Movie
from app.schemas.movie import MovieResponse, PaginatedMoviesResponse

router = APIRouter(prefix="/api/v1/movies", tags=["Movies"])

SORT_COLUMNS = {
    "title": Movie.title,
    "release_date": Movie.release_date,
    "created_at": Movie.created_at,
}


@router.get("", response_model=PaginatedMoviesResponse)
async def list_movies(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(10, ge=1, le=50, description="Cantidad de películas por página"),
    sort_by: Literal["title", "release_date", "created_at"] = Query(
        "created_at", description="Campo de ordenamiento"
    ),
    order: Literal["asc", "desc"] = Query("desc", description="Dirección del ordenamiento"),
    db: AsyncSession = Depends(get_db),
):
    """Lista pública paginada y ordenada del catálogo de películas."""
    count_stmt = select(func.count(Movie.id))
    total = (await db.execute(count_stmt)).scalar_one()

    sort_column = SORT_COLUMNS[sort_by]
    order_clause = asc(sort_column) if order == "asc" else desc(sort_column)

    offset = (page - 1) * page_size
    stmt = (
        select(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.countries))
        .order_by(order_clause, Movie.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    movies = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedMoviesResponse(
        items=movies,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie_detail(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Ficha pública detallada de una película."""
    stmt = (
        select(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.countries))
        .where(Movie.id == movie_id)
    )
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    return movie