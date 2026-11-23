from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class MovieAvailabilityLog(Base):
    __tablename__ = "movie_availability_logs"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_is_available = Column(Boolean, nullable=False)
    new_is_available = Column(Boolean, nullable=False)
    previous_status = Column(String(30), nullable=False)  # "Disponible" | "Próximamente"
    new_status = Column(String(30), nullable=False)       # "Disponible" | "Próximamente"
    reason = Column(Text, nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    movie = relationship("Movie", back_populates="availability_logs")