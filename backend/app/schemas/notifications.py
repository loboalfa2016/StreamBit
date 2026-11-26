from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AvailabilityAlertResponse(BaseModel):
    movie_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    movie_id: Optional[int] = None
    comment_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationPreferencesResponse(BaseModel):
    notify_availability: bool
    notify_comment_replies: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferencesUpdate(BaseModel):
    notify_availability: Optional[bool] = None
    notify_comment_replies: Optional[bool] = None
