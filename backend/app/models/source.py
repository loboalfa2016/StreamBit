from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer,
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    resource_identifier = Column(String(500), nullable=False)
    territories = Column(JSON, default=list, nullable=False)
    languages = Column(JSON, default=list, nullable=False)
    subtitles = Column(JSON, default=list, nullable=False)
    audio_type = Column(String(50), nullable=True)  # Ej: "Latino", "Subtitulado", "Original"
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    authorization_reference = Column(String(255), nullable=False)
    authorization_terms = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False, index=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    movie = relationship("Movie", back_populates="sources")
    provider = relationship("Provider", back_populates="sources")
    created_by_user = relationship("User")