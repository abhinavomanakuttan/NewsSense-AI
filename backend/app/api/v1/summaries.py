"""FastAPI router for Multi-Document and Event Summaries."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_event_repo
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventSummaryOutput
from app.services.event_summarizer_service import EventSummarizerService

router = APIRouter(prefix="/summaries", tags=["Summaries"])


class DirectSummarizeRequest(BaseModel):
    """Payload for summarizing ad-hoc multi-source texts."""
    title: str = Field(default="Ad-Hoc Event Brief")
    texts: list[str] = Field(min_length=1, description="List of source passages or articles")
    sources: list[str] = Field(default_factory=list, description="Corresponding source names")
    length: str = Field(default="standard", description="brief | standard | detailed")


@router.get("/event/{event_id}", response_model=EventSummaryOutput)
async def get_event_summary(
    event_id: UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Retrieve multi-document synthesized summary for an event."""
    service = EventSummarizerService(event_repo.db, event_repo)
    return await service.summarize_event_by_id(event_id, force_regenerate=False)


@router.post("/synthesize", response_model=EventSummaryOutput)
async def synthesize_texts(
    req: DirectSummarizeRequest,
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Directly synthesize multiple news texts into a factual multi-document summary."""
    from app.models.article import Article
    from datetime import datetime, timezone
    import uuid

    # Construct temporary in-memory articles
    temp_articles = []
    for idx, text in enumerate(req.texts):
        s_name = req.sources[idx] if idx < len(req.sources) else f"Source {idx + 1}"
        art = Article(
            id=uuid.uuid4(),
            title=f"{req.title} - {s_name}",
            slug=f"temp-{uuid.uuid4()}",
            content=text,
            summary=text[:250],
            source_name=s_name,
            published_at=datetime.now(timezone.utc).isoformat(),
        )
        temp_articles.append(art)

    service = EventSummarizerService(event_repo.db, event_repo)
    return await service.summarize_articles(
        event_title=req.title,
        articles=temp_articles,
        length=req.length,
    )
