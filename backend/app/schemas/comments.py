from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class CommentCreateRequest(BaseModel):
    content: str
    guest_name: Optional[str] = None
    parent_id: Optional[int] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2 or len(cleaned) > 1000:
            raise ValueError("El comentario debe tener entre 2 y 1000 caracteres.")
        return cleaned

    @field_validator("guest_name")
    @classmethod
    def validate_guest_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 50:
            raise ValueError("El nombre de visitante no puede superar 50 caracteres.")
        return cleaned


class CommentReplyResponse(BaseModel):
    id: int
    movie_id: int
    parent_id: Optional[int] = None
    author_name: str
    is_registered_user: bool
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(CommentReplyResponse):
    replies: list[CommentReplyResponse] = []
    replies_count: int = 0


class CommentListResponse(BaseModel):
    items: list[CommentResponse]
    total: int
    page: int
    page_size: int
