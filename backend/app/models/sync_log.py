from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), default="tmdb", nullable=False)
    trigger = Column(String(20), nullable=False)  # "scheduled" o "manual"
    status = Column(String(20), nullable=False)   # "success" o "error"
    created_count = Column(Integer, default=0, nullable=False)
    updated_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    executed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )