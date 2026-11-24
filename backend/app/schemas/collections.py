from typing import Optional
from pydantic import BaseModel
from app.schemas.movie import MovieResponse


class FeaturedMovieResponse(BaseModel):
    movie: Optional[MovieResponse] = None
    selection_rule: str


class CatalogCollectionResponse(BaseModel):
    slug: str
    title: str
    ordering_rule: str
    total: int
    items: list[MovieResponse] = []


class CatalogCollectionsResponse(BaseModel):
    featured: Optional[MovieResponse] = None
    collections: list[CatalogCollectionResponse] = []