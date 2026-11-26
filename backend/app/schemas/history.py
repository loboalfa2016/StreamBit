from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class PlaybackEventCreate(BaseModel):
    movie_id: int
    source_id: Optional[int] = None
    event: Literal["started", "progress", "paused", "completed_verified", "error"] = "started"
    position_seconds: Optional[int] = Field(default=None, ge=0)
    duration_seconds: Optional[int] = Field(default=None, gt=0)
    provider_verified: bool = False


class WatchHistoryMovieSummary(BaseModel):
    id: int
    title: str
    poster_url: Optional[str] = None
    release_date: Optional[date] = None
    availability_status: str

    model_config = ConfigDict(from_attributes=True)


class WatchHistoryItemResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    source_id: Optional[int] = None
    last_event: str
    position_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    is_completed_verified: bool
    started_at: datetime
    last_watched_at: datetime
    movie: WatchHistoryMovieSummary

    model_config = ConfigDict(from_attributes=True)


class WatchHistoryListResponse(BaseModel):
    items: list[WatchHistoryItemResponse]
    total: int
    page: int
    page_size: int
