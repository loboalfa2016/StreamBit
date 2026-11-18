from sqlalchemy import Column, Integer, String, Text, Boolean
from app.core.database import Base

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True, nullable=False)
    synopsis = Column(Text, nullable=True)
    is_available = Column(Boolean, default=False) # Representa "Disponible" o "Próximamente"