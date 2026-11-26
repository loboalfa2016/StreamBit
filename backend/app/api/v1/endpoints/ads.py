from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.ads import AdCampaign, AdImpression
from app.models.movie import Movie
from app.models.source import Source
from app.models.user import User
from app.schemas.ads import (
    AdCampaignCreate,
    AdCampaignListResponse,
    AdCampaignResponse,
    AdCampaignUpdate,
    AdImpressionCreate,
    AdImpressionResponse,
    AdsSummaryReportResponse,
    ConfirmRevenueRequest,
    PrerollAdDecisionResponse,
    PublicPrerollAd,
)

router = APIRouter(tags=["Ads"])


@router.get(
    "/ads/preroll",
    response_model=PrerollAdDecisionResponse,
    summary="Evaluar y obtener un anuncio pre-roll antes de iniciar reproducción",
)
async def get_preroll_ad(
    movie_id: int = Query(...),
    source_id: int = Query(...),
    playback_session_id: str = Query(..., min_length=4, max_length=100),
    country: Optional[str] = Query(default=None, min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db),
):
    movie_exists = (
        await db.execute(select(Movie.id).where(Movie.id == movie_id))
    ).scalar_one_or_none()
    if not movie_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    source = (
        await db.execute(
            select(Source)
            .options(selectinload(Source.provider))
            .where(Source.id == source_id)
        )
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fuente de reproducción no encontrada.",
        )
    if source.movie_id != movie_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fuente no pertenece a la película indicada.",
        )

    if not source.provider or not source.provider.allows_preroll_ads:
        return PrerollAdDecisionResponse(
            show_ad=False,
            reason="El proveedor de la fuente no permite publicidad pre-roll.",
            ad=None,
        )

    existing_impression = (
        await db.execute(
            select(AdImpression.id).where(
                AdImpression.playback_session_id == playback_session_id,
                AdImpression.movie_id == movie_id,
                AdImpression.event_type == "impression",
                AdImpression.is_valid.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing_impression is not None:
        return PrerollAdDecisionResponse(
            show_ad=False,
            reason="Ya se registró un anuncio pre-roll en esta sesión de reproducción.",
            ad=None,
        )

    now = datetime.now(timezone.utc)
    campaigns_stmt = (
        select(AdCampaign)
        .where(
            AdCampaign.is_active.is_(True),
            AdCampaign.placement == "pre_roll",
        )
        .order_by(desc(AdCampaign.cpm_estimated_usd), desc(AdCampaign.id))
    )
    campaigns = list((await db.execute(campaigns_stmt)).scalars().all())

    normalized_country = country.upper() if country else None
    selected_campaign: Optional[AdCampaign] = None
    for campaign in campaigns:
        if campaign.starts_at and campaign.starts_at > now:
            continue
        if campaign.ends_at and campaign.ends_at < now:
            continue
        if campaign.target_countries:
            allowed = {c.upper() for c in campaign.target_countries}
            if normalized_country is None or normalized_country not in allowed:
                continue
        selected_campaign = campaign
        break

    if not selected_campaign:
        return PrerollAdDecisionResponse(
            show_ad=False,
            reason="No hay campañas pre-roll activas disponibles para este contexto.",
            ad=None,
        )

    return PrerollAdDecisionResponse(
        show_ad=True,
        reason="Anuncio pre-roll disponible.",
        ad=PublicPrerollAd(
            campaign_id=selected_campaign.id,
            media_url=selected_campaign.media_url,
            click_url=selected_campaign.click_url,
            duration_seconds=selected_campaign.duration_seconds,
            placement=selected_campaign.placement,
        ),
    )


@router.post(
    "/ads/impressions",
    response_model=AdImpressionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar impresión o evento de anuncio pre-roll",
)
async def record_ad_impression(
    payload: AdImpressionCreate,
    db: AsyncSession = Depends(get_db),
):
    campaign = (
        await db.execute(select(AdCampaign).where(AdCampaign.id == payload.campaign_id))
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaña publicitaria no encontrada.",
        )

    movie_exists = (
        await db.execute(select(Movie.id).where(Movie.id == payload.movie_id))
    ).scalar_one_or_none()
    if not movie_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )

    source: Optional[Source] = None
    if payload.source_id is not None:
        source = (
            await db.execute(
                select(Source)
                .options(selectinload(Source.provider))
                .where(Source.id == payload.source_id)
            )
        ).scalar_one_or_none()
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fuente de reproducción no encontrada.",
            )
        if source.movie_id != payload.movie_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fuente no pertenece a la película indicada.",
            )

    is_valid = True
    estimated_rev = Decimal("0")

    if payload.event_type == "impression":
        already_recorded = (
            await db.execute(
                select(AdImpression.id).where(
                    AdImpression.playback_session_id == payload.playback_session_id,
                    AdImpression.movie_id == payload.movie_id,
                    AdImpression.event_type == "impression",
                    AdImpression.is_valid.is_(True),
                )
            )
        ).scalar_one_or_none()
        provider_allows = (
            source is None
            or (source.provider is not None and source.provider.allows_preroll_ads)
        )
        if already_recorded is not None or not provider_allows:
            is_valid = False
        else:
            estimated_rev = (Decimal(str(campaign.cpm_estimated_usd)) / Decimal("1000")).quantize(
                Decimal("0.0001")
            )

    impression = AdImpression(
        campaign_id=payload.campaign_id,
        movie_id=payload.movie_id,
        source_id=payload.source_id,
        playback_session_id=payload.playback_session_id,
        event_type=payload.event_type,
        is_valid=is_valid,
        estimated_revenue_usd=estimated_rev,
        confirmed_revenue_usd=Decimal("0"),
        is_revenue_confirmed=False,
    )
    db.add(impression)
    await db.commit()
    await db.refresh(impression)
    return impression


