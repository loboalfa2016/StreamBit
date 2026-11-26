from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel


class RecommendedMovieItem(BaseModel):
    id: int
    title: str
    poster_url: Optional[str] = None
    release_date: Optional[date] = None
    availability_status: str
    genres: list[str]
    average_score: Optional[float] = None
    ratings_count: int
    recommendation_reason: str


class RecommendationsResponse(BaseModel):
    strategy: Literal["personalized", "general", "general_fallback"]
    explanation: str
    items: list[RecommendedMovieItem]
    total: int
