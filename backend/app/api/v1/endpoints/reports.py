from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.ads import AdCampaign, AdImpression
from app.models.community import Comment, Rating
from app.models.moderation import CommentReport
from app.models.movie import Movie
from app.models.user import User
from app.models.watch_history import WatchHistory
from app.schemas.reports import (
    AdsMetrics,
    AdsPerformanceReportResponse,
    CampaignPerformanceItem,
    CatalogMetrics,
    CommunityMetrics,
    OverviewReportResponse,
    PlaybackMetrics,
    TopMovieMetricItem,
    TopMoviesReportResponse,
)

router = APIRouter(prefix="/admin/reports", tags=["Reports"])

OVERVIEW_DEFINITIONS: dict[str, str] = {
    "catalog.available_movies": "Películas publicadas con al menos una fuente activa y verificada (is_available=True).",
    "playback.verified_starts_count": "Entradas registradas en watch_history dentro del periodo.",
    "playback.verified_completions_count": "Reproducciones completadas únicamente cuando el proveedor lo confirmó explícitamente (is_completed_verified=True).",
    "ads.total_valid_impressions": "Impresiones pre-roll válidas (is_valid=True, sin duplicados de sesión).",
    "ads.estimated_revenue_usd": "Ingreso estimado calculado por CPM; NO equivale a ingreso confirmado ni facturado.",
    "ads.confirmed_revenue_usd": "Ingreso real confirmado explícitamente por administración (is_revenue_confirmed=True).",
}


def _validate_date_range(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from no puede ser mayor que date_to.",
        )


def _date_filters(column, date_from: Optional[datetime], date_to: Optional[datetime]) -> list:
    filters = []
    if date_from is not None:
        filters.append(column >= date_from)
    if date_to is not None:
        filters.append(column <= date_to)
    return filters


@router.get(
    "/overview",
    response_model=OverviewReportResponse,
    summary="Resumen general de métricas operativas (solo lectura)",
)
async def get_overview_report(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    _: User = Depends(require_permission("view_analytics")),
    db: AsyncSession = Depends(get_db),
):
    _validate_date_range(date_from, date_to)

    # Catálogo (estado actual)
    total_movies = (await db.execute(select(func.count(Movie.id)))).scalar_one()
    published_movies = (
        await db.execute(select(func.count(Movie.id)).where(Movie.is_published.is_(True)))
    ).scalar_one()
    available_movies = (
        await db.execute(
            select(func.count(Movie.id)).where(
                Movie.is_published.is_(True), Movie.is_available.is_(True)
            )
        )
    ).scalar_one()
    coming_soon_movies = (
        await db.execute(
            select(func.count(Movie.id)).where(
                Movie.is_published.is_(True), Movie.is_available.is_(False)
            )
        )
    ).scalar_one()

    # Reproducciones (watch_history)
    wh_filters = _date_filters(WatchHistory.last_watched_at, date_from, date_to)
    verified_starts_count = (
        await db.execute(select(func.count(WatchHistory.id)).where(*wh_filters))
    ).scalar_one()
    verified_completions_count = (
        await db.execute(
            select(func.count(WatchHistory.id)).where(
                *wh_filters, WatchHistory.is_completed_verified.is_(True)
            )
        )
    ).scalar_one()

    # Comunidad
    rating_filters = _date_filters(Rating.created_at, date_from, date_to)
    avg_rating_val, total_ratings = (
        await db.execute(
            select(func.avg(Rating.score), func.count(Rating.id)).where(*rating_filters)
        )
    ).one()
    average_rating = (
        round(float(avg_rating_val), 2)
        if total_ratings > 0 and avg_rating_val is not None
        else None
    )

    comment_filters = _date_filters(Comment.created_at, date_from, date_to)
    total_visible_comments = (
        await db.execute(
            select(func.count(Comment.id)).where(
                *comment_filters, Comment.is_hidden.is_(False)
            )
        )
    ).scalar_one()

    report_filters = _date_filters(CommentReport.created_at, date_from, date_to)
    pending_reports_count = (
        await db.execute(
            select(func.count(CommentReport.id)).where(
                *report_filters, CommentReport.status == "pending"
            )
        )
    ).scalar_one()

    # Publicidad
    ad_filters = _date_filters(AdImpression.created_at, date_from, date_to)
    total_valid_impressions = (
        await db.execute(
            select(func.count(AdImpression.id)).where(
                *ad_filters,
                AdImpression.event_type == "impression",
                AdImpression.is_valid.is_(True),
            )
        )
    ).scalar_one()
    total_completed_ads = (
        await db.execute(
            select(func.count(AdImpression.id)).where(
                *ad_filters, AdImpression.event_type == "completed"
            )
        )
    ).scalar_one()
    total_clicks = (
        await db.execute(
            select(func.count(AdImpression.id)).where(
                *ad_filters, AdImpression.event_type == "click"
            )
        )
    ).scalar_one()
    estimated_sum = (
        await db.execute(
            select(func.coalesce(func.sum(AdImpression.estimated_revenue_usd), 0)).where(
                *ad_filters, AdImpression.is_valid.is_(True)
            )
        )
    ).scalar_one()
    confirmed_sum = (
        await db.execute(
            select(func.coalesce(func.sum(AdImpression.confirmed_revenue_usd), 0)).where(
                *ad_filters, AdImpression.is_revenue_confirmed.is_(True)
            )
        )
    ).scalar_one()

    return OverviewReportResponse(
        date_from=date_from,
        date_to=date_to,
        catalog=CatalogMetrics(
            total_movies=int(total_movies),
            published_movies=int(published_movies),
            available_movies=int(available_movies),
            coming_soon_movies=int(coming_soon_movies),
        ),
        playback=PlaybackMetrics(
            verified_starts_count=int(verified_starts_count),
            verified_completions_count=int(verified_completions_count),
        ),
        community=CommunityMetrics(
            total_ratings=int(total_ratings),
            average_rating=average_rating,
            total_visible_comments=int(total_visible_comments),
            pending_reports_count=int(pending_reports_count),
        ),
        ads=AdsMetrics(
            total_valid_impressions=int(total_valid_impressions),
            total_completed_ads=int(total_completed_ads),
            total_clicks=int(total_clicks),
            estimated_revenue_usd=round(float(estimated_sum), 4),
            confirmed_revenue_usd=round(float(confirmed_sum), 4),
        ),
        metric_definitions=OVERVIEW_DEFINITIONS,
    )


