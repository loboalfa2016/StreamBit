from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CatalogMetrics(BaseModel):
    total_movies: int
    published_movies: int
    available_movies: int
    coming_soon_movies: int


class PlaybackMetrics(BaseModel):
    verified_starts_count: int
    verified_completions_count: int


class CommunityMetrics(BaseModel):
    total_ratings: int
    average_rating: Optional[float] = None
    total_visible_comments: int
    pending_reports_count: int


class AdsMetrics(BaseModel):
    total_valid_impressions: int
    total_completed_ads: int
    total_clicks: int
    estimated_revenue_usd: float
    confirmed_revenue_usd: float


class OverviewReportResponse(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    catalog: CatalogMetrics
    playback: PlaybackMetrics
    community: CommunityMetrics
    ads: AdsMetrics
    metric_definitions: dict[str, str]


class TopMovieMetricItem(BaseModel):
    movie_id: int
    title: str
    availability_status: str
    starts_count: int
    verified_completions_count: int
    average_rating: Optional[float] = None
    ratings_count: int


class TopMoviesReportResponse(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    items: list[TopMovieMetricItem]
    metric_definitions: dict[str, str]


class CampaignPerformanceItem(BaseModel):
    campaign_id: int
    campaign_name: str
    advertiser_name: str
    valid_impressions: int
    completed_ads: int
    clicks: int
    estimated_revenue_usd: float
    confirmed_revenue_usd: float


class AdsPerformanceReportResponse(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    items: list[CampaignPerformanceItem]
    total_estimated_revenue_usd: float
    total_confirmed_revenue_usd: float
    metric_definitions: dict[str, str]
