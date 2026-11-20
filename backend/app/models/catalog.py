from sqlalchemy import Column,  Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
) 
movie_countries = Table(
    "movie_countries",
    Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("country_id", Integer, ForeignKey("countries.id", ondelete="CASCADE"), primary_key=True),
) 
class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(15), unique=True, nullable=False, index=True)  # Ej: es-419, es-ES, en
    name = Column(String(100), nullable=False)