@router.post(
    "/admin/ads/campaigns",
    response_model=AdCampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una campaña publicitaria pre-roll",
)
async def create_ad_campaign(
    payload: AdCampaignCreate,
    _: User = Depends(require_permission("manage_ads")),
    db: AsyncSession = Depends(get_db),
):
    campaign = AdCampaign(**payload.model_dump(), placement="pre_roll")
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get(
    "/admin/ads/campaigns",
    response_model=AdCampaignListResponse,
    summary="Listar campañas publicitarias",
)
async def list_ad_campaigns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("view_ads_reports")),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(AdCampaign.id)))).scalar_one()
    stmt = (
        select(AdCampaign)
        .order_by(desc(AdCampaign.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return AdCampaignListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/admin/ads/campaigns/{campaign_id}",
    response_model=AdCampaignResponse,
    summary="Actualizar una campaña publicitaria",
)
async def update_ad_campaign(
    campaign_id: int,
    payload: AdCampaignUpdate,
    _: User = Depends(require_permission("manage_ads")),
    db: AsyncSession = Depends(get_db),
):
    campaign = (
        await db.execute(select(AdCampaign).where(AdCampaign.id == campaign_id))
    ).scalar_one_or_none()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaña publicitaria no encontrada.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    campaign.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch(
    "/admin/ads/impressions/{impression_id}/confirm-revenue",
    response_model=AdImpressionResponse,
    summary="Confirmar ingreso real de una impresión publicitaria",
)
async def confirm_impression_revenue(
    impression_id: int,
    payload: ConfirmRevenueRequest,
    _: User = Depends(require_permission("manage_ads")),
    db: AsyncSession = Depends(get_db),
):
    impression = (
        await db.execute(select(AdImpression).where(AdImpression.id == impression_id))
    ).scalar_one_or_none()
    if not impression:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Impresión publicitaria no encontrada.",
        )

    impression.confirmed_revenue_usd = Decimal(str(payload.confirmed_revenue_usd))
    impression.is_revenue_confirmed = True

    await db.commit()
    await db.refresh(impression)
    return impression


@router.get(
    "/admin/ads/reports/summary",
    response_model=AdsSummaryReportResponse,
    summary="Resumen de impresiones e ingresos estimados vs confirmados",
)
async def get_ads_summary_report(
    _: User = Depends(require_permission("view_ads_reports")),
    db: AsyncSession = Depends(get_db),
):
    total_valid_impressions = (
        await db.execute(
            select(func.count(AdImpression.id)).where(
                AdImpression.event_type == "impression",
                AdImpression.is_valid.is_(True),
            )
        )
    ).scalar_one()

    total_completed = (
        await db.execute(
            select(func.count(AdImpression.id)).where(
                AdImpression.event_type == "completed"
            )
        )
    ).scalar_one()

    total_clicks = (
        await db.execute(
            select(func.count(AdImpression.id)).where(
                AdImpression.event_type == "click"
            )
        )
    ).scalar_one()

    estimated_sum = (
        await db.execute(
            select(func.coalesce(func.sum(AdImpression.estimated_revenue_usd), 0)).where(
                AdImpression.is_valid.is_(True)
            )
        )
    ).scalar_one()

    confirmed_sum = (
        await db.execute(
            select(func.coalesce(func.sum(AdImpression.confirmed_revenue_usd), 0)).where(
                AdImpression.is_revenue_confirmed.is_(True)
            )
        )
    ).scalar_one()

    return AdsSummaryReportResponse(
        total_valid_impressions=int(total_valid_impressions),
        total_completed=int(total_completed),
        total_clicks=int(total_clicks),
        estimated_revenue_usd=round(float(estimated_sum), 4),
        confirmed_revenue_usd=round(float(confirmed_sum), 4),
    )
