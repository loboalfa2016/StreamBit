from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class WatchHistory(Base):
    __tablename__ = "watch_history"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_watch_history_user_movie"),
        CheckConstraint(
            "position_seconds IS NULL OR position_seconds >= 0",
            name="check_watch_history_position_non_negative",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="check_watch_history_duration_positive",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movie_id = Column(
        Integer,
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id = Column(
        Integer,
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_event = Column(String(50), default="started", nullable=False)
    position_seconds = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    is_completed_verified = Column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_watched_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    user = relationship("User")
    movie = relationship("Movie")
    source = relationship("Source")
