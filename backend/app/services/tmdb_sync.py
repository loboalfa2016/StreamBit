import logging
from datetime import date
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.movie import Movie
from app.models.sync_log import SyncLog

logger = logging.getLogger("streambit.sync")
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


async def sync_movies_from_tmdb(db: AsyncSession, trigger: str = "manual") -> SyncLog:
    created_count = 0
    updated_count = 0

    if not settings.TMDB_API_KEY:
        log = SyncLog(
            provider="tmdb",
            trigger=trigger,
            status="error",
            error_message="TMDB_API_KEY no está configurada.",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        logger.error("EVENT=SYNC_FAILED trigger=%s reason=MISSING_API_KEY", trigger)
        return log

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{settings.TMDB_BASE_URL}/movie/popular",
                params={
                    "api_key": settings.TMDB_API_KEY,
                    "language": "es-ES",
                    "page": 1,
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])

        for item in results:
            ext_id = str(item.get("id"))
            title = item.get("title")
            if not ext_id or not title:
                continue

            synopsis = item.get("overview") or None
            release_date = _parse_date(item.get("release_date"))
            poster_path = item.get("poster_path")
            poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None

            stmt = select(Movie).where(Movie.external_id == ext_id)
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing:
                # Actualiza solo metadatos permitidos; nunca toca is_available ni sources
                existing.title = title
                existing.synopsis = synopsis
                existing.release_date = release_date
                existing.poster_url = poster_url
                updated_count += 1
            else:
                new_movie = Movie(
                    external_id=ext_id,
                    title=title,
                    synopsis=synopsis,
                    release_date=release_date,
                    poster_url=poster_url,
                    is_available=False,  # Nunca supone derechos de reproducción
                )
                db.add(new_movie)
                created_count += 1

        log = SyncLog(
            provider="tmdb",
            trigger=trigger,
            status="success",
            created_count=created_count,
            updated_count=updated_count,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        logger.info(
            "EVENT=SYNC_SUCCESS trigger=%s created=%s updated=%s",
            trigger,
            created_count,
            updated_count,
        )
        return log

    except Exception as exc:
        await db.rollback()
        log = SyncLog(
            provider="tmdb",
            trigger=trigger,
            status="error",
            error_message=str(exc),
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        logger.error("EVENT=SYNC_FAILED trigger=%s error=%s", trigger, str(exc))
        return log