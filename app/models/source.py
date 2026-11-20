from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False)
    resource_url = Column(String(500), nullable=False)
    audio_language_id = Column(Integer, ForeignKey("languages.id"), nullable=True)
    subtitle_language_id = Column(Integer, ForeignKey("languages.id"), nullable=True)
    authorization_ref = Column(Text, nullable=True)  # Evidencia o referencia de autorización
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    movie = relationship("Movie", back_populates="sources")
    audio_language = relationship("Language", foreign_keys=[audio_language_id])
    subtitle_language = relationship("Language", foreign_keys=[subtitle_language_id])