from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminMovieUpdateRequest(BaseModel):
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_indie: Optional[bool] = None
    age_rating: Optional[str] = Field(default=None, max_length=20)


class AdminMovieListItem(BaseModel):
    id: int
    external_id: Optional[str] = None
    title: str
    director: Optional[str] = None
    release_date: Optional[date] = None
    age_rating: Optional[str] = None
    is_available: bool
    is_published: bool
    is_featured: bool
    is_indie: bool
    availability_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminMovieListResponse(BaseModel):
    items: list[AdminMovieListItem]
    total: int
    page: int
    page_size: int


class AdminUserStatusUpdateRequest(BaseModel):
    is_active: bool


class AdminUserListItem(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_verified: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminBroadcastNotificationRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5, max_length=1000)
    movie_id: Optional[int] = None
    target_user_ids: Optional[list[int]] = None


class AdminAuditLogResponse(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogResponse]
    total: int
    page: int
    page_size: int