@router.get(
    "/top-movies",
    response_model=TopMoviesReportResponse,
    summary="Top de películas por reproducciones iniciadas y completadas verificadas",
)
async def get_top_movies_report(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_permission("view_analytics")),
    db: AsyncSession = Depends(get_db),
):
    _validate_date_range(date_from, date_to)

    wh_filters = _date_filters(WatchHistory.last_watched_at, date_from, date_to)
    starts_col = func.count(WatchHistory.id).label("starts_count")
    completions_col = func.sum(
        case((WatchHistory.is_completed_verified.is_(True), 1), else_=0)
    ).label("verified_completions_count")

    top_stmt = (
        select(
            Movie.id,
            Movie.title,
            Movie.is_available,
            starts_col,
            completions_col,
        )
        .join(WatchHistory, WatchHistory.movie_id == Movie.id)
        .where(*wh_filters)
        .group_by(Movie.id, Movie.title, Movie.is_available)
        .order_by(desc(starts_col), desc(completions_col), Movie.id.asc())
        .limit(limit)
    )
    rows = (await db.execute(top_stmt)).all()

    movie_ids = [r[0] for r in rows]
    rating_map: dict[int, tuple[Optional[float], int]] = {}
    if movie_ids:
        rating_rows = (
            await db.execute(
                select(
                    Rating.movie_id,
                    func.avg(Rating.score),
                    func.count(Rating.id),
                )
                .where(Rating.movie_id.in_(movie_ids))
                .group_by(Rating.movie_id)
            )
        ).all()
        rating_map = {
            r[0]: (round(float(r[1]), 2) if r[1] is not None else None, int(r[2]))
            for r in rating_rows
        }

    items = []
    for mid, title, is_avail, starts, completions in rows:
        avg_r, cnt_r = rating_map.get(mid, (None, 0))
        items.append(
            TopMovieMetricItem(
                movie_id=mid,
                title=title,
                availability_status="Disponible" if is_avail else "Próximamente",
                starts_count=int(starts or 0),
                verified_completions_count=int(completions or 0),
                average_rating=avg_r,
                ratings_count=cnt_r,
            )
        )

    return TopMoviesReportResponse(
        date_from=date_from,
        date_to=date_to,
        items=items,
        metric_definitions={
            "starts_count": "Cantidad de usuarios únicos con actividad registrada en watch_history en el periodo.",
            "verified_completions_count": "Cantidad de usuarios con finalización confirmada por el proveedor (is_completed_verified=True).",
            "average_rating": "Promedio histórico de calificaciones (1 a 5) de la película.",
        },
    )


