from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class PublicProviderResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)


class PlaybackOptionResponse(BaseModel):
    source_id: int
    provider: PublicProviderResponse
    resource_identifier: str
    languages: List[str] = []
    audio_type: Optional[str] = None
    subtitles: List[str] = []
    territories: List[str] = []
    expires_at: Optional[datetime] = None


class MoviePlaybackOptionsResponse(BaseModel):
    movie_id: int
    title: str
    is_available: bool
    availability_status: str
    territory_applied: Optional[str] = None
    total_options: int
    options: List[PlaybackOptionResponse] = []