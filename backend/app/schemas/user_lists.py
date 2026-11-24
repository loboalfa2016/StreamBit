from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.movie import MovieResponse


class FavoriteActionResponse(BaseModel):
    movie_id: int
    is_favorite: bool
    detail: str


class FavoriteItemResponse(BaseModel):
    movie_id: int
    created_at: datetime
    movie: MovieResponse

    model_config = ConfigDict(from_attributes=True)


class UserListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Nombre de la lista")
    description: Optional[str] = Field(None, max_length=500)


class UserListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class UserListSummaryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    total_movies: int
    created_at: datetime
    updated_at: datetime


class UserListDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    total_movies: int
    movies: list[MovieResponse] = []
    created_at: datetime
    updated_at: datetime


class ListMovieActionResponse(BaseModel):
    list_id: int
    movie_id: int
    in_list: bool
    detail: str