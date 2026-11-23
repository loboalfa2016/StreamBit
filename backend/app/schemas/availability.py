from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AvailabilityEvaluateRequest(BaseModel):
    reason: Optional[str] = "Evaluación manual de disponibilidad"


class AvailabilityLogResponse(BaseModel):
    id: int
    movie_id: int
    previous_is_available: bool
    new_is_available: bool
    previous_status: str
    new_status: str
    reason: str
    changed_by_user_id: Optional[int] = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MovieAvailabilityResponse(BaseModel):
    movie_id: int
    title: str
    is_available: bool
    availability_status: str
    valid_sources_count: int
    status_changed: bool
    log: Optional[AvailabilityLogResponse] = None