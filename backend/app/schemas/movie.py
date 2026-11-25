from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, computed_field


class GenreResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class CountryResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MovieResponse(BaseModel):
    id: int
    external_id: str | None = None
    title: str
    synopsis: str | None = None
    release_date: date | None = None
    duration_minutes: int | None = None
    age_rating: str | None = None
    poster_url: str | None = None
    original_language: str | None = None
    director: str | None = None
    is_available: bool
    genres: list[GenreResponse] = []
    countries: list[CountryResponse] = []
    cast: list[str] | None = None
    created_at: datetime

    @computed_field
    @property
    def availability_status(self) -> str:
        return "Disponible" if self.is_available else "Próximamente"

    model_config = ConfigDict(from_attributes=True)


class PaginatedMoviesResponse(BaseModel):
    items: list[MovieResponse]
    total: int
    page: int
    page_size: int
    total_pages: int