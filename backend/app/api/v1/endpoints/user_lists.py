from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user  # Ajusta si tu dependencia está en otro módulo
from app.core.database import get_db
from app.models.movie import Movie
from app.models.user import User
from app.models.user_lists import Favorite, UserList, UserListItem
from app.schemas.user_lists import (
    FavoriteActionResponse,
    FavoriteItemResponse,
    ListMovieActionResponse,
    UserListCreate,
    UserListDetailResponse,
    UserListSummaryResponse,
    UserListUpdate,
)

router = APIRouter(prefix="/me", tags=["Usuario - Favoritos y Listas"])


async def _get_owned_list(db: AsyncSession, list_id: int, user_id: int) -> UserList:
    stmt = (
        select(UserList)
        .options(
            selectinload(UserList.items)
            .selectinload(UserListItem.movie)
            .selectinload(Movie.genres),
            selectinload(UserList.items)
            .selectinload(UserListItem.movie)
            .selectinload(Movie.countries),
        )
        .where(UserList.id == list_id, UserList.user_id == user_id)
    )
    user_list = (await db.execute(stmt)).scalar_one_or_none()
    if not user_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lista no encontrada.",
        )
    return user_list


async def _ensure_movie_exists(db: AsyncSession, movie_id: int) -> Movie:
    movie = (
        await db.execute(select(Movie).where(Movie.id == movie_id))
    ).scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )
    return movie


# ========================
# FAVORITOS
# ========================

@router.get("/favorites", response_model=list[FavoriteItemResponse], summary="Listar mis películas favoritas")
async def list_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Favorite)
        .options(
            selectinload(Favorite.movie).selectinload(Movie.genres),
            selectinload(Favorite.movie).selectinload(Movie.countries),
        )
        .where(Favorite.user_id == current_user.id)
        .order_by(desc(Favorite.created_at))
    )
    return (await db.execute(stmt)).scalars().all()


