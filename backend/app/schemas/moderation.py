from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class CommentReportCreateRequest(BaseModel):
    reason: Literal[
        "spam",
        "harassment",
        "hate_speech",
        "spoilers",
        "inappropriate",
        "other",
    ]
    details: Optional[str] = Field(default=None, max_length=500)


class CommentReportResponse(BaseModel):
    id: int
    comment_id: int
    reason: str
    details: Optional[str] = None
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class CommentReportListResponse(BaseModel):
    items: list[CommentReportResponse]
    total: int
    page: int
    page_size: int


class ModerationActionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class ModerationLogResponse(BaseModel):
    id: int
    comment_id: Optional[int] = None
    admin_user_id: Optional[int] = None
    action: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModerationLogListResponse(BaseModel):
    items: list[ModerationLogResponse]
    total: int
    page: int
    page_size: int
