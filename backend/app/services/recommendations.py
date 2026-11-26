from collections import Counter
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Genre, movie_genres
from app.models.community import Rating
from app.models.movie import Movie
from app.models.user import User
from app.models.user_lists import Favorite
from app.models.watch_history import WatchHistory
from app.schemas.recommendations import RecommendationsResponse, RecommendedMovieItem


def _general_sort_key(
    movie: Movie,
    rating_stats: dict[int, tuple[Optional[float], int]],
) -> tuple:
    avg_score, ratings_count = rating_stats.get(movie.id, (None, 0))
    return (
        avg_score or 0.0,
        ratings_count,
        1 if movie.is_featured else 0,
        movie.release_date or date.min,
        movie.id,
    )


def _general_reason(
    movie: Movie,
    rating_stats: dict[int, tuple[Optional[float], int]],
) -> str:
    avg_score, ratings_count = rating_stats.get(movie.id, (None, 0))
    if ratings_count > 0 and (avg_score or 0.0) >= 4.0:
        return "Mejor calificada disponible"
    if movie.is_featured:
        return "Destacada disponible"
    return "Estreno reciente disponible"


def _to_recommended_item(
    movie: Movie,
    rating_stats: dict[int, tuple[Optional[float], int]],
    reason: str,
) -> RecommendedMovieItem:
    avg_score, ratings_count = rating_stats.get(movie.id, (None, 0))
    return RecommendedMovieItem(
        id=movie.id,
        title=movie.title,
        poster_url=movie.poster_url,
        release_date=movie.release_date,
        availability_status=movie.availability_status,
        genres=[g.name for g in movie.genres],
        average_score=avg_score,
        ratings_count=ratings_count,
        recommendation_reason=reason,
    )


async def get_recommendations_for_user(
    db: AsyncSession,
    current_user: Optional[User],
    limit: int = 10,
) -> RecommendationsResponse:
    movies_stmt = (
        select(Movie)
        .options(selectinload(Movie.genres))
        .where(Movie.is_published.is_(True), Movie.is_available.is_(True))
    )
    available_movies = list((await db.execute(movies_stmt)).scalars().all())

    stats_rows = (
        await db.execute(
            select(
                Rating.movie_id,
                func.avg(Rating.score),
                func.count(Rating.id),
            ).group_by(Rating.movie_id)
        )
    ).all()
    rating_stats: dict[int, tuple[Optional[float], int]] = {
        row[0]: (round(float(row[1]), 2) if row[1] is not None else None, int(row[2]))
        for row in stats_rows
    }

    if current_user is None:
        sorted_general = sorted(
            available_movies,
            key=lambda m: _general_sort_key(m, rating_stats),
            reverse=True,
        )[:limit]
        items = [
            _to_recommended_item(m, rating_stats, _general_reason(m, rating_stats))
            for m in sorted_general
        ]
        return RecommendationsResponse(
            strategy="general",
            explanation="Recomendaciones generales basadas en películas disponibles y mejor valoradas del catálogo.",
            items=items,
            total=len(items),
        )

    fav_ids = set(
        (
            await db.execute(
                select(Favorite.movie_id).where(Favorite.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    history_ids = set(
        (
            await db.execute(
                select(WatchHistory.movie_id).where(
                    WatchHistory.user_id == current_user.id
                )
            )
        )
        .scalars()
        .all()
    )
    excluded_ids = fav_ids | history_ids

    genre_counts: Counter[str] = Counter()
    if excluded_ids:
        user_genre_names = list(
            (
                await db.execute(
                    select(Genre.name)
                    .join(movie_genres, Genre.id == movie_genres.c.genre_id)
                    .where(movie_genres.c.movie_id.in_(excluded_ids))
                )
            )
            .scalars()
            .all()
        )
        genre_counts.update(user_genre_names)

    unseen_candidates = [m for m in available_movies if m.id not in excluded_ids]

    if genre_counts and unseen_candidates:
        scored: list[tuple[tuple, Movie, str]] = []
        for m in unseen_candidates:
            matching = [g.name for g in m.genres if g.name in genre_counts]
            if not matching:
                continue
            weight = sum(genre_counts[name] for name in matching)
            best_genre = max(matching, key=lambda name: genre_counts[name])
            avg_score, ratings_count = rating_stats.get(m.id, (None, 0))
            score_key = (
                weight,
                avg_score or 0.0,
                ratings_count,
                1 if m.is_featured else 0,
                m.release_date or date.min,
                m.id,
            )
            scored.append((score_key, m, best_genre))

        if scored:
            scored.sort(key=lambda entry: entry[0], reverse=True)
            selected_items: list[RecommendedMovieItem] = []
            selected_ids: set[int] = set()

            for _, m, best_genre in scored[:limit]:
                selected_ids.add(m.id)
                selected_items.append(
                    _to_recommended_item(
                        m,
                        rating_stats,
                        f"Basado en tu interés en {best_genre}",
                    )
                )

            if len(selected_items) < limit:
                remaining = [
                    m for m in unseen_candidates if m.id not in selected_ids
                ]
                remaining.sort(
                    key=lambda m: _general_sort_key(m, rating_stats),
                    reverse=True,
                )
                for m in remaining[: limit - len(selected_items)]:
                    selected_items.append(
                        _to_recommended_item(
                            m, rating_stats, _general_reason(m, rating_stats)
                        )
                    )

            return RecommendationsResponse(
                strategy="personalized",
                explanation="Recomendaciones personalizadas basadas en tus géneros favoritos e historial de visualización.",
                items=selected_items,
                total=len(selected_items),
            )

    fallback_pool = unseen_candidates if unseen_candidates else available_movies
    sorted_fallback = sorted(
        fallback_pool,
        key=lambda m: _general_sort_key(m, rating_stats),
        reverse=True,
    )[:limit]
    fallback_items = [
        _to_recommended_item(m, rating_stats, _general_reason(m, rating_stats))
        for m in sorted_fallback
    ]
    return RecommendationsResponse(
        strategy="general_fallback",
        explanation="Recomendaciones generales del catálogo porque aún no hay suficiente actividad o coincidencias.",
        items=fallback_items,
        total=len(fallback_items),
    )