@router.put(
    "/favorites/{movie_id}",
    response_model=FavoriteActionResponse,
    summary="Agregar película a favoritos (idempotente)",
)
async def add_favorite(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_movie_exists(db, movie_id)

    existing = (
        await db.execute(
            select(Favorite).where(
                Favorite.user_id == current_user.id,
                Favorite.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        return FavoriteActionResponse(
            movie_id=movie_id,
            is_favorite=True,
            detail="La película ya estaba en tus favoritos.",
        )

    fav = Favorite(user_id=current_user.id, movie_id=movie_id)
    db.add(fav)
    await db.commit()

    return FavoriteActionResponse(
        movie_id=movie_id,
        is_favorite=True,
        detail="Película agregada a favoritos.",
    )


@router.delete(
    "/favorites/{movie_id}",
    response_model=FavoriteActionResponse,
    summary="Quitar película de favoritos (idempotente)",
)
async def remove_favorite(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(Favorite).where(
                Favorite.user_id == current_user.id,
                Favorite.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()

    if not existing:
        return FavoriteActionResponse(
            movie_id=movie_id,
            is_favorite=False,
            detail="La película no estaba en tus favoritos.",
        )

    await db.delete(existing)
    await db.commit()

    return FavoriteActionResponse(
        movie_id=movie_id,
        is_favorite=False,
        detail="Película retirada de favoritos.",
    )


# ========================
# LISTAS PERSONALES
# ========================

@router.get("/lists", response_model=list[UserListSummaryResponse], summary="Listar mis listas personales")
async def list_user_lists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(UserList)
        .options(selectinload(UserList.items))
        .where(UserList.user_id == current_user.id)
        .order_by(desc(UserList.updated_at))
    )
    lists = (await db.execute(stmt)).scalars().all()
    return [
        UserListSummaryResponse(
            id=ul.id,
            name=ul.name,
            description=ul.description,
            total_movies=len(ul.items),
            created_at=ul.created_at,
            updated_at=ul.updated_at,
        )
        for ul in lists
    ]


@router.post(
    "/lists",
    response_model=UserListSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una lista personal",
)
async def create_user_list(
    payload: UserListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="El nombre de la lista no puede estar vacío.")

    new_list = UserList(
        user_id=current_user.id,
        name=clean_name,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(new_list)
    await db.commit()
    await db.refresh(new_list)

    return UserListSummaryResponse(
        id=new_list.id,
        name=new_list.name,
        description=new_list.description,
        total_movies=0,
        created_at=new_list.created_at,
        updated_at=new_list.updated_at,
    )


@router.get(
    "/lists/{list_id}",
    response_model=UserListDetailResponse,
    summary="Ver detalle y películas de una lista propia",
)
async def get_user_list_detail(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_list = await _get_owned_list(db, list_id, current_user.id)
    movies = [item.movie for item in user_list.items if item.movie is not None]
    return UserListDetailResponse(
        id=user_list.id,
        name=user_list.name,
        description=user_list.description,
        total_movies=len(movies),
        movies=movies,
        created_at=user_list.created_at,
        updated_at=user_list.updated_at,
    )


@router.patch(
    "/lists/{list_id}",
    response_model=UserListSummaryResponse,
    summary="Renombrar o actualizar una lista propia",
)
async def update_user_list(
    list_id: int,
    payload: UserListUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_list = await _get_owned_list(db, list_id, current_user.id)

    if payload.name is not None:
        clean_name = payload.name.strip()
        if not clean_name:
            raise HTTPException(status_code=422, detail="El nombre de la lista no puede estar vacío.")
        user_list.name = clean_name

    if payload.description is not None:
        user_list.description = payload.description.strip() or None

    await db.commit()
    await db.refresh(user_list)

    return UserListSummaryResponse(
        id=user_list.id,
        name=user_list.name,
        description=user_list.description,
        total_movies=len(user_list.items),
        created_at=user_list.created_at,
        updated_at=user_list.updated_at,
    )


@router.delete(
    "/lists/{list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una lista propia",
)
async def delete_user_list(
    list_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_list = await _get_owned_list(db, list_id, current_user.id)
    await db.delete(user_list)
    await db.commit()
    return None


@router.put(
    "/lists/{list_id}/movies/{movie_id}",
    response_model=ListMovieActionResponse,
    summary="Agregar película a una lista propia (idempotente)",
)
async def add_movie_to_list(
    list_id: int,
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_list(db, list_id, current_user.id)
    await _ensure_movie_exists(db, movie_id)

    existing = (
        await db.execute(
            select(UserListItem).where(
                UserListItem.list_id == list_id,
                UserListItem.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        return ListMovieActionResponse(
            list_id=list_id,
            movie_id=movie_id,
            in_list=True,
            detail="La película ya estaba en esta lista.",
        )

    db.add(UserListItem(list_id=list_id, movie_id=movie_id))
    await db.commit()

    return ListMovieActionResponse(
        list_id=list_id,
        movie_id=movie_id,
        in_list=True,
        detail="Película agregada a la lista.",
    )


@router.delete(
    "/lists/{list_id}/movies/{movie_id}",
    response_model=ListMovieActionResponse,
    summary="Retirar película de una lista propia (idempotente)",
)
async def remove_movie_from_list(
    list_id: int,
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_list(db, list_id, current_user.id)

    existing = (
        await db.execute(
            select(UserListItem).where(
                UserListItem.list_id == list_id,
                UserListItem.movie_id == movie_id,
            )
        )
    ).scalar_one_or_none()

    if not existing:
        return ListMovieActionResponse(
            list_id=list_id,
            movie_id=movie_id,
            in_list=False,
            detail="La película no estaba en esta lista.",
        )

    await db.delete(existing)
    await db.commit()

    return ListMovieActionResponse(
        list_id=list_id,
        movie_id=movie_id,
        in_list=False,
        detail="Película retirada de la lista.",
    )