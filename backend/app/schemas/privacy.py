from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PrivacyPolicyResponse(BaseModel):
    version: str
    last_updated: str
    data_collected: dict[str, str]
    retention_policy: dict[str, int]
    user_rights: list[dict[str, str]]
    regional_compliance_notes: str


class UserProfileExport(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_verified: bool
    created_at: datetime
    notify_availability: bool
    notify_comment_replies: bool

    model_config = ConfigDict(from_attributes=True)


class UserDataExportResponse(BaseModel):
    exported_at: datetime
    profile: UserProfileExport
    favorites: list[dict[str, Any]]
    lists: list[dict[str, Any]]
    watch_history: list[dict[str, Any]]
    ratings: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    availability_alerts: list[dict[str, Any]]
    notifications: list[dict[str, Any]]


class UserProfileRectifyRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)


class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1)
    confirm: bool


class RetentionCleanupResponse(BaseModel):
    deleted_history_records: int
    deleted_read_notifications: int
    executed_at: datetime
