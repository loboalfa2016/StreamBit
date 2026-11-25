from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, desc, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.catalog import Genre
from app.models.movie import Movie
from app.schemas.collections import (
    CatalogCollectionResponse,
    CatalogCollectionsResponse,
    FeaturedMovieResponse,
)

router = APIRouter(prefix="/catalog", tags=["Catálogo - Home y Colecciones"])


def _apply_order(stmt, sort_by: str, default_order: list):
    if sort_by == "newest":
        return stmt.order_by(desc(Movie.release_date), desc(Movie.created_at), Movie.id.asc())
    if sort_by == "oldest":
        return stmt.order_by(asc(Movie.release_date), asc(Movie.created_at), Movie.id.asc())
    if sort_by == "title_asc":
        return stmt.order_by(asc(Movie.title), Movie.id.asc())
    if sort_by == "available_first":
        return stmt.order_by(desc(Movie.is_available), desc(Movie.created_at), Movie.id.asc())
    return stmt.order_by(*default_order)


async def _get_featured_movie(db: AsyncSession) -> tuple[Optional[Movie], str]:
    # Regla 1: Película marcada manualmente como destacada (publicada, priorizando disponibles)
    explicit_stmt = (
        select(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.countries))
        .where(Movie.is_published.is_(True), Movie.is_featured.is_(True))
        .order_by(desc(Movie.is_available), desc(Movie.created_at), Movie.id.asc())
        .limit(1)
    )
    movie = (await db.execute(explicit_stmt)).scalar_one_or_none()
    if movie:
        return movie, "Destacada configurada manualmente (is_featured=true)."

    # Regla 2 (Fallback): Película publicada y disponible más reciente
    fallback_stmt = (
        select(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.countries))
        .where(Movie.is_published.is_(True))
        .order_by(desc(Movie.is_available), desc(Movie.created_at), Movie.id.asc())
        .limit(1)
    )
    movie = (await db.execute(fallback_stmt)).scalar_one_or_none()
    if movie:
        return movie, "Selección automática: película publicada y disponible más reciente."

    return None, "No hay películas publicables disponibles."


@router.get(
    "/featured",
    response_model=FeaturedMovieResponse,
    summary="Obtener película destacada activa",
)
async def get_featured_movie(db: AsyncSession = Depends(get_db)):
    movie, rule = await _get_featured_movie(db)
    return FeaturedMovieResponse(movie=movie, selection_rule=rule)


@router.get(
    "/collections",
    response_model=CatalogCollectionsResponse,
    summary="Obtener colecciones del catálogo para la página principal",
)
async def get_catalog_collections(
    limit: int = Query(10, ge=1, le=25, description="Máximo de películas por colección"),
    genre: Optional[str] = Query(
        None, min_length=1, max_length=60, description="Filtrar colección por un género específico"
    ),
    sort_by: Literal["default", "newest", "oldest", "title_asc", "available_first"] = Query(
        "default", description="Regla de ordenamiento para las colecciones"
    ),
    db: AsyncSession = Depends(get_db),
):
    featured_movie, _ = await _get_featured_movie(db)
    collections: list[CatalogCollectionResponse] = []

    base_options = (selectinload(Movie.genres), selectinload(Movie.countries))

    # 1. Populares: disponibles primero y más recientes
    popular_stmt = _apply_order(
        select(Movie).options(*base_options).where(Movie.is_published.is_(True)),
        sort_by,
        [desc(Movie.is_available), desc(Movie.created_at), Movie.id.asc()],
    ).limit(limit)
    popular_movies = (await db.execute(popular_stmt)).scalars().all()
    collections.append(
        CatalogCollectionResponse(
            slug="popular",
            title="Populares",
            ordering_rule="Disponibles primero, luego más recientes" if sort_by == "default" else f"Orden configurado: {sort_by}",
            total=len(popular_movies),
            items=popular_movies,
        )
    )

    # 2. Clásicas: estrenadas antes del año 2000
    classics_stmt = _apply_order(
        select(Movie)
        .options(*base_options)
        .where(
            Movie.is_published.is_(True),
            Movie.release_date.is_not(None),
            extract("year", Movie.release_date) < 2000,
        ),
        sort_by,
        [asc(Movie.release_date), Movie.id.asc()],
    ).limit(limit)
    classics_movies = (await db.execute(classics_stmt)).scalars().all()
    collections.append(
        CatalogCollectionResponse(
            slug="classics",
            title="Clásicas",
            ordering_rule="Estrenos anteriores a 2000, orden cronológico" if sort_by == "default" else f"Orden configurado: {sort_by}",
            total=len(classics_movies),
            items=classics_movies,
        )
    )

    # 3. Independientes: marcadas con is_indie=True o con género Indie/Independiente
    indie_stmt = _apply_order(
        select(Movie)
        .options(*base_options)
        .where(
            Movie.is_published.is_(True),
            or_(
                Movie.is_indie.is_(True),
                Movie.genres.any(Genre.name.ilike("%indie%")),
                Movie.genres.any(Genre.name.ilike("%independiente%")),
            ),
        ),
        sort_by,
        [desc(Movie.is_available), desc(Movie.release_date), Movie.id.asc()],
    ).limit(limit)
    indie_movies = (await db.execute(indie_stmt)).scalars().all()
    collections.append(
        CatalogCollectionResponse(
            slug="indie",
            title="Independientes",
            ordering_rule="Películas indie disponibles primero y por fecha de estreno" if sort_by == "default" else f"Orden configurado: {sort_by}",
            total=len(indie_movies),
            items=indie_movies,
        )
    )

    # 4. Por género: si se pasa ?genre=X trae ese género; si no, trae hasta 3 géneros con películas publicadas
    if genre and genre.strip():
        genre_stmt = _apply_order(
            select(Movie)
            .options(*base_options)
            .where(
                Movie.is_published.is_(True),
                Movie.genres.any(Genre.name.ilike(f"%{genre.strip()}%")),
            ),
            sort_by,
            [desc(Movie.is_available), desc(Movie.release_date), Movie.id.asc()],
        ).limit(limit)
        genre_movies = (await db.execute(genre_stmt)).scalars().all()
        collections.append(
            CatalogCollectionResponse(
                slug=f"genre-{genre.strip().lower().replace(' ', '-')}",
                title=f"Género: {genre.strip()}",
                ordering_rule="Disponibles primero y por fecha de estreno" if sort_by == "default" else f"Orden configurado: {sort_by}",
                total=len(genre_movies),
                items=genre_movies,
            )
        )
    else:
        genres_stmt = select(Genre).order_by(asc(Genre.name)).limit(3)
        genres_list = (await db.execute(genres_stmt)).scalars().all()
        for g in genres_list:
            g_movies_stmt = _apply_order(
                select(Movie)
                .options(*base_options)
                .where(
                    Movie.is_published.is_(True),
                    Movie.genres.any(Genre.id == g.id),
                ),
                sort_by,
                [desc(Movie.is_available), desc(Movie.release_date), Movie.id.asc()],
            ).limit(limit)
            g_movies = (await db.execute(g_movies_stmt)).scalars().all()
            if g_movies:
                collections.append(
                    CatalogCollectionResponse(
                        slug=f"genre-{g.name.lower().replace(' ', '-')}",
                        title=f"Género: {g.name}",
                        ordering_rule="Disponibles primero y por fecha de estreno" if sort_by == "default" else f"Orden configurado: {sort_by}",
                        total=len(g_movies),
                        items=g_movies,
                    )
                )

    return CatalogCollectionsResponse(
        featured=featured_movie,
        collections=collections,
    )