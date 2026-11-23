from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.movie import Movie
from app.models.provider import Provider
from app.models.source import Source
from app.schemas.playback import (
    MoviePlaybackOptionsResponse,
    PlaybackOptionResponse,
    PublicProviderResponse,
)

router = APIRouter(prefix="/movies", tags=["Reproducción - Visitantes"])


@router.get(
    "/{movie_id}/playback-options",
    response_model=MoviePlaybackOptionsResponse,
    summary="Consultar servidores, idiomas y subtítulos disponibles",
)
async def get_movie_playback_options(
    movie_id: int,
    territory: Optional[str] = Query(
        default=None,
        min_length=2,
        max_length=10,
        description="Código de territorio (ej. CO, MX). Si se omite, devuelve todas las activas.",
    ),
    language: Optional[str] = Query(
        default=None,
        description="Filtrar por idioma de audio (ej. es, en).",
    ),
    db: AsyncSession = Depends(get_db),
):
    movie_result = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = movie_result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Película no encontrada")

    stmt = (
        select(Source)
        .join(Provider, Source.provider_id == Provider.id)
        .options(selectinload(Source.provider))
        .where(
            Source.movie_id == movie_id,
            Source.is_active.is_(True),
            Source.is_verified.is_(True),
            Provider.is_active.is_(True),
        )
    )
    result = await db.execute(stmt)
    sources = result.scalars().all()

    now = datetime.now(timezone.utc)
    territory_code = territory.upper() if territory else None
    language_code = language.lower() if language else None

    valid_options: list[PlaybackOptionResponse] = []

    for src in sources:
        # Descartar fuentes caducadas
        if src.expires_at is not None and src.expires_at <= now:
            continue

        # Filtrar por territorio (coincidencia exacta o GLOBAL)
        src_territories = [t.upper() for t in (src.territories or [])]
        if territory_code and src_territories:
            if territory_code not in src_territories and "GLOBAL" not in src_territories:
                continue

        # Filtrar por idioma si se indicó
        src_languages = [lang.lower() for lang in (src.languages or [])]
        if language_code and language_code not in src_languages:
            continue

        valid_options.append(
            PlaybackOptionResponse(
                source_id=src.id,
                provider=PublicProviderResponse.model_validate(src.provider),
                resource_identifier=src.resource_identifier,
                languages=src.languages or [],
                audio_type=src.audio_type,
                subtitles=src.subtitles or [],
                territories=src_territories,
                expires_at=src.expires_at,
            )
        )

    is_available = len(valid_options) > 0
    return MoviePlaybackOptionsResponse(
        movie_id=movie.id,
        title=movie.title,
        is_available=is_available,
        availability_status="Disponible" if is_available else "Próximamente",
        territory_applied=territory_code,
        total_options=len(valid_options),
        options=valid_options,
    )