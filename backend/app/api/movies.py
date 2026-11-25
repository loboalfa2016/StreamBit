import math
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, and_, asc, cast as sa_cast, desc, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.catalog import Country, Genre
from app.models.movie import Movie
from app.models.source import Source
from app.schemas.movie import MovieResponse, PaginatedMoviesResponse

router = APIRouter(prefix="/api/v1/movies", tags=["Movies"])

SORT_COLUMNS = {
    "title": Movie.title,
    "release_date": Movie.release_date,
    "created_at": Movie.created_at,
    "is_available": Movie.is_available,
}


@router.get("", response_model=PaginatedMoviesResponse)
async def list_movies(
    q: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Búsqueda por título, sinopsis, director o reparto",
    ),
    genre: Optional[str] = Query(
        None, min_length=1, max_length=60, description="Filtrar por nombre de género"
    ),
    year: Optional[int] = Query(
        None, ge=1888, le=2100, description="Filtrar por año de estreno"
    ),
    country: Optional[str] = Query(
        None, min_length=1, max_length=60, description="Filtrar por país (nombre o código)"
    ),
    language: Optional[str] = Query(
        None, min_length=2, max_length=10, description="Filtrar por idioma original o de fuente (ej. en, es)"
    ),
    director: Optional[str] = Query(
        None, min_length=1, max_length=100, description="Filtrar por director"
    ),
    actor: Optional[str] = Query(
        None, min_length=1, max_length=100, description="Filtrar por actor en el reparto"
    ),
    only_available: Optional[bool] = Query(
        None, description="Si es true, devuelve solo películas disponibles"
    ),
    page: int = Query(1, ge=1, le=1000, description="Número de página"),
    page_size: int = Query(10, ge=1, le=50, description="Cantidad de películas por página (máx. 50)"),
    sort_by: Literal["title", "release_date", "created_at", "is_available"] = Query(
        "created_at", description="Campo de ordenamiento"
    ),
    order: Literal["asc", "desc"] = Query("desc", description="Dirección del ordenamiento"),
    db: AsyncSession = Depends(get_db),
):
    """Búsqueda, filtrado combinable, paginación y ordenamiento del catálogo."""
    filters = []

    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Movie.title.ilike(term),
                Movie.synopsis.ilike(term),
                Movie.director.ilike(term),
                sa_cast(Movie.cast, String).ilike(term),
            )
        )

    if genre and genre.strip():
        filters.append(Movie.genres.any(Genre.name.ilike(f"%{genre.strip()}%")))

    if year is not None:
        filters.append(extract("year", Movie.release_date) == year)

    if country and country.strip():
        country_term = f"%{country.strip()}%"
        country_cond = Country.name.ilike(country_term)
        if hasattr(Country, "code"):
            country_cond = or_(country_cond, Country.code.ilike(country.strip()))
        filters.append(Movie.countries.any(country_cond))

    if language and language.strip():
        lang_clean = language.strip().lower()
        filters.append(
            or_(
                func.lower(Movie.original_language) == lang_clean,
                Movie.sources.any(
                    and_(
                        Source.is_active.is_(True),
                        Source.is_verified.is_(True),
                        sa_cast(Source.languages, String).ilike(f'%"{lang_clean}"%'),
                    )
                ),
            )
        )

    if director and director.strip():
        filters.append(Movie.director.ilike(f"%{director.strip()}%"))

    if actor and actor.strip():
        filters.append(sa_cast(Movie.cast, String).ilike(f"%{actor.strip()}%"))

    if only_available is True:
        filters.append(Movie.is_available.is_(True))

    count_stmt = select(func.count(Movie.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    if total == 0:
        return PaginatedMoviesResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )

    sort_column = SORT_COLUMNS[sort_by]
    order_clause = asc(sort_column) if order == "asc" else desc(sort_column)

    offset = (page - 1) * page_size
    stmt = (
        select(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.countries))
        .where(*filters)
        .order_by(order_clause, Movie.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    movies = result.scalars().all()

    total_pages = math.ceil(total / page_size)

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