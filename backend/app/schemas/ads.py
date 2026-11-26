from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class AdCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    advertiser_name: str = Field(..., min_length=1, max_length=150)
    media_url: str = Field(..., min_length=1, max_length=500)
    click_url: Optional[str] = Field(default=None, max_length=500)
    duration_seconds: int = Field(..., ge=15, le=30)
    cpm_estimated_usd: float = Field(default=0.0, ge=0)
    target_countries: Optional[list[str]] = None
    is_active: bool = True
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class AdCampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    advertiser_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    media_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    click_url: Optional[str] = Field(default=None, max_length=500)
    duration_seconds: Optional[int] = Field(default=None, ge=15, le=30)
    cpm_estimated_usd: Optional[float] = Field(default=None, ge=0)
    target_countries: Optional[list[str]] = None
    is_active: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class AdCampaignResponse(BaseModel):
    id: int
    name: str
    advertiser_name: str
    placement: str
    media_url: str
    click_url: Optional[str] = None
    duration_seconds: int
    cpm_estimated_usd: float
    target_countries: Optional[list[str]] = None
    is_active: bool
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdCampaignListResponse(BaseModel):
    items: list[AdCampaignResponse]
    total: int
    page: int
    page_size: int


class PublicPrerollAd(BaseModel):
    campaign_id: int
    media_url: str
    click_url: Optional[str] = None
    duration_seconds: int
    placement: str


class PrerollAdDecisionResponse(BaseModel):
    show_ad: bool
    reason: str
    ad: Optional[PublicPrerollAd] = None


class AdImpressionCreate(BaseModel):
    campaign_id: int
    movie_id: int
    source_id: Optional[int] = None
    playback_session_id: str = Field(..., min_length=4, max_length=100)
    event_type: Literal["impression", "completed", "skipped", "error", "click"]


class AdImpressionResponse(BaseModel):
    id: int
    campaign_id: int
    movie_id: int
    source_id: Optional[int] = None
    playback_session_id: str
    event_type: str
    is_valid: bool
    estimated_revenue_usd: float
    confirmed_revenue_usd: float
    is_revenue_confirmed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfirmRevenueRequest(BaseModel):
    confirmed_revenue_usd: float = Field(..., ge=0)


class AdsSummaryReportResponse(BaseModel):
    total_valid_impressions: int
    total_completed: int
    total_clicks: int
    estimated_revenue_usd: float
    confirmed_revenue_usd: float