@router.get(
    "/ads-performance",
    response_model=AdsPerformanceReportResponse,
    summary="Desempeño e ingresos estimados vs confirmados por campaña publicitaria",
)
async def get_ads_performance_report(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    _: User = Depends(require_permission("view_ads_reports")),
    db: AsyncSession = Depends(get_db),
):
    _validate_date_range(date_from, date_to)

    join_conditions = [AdImpression.campaign_id == AdCampaign.id]
    join_conditions.extend(_date_filters(AdImpression.created_at, date_from, date_to))

    valid_imp_col = func.coalesce(
        func.sum(
            case(
                (
                    and_(
                        AdImpression.event_type == "impression",
                        AdImpression.is_valid.is_(True),
                    ),
                    1,
                ),
                else_=0,
            )
        ),
        0,
    ).label("valid_impressions")

    completed_col = func.coalesce(
        func.sum(case((AdImpression.event_type == "completed", 1), else_=0)),
        0,
    ).label("completed_ads")

    clicks_col = func.coalesce(
        func.sum(case((AdImpression.event_type == "click", 1), else_=0)),
        0,
    ).label("clicks")

    est_rev_col = func.coalesce(
        func.sum(
            case(
                (AdImpression.is_valid.is_(True), AdImpression.estimated_revenue_usd),
                else_=0,
            )
        ),
        0,
    ).label("estimated_revenue_usd")

    conf_rev_col = func.coalesce(
        func.sum(
            case(
                (
                    AdImpression.is_revenue_confirmed.is_(True),
                    AdImpression.confirmed_revenue_usd,
                ),
                else_=0,
            )
        ),
        0,
    ).label("confirmed_revenue_usd")

    stmt = (
        select(
            AdCampaign.id,
            AdCampaign.name,
            AdCampaign.advertiser_name,
            valid_imp_col,
            completed_col,
            clicks_col,
            est_rev_col,
            conf_rev_col,
        )
        .outerjoin(AdImpression, and_(*join_conditions))
        .group_by(AdCampaign.id, AdCampaign.name, AdCampaign.advertiser_name)
        .order_by(desc(valid_imp_col), AdCampaign.id.asc())
    )
    rows = (await db.execute(stmt)).all()

    items = [
        CampaignPerformanceItem(
            campaign_id=cid,
            campaign_name=cname,
            advertiser_name=adv,
            valid_impressions=int(v_imp),
            completed_ads=int(comp),
            clicks=int(clk),
            estimated_revenue_usd=round(float(est), 4),
            confirmed_revenue_usd=round(float(conf), 4),
        )
        for cid, cname, adv, v_imp, comp, clk, est, conf in rows
    ]

    total_est = round(sum(item.estimated_revenue_usd for item in items), 4)
    total_conf = round(sum(item.confirmed_revenue_usd for item in items), 4)

    return AdsPerformanceReportResponse(
        date_from=date_from,
        date_to=date_to,
        items=items,
        total_estimated_revenue_usd=total_est,
        total_confirmed_revenue_usd=total_conf,
        metric_definitions={
            "valid_impressions": "Impresiones pre-roll válidas (is_valid=True), excluyendo duplicados de sesión.",
            "estimated_revenue_usd": "Ingreso estimado por CPM; no representa dinero cobrado ni confirmado.",
            "confirmed_revenue_usd": "Ingreso confirmado explícitamente en facturación/operación (is_revenue_confirmed=True).",
        },
    )
