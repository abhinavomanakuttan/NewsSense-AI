"""FastAPI Endpoints for Media Bias and Framing Agent."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_event_repo
from app.repositories.event_repository import EventRepository
from app.schemas.framing import (
    AnalyzeEventRequest,
    CompareArticlesRequest,
    EventFramingResponse,
)
from app.services.framing_service import FramingService

router = APIRouter(prefix="/framing", tags=["Framing"])


@router.post("/analyze-event/{event_id}", response_model=EventFramingResponse)
async def analyze_event_framing(
    event_id: UUID,
    request: AnalyzeEventRequest = AnalyzeEventRequest(),
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Analyze multi-source coverage framing, discourse patterns, and fact omissions for an event."""
    service = FramingService(event_repo.db, event_repo)
    try:
        return await service.analyze_event_by_id(
            event_id=event_id,
            force_recheck=request.force_recheck,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/event/{event_id}", response_model=EventFramingResponse)
async def get_event_framing(
    event_id: UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Retrieve existing coverage framing analysis for an event."""
    service = FramingService(event_repo.db, event_repo)
    try:
        return await service.analyze_event_by_id(
            event_id=event_id,
            force_recheck=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/compare-articles", response_model=EventFramingResponse)
async def compare_articles_framing(request: CompareArticlesRequest):
    """Compare framing and discourse features across arbitrary user-submitted articles."""
    async with FramingService() as service:
        return await service.compare_arbitrary_articles(
            event_title=request.event_title,
            articles=request.articles,
        )
