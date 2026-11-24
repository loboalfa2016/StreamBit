from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.movie import Movie
from app.models.provider import Provider
from app.models.source import Source
from app.models.user import User
from app.schemas.source import (
    ProviderCreate,
    ProviderResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)
from app.services.availability import recalculate_movie_availability

router = APIRouter(prefix="/admin", tags=["Admin - Fuentes"])


@router.post(
    "/providers",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    payload: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    existing_provider = await db.execute(
        select(Provider.id)
        .where(or_(Provider.name == payload.name, Provider.code == payload.code))
        .limit(1)
    )
    if existing_provider.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proveedor con ese nombre o código.",
        )

    provider = Provider(**payload.model_dump())
    db.add(provider)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proveedor con ese nombre o código.",
        )
    await db.refresh(provider)
    return provider


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    result = await db.execute(select(Provider).order_by(Provider.name, Provider.id))
    return list(result.scalars().all())


@router.post(
    "/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    movie_result = await db.execute(select(Movie.id).where(Movie.id == payload.movie_id))
    if movie_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    provider_result = await db.execute(
        select(Provider.id).where(Provider.id == payload.provider_id)
    )
    if provider_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado.",
        )

    source = Source(
        **payload.model_dump(),
        created_by_user_id=current_user.id,
    )
    db.add(source)
    await db.flush()
    await recalculate_movie_availability(
        db=db,
        movie_id=source.movie_id,
        reason="Fuente creada manualmente",
        changed_by_user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(source)
    return source


@router.get(
    "/movies/{movie_id}/sources",
    response_model=list[SourceResponse],
)
async def list_movie_sources(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    movie_result = await db.execute(select(Movie.id).where(Movie.id == movie_id))
    if movie_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    result = await db.execute(
        select(Source)
        .where(Source.movie_id == movie_id)
        .order_by(Source.id)
    )
    return list(result.scalars().all())


@router.patch(
    "/sources/{source_id}",
    response_model=SourceResponse,
)
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fuente no encontrada.",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "provider_id" in updates:
        provider_result = await db.execute(
            select(Provider.id).where(Provider.id == updates["provider_id"])
        )
        if provider_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proveedor no encontrado.",
            )

    for field, value in updates.items():
        setattr(source, field, value)

    await recalculate_movie_availability(
        db=db,
        movie_id=source.movie_id,
        reason="Fuente actualizada manualmente",
        changed_by_user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(source)
    return source


@router.patch(
    "/sources/{source_id}/deactivate",
    response_model=SourceResponse,
)
async def deactivate_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("catalog:write")),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fuente no encontrada.",
        )

    source.is_active = False
    await recalculate_movie_availability(
        db=db,
        movie_id=source.movie_id,
        reason="Fuente desactivada manualmente",
        changed_by_user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(source)
    return source
