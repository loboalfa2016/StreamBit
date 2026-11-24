from datetime import date, datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, JSON, text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.catalog import movie_genres, movie_countries


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, nullable=True, index=True)  # ID de TMDB
    title = Column(String(255), index=True, nullable=False)
    synopsis = Column(Text, nullable=True)
    release_date = Column(Date, nullable=True, index=True)
    duration_minutes = Column(Integer, nullable=True)
    age_rating = Column(String(20), nullable=True)
    poster_url = Column(String(500), nullable=True)
    original_language = Column(String(10), nullable=True, index=True)
    director = Column(String(255), nullable=True, index=True)
    cast = Column(JSON, default=list, nullable=True)
    is_available = Column(Boolean, default=False, nullable=False, index=True)
    is_published = Column(Boolean, default=True, server_default=text("true"), nullable=False, index=True)
    is_featured = Column(Boolean, default=False, server_default=text("false"), nullable=False, index=True)
    is_indie = Column(Boolean, default=False, server_default=text("false"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    genres = relationship("Genre", secondary=movie_genres, backref="movies")
    countries = relationship("Country", secondary=movie_countries, backref="movies")
    sources = relationship("Source", back_populates="movie", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="movie", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="movie", cascade="all, delete-orphan")
    availability_logs = relationship(
        "MovieAvailabilityLog",
        back_populates="movie",
        cascade="all, delete-orphan",
    )

    @property
    def availability_status(self) -> str:
        return "Disponible" if self.is_available else "Próximamente"