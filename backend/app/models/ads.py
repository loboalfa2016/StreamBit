from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"
    __table_args__ = (
        CheckConstraint("placement = 'pre_roll'", name="check_ad_placement_preroll"),
        CheckConstraint(
            "duration_seconds >= 15 AND duration_seconds <= 30",
            name="check_ad_duration_range",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    advertiser_name = Column(String(150), nullable=False)
    placement = Column(
        String(30),
        default="pre_roll",
        server_default=text("'pre_roll'"),
        nullable=False,
    )
    media_url = Column(String(500), nullable=False)
    click_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=False)
    cpm_estimated_usd = Column(
        Numeric(10, 4),
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    target_countries = Column(JSON, nullable=True)
    is_active = Column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        index=True,
    )
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), nullable=True)

    impressions = relationship(
        "AdImpression",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class AdImpression(Base):
    __tablename__ = "ad_impressions"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(
        Integer,
        ForeignKey("ad_campaigns.id", ondelete="CASCADE"),
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
        index=True,
    )
    playback_session_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    is_valid = Column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    estimated_revenue_usd = Column(
        Numeric(10, 4),
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    confirmed_revenue_usd = Column(
        Numeric(10, 4),
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    is_revenue_confirmed = Column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    campaign = relationship("AdCampaign", back_populates="impressions")
    movie = relationship("Movie")
    source = relationship("Source")
