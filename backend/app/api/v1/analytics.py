from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_admin,
    get_db,
    get_optional_user,
)
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsEventItem,
    AnalyticsEventList,
    AnalyticsOverview,
    CategoryStats,
    DailyCount,
    SentimentStats,
    SourceStats,
    TrackEventRequest,
    UserActivityStats,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _admin_service(
    db: AsyncSession = Depends(get_db), admin=Depends(get_current_admin)
) -> AnalyticsService:
    return AnalyticsService(AnalyticsRepository(db))


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return await AnalyticsService(AnalyticsRepository(db)).get_overview()


@router.get("/activity", response_model=list[UserActivityStats])
async def activity(
    days: int = Query(14, ge=1, le=90),
    service: AnalyticsService = Depends(_admin_service),
):
    return await service.get_activity(days)


@router.get("/articles-trend", response_model=list[DailyCount])
async def articles_trend(
    days: int = Query(14, ge=1, le=90),
    service: AnalyticsService = Depends(_admin_service),
):
    return await service.get_articles_trend(days)


@router.get("/categories", response_model=list[CategoryStats])
async def categories(
    limit: int = Query(20, ge=1, le=100),
    service: AnalyticsService = Depends(_admin_service),
):
    return await service.get_categories(limit)


@router.get("/sources", response_model=list[SourceStats])
async def sources(
    limit: int = Query(10, ge=1, le=100),
    service: AnalyticsService = Depends(_admin_service),
):
    return await service.get_sources(limit)


@router.get("/sentiment", response_model=list[SentimentStats])
async def sentiment(
    service: AnalyticsService = Depends(_admin_service),
):
    return await service.get_sentiment()


@router.get("/events", response_model=AnalyticsEventList)
async def events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    service: AnalyticsService = Depends(_admin_service),
):
    return await service.get_events(skip, limit)


@router.post("/track", response_model=AnalyticsEventItem)
async def track_event(
    request: TrackEventRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    service = AnalyticsService(AnalyticsRepository(db))
    return await service.track_event(
        event_type=request.event_type,
        user_id=str(user.id) if user else None,
        article_id=request.article_id,
        value=request.value,
        metadata=request.metadata,
    )
