from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RatingCreateRequest(BaseModel):
    score: int = Field(..., ge=1, le=5)


class RatingResponse(BaseModel):
    id: int
    movie_id: int
    score: int
    is_registered_user: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MovieRatingSummaryResponse(BaseModel):
    movie_id: int
    average_score: Optional[float] = None
    ratings_count: int
    my_rating: Optional[int] = None
