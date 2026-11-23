from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class Provider(Base):
    __tablename__ = "providers"
    __table_args__ = (UniqueConstraint("name", name="uq_providers_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, index=True, nullable=False)
    base_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sources = relationship("Source", back_populates="provider")
