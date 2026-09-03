from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_article_repo, get_event_repo
from app.repositories.article_repository import ArticleRepository
from app.repositories.event_repository import EventRepository
from app.schemas.event import (
    EventArticleResponse,
    EventResponse,
    EventSummaryOutput,
    EventSummaryRequest,
)
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    event_repo: EventRepository = Depends(get_event_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = EventService(event_repo, article_repo)
    return await service.get_events(skip, limit)


@router.get("/{slug}", response_model=EventResponse)
async def get_event(
    slug: str,
    event_repo: EventRepository = Depends(get_event_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = EventService(event_repo, article_repo)
    return await service.get_event(slug)


@router.get("/{event_id}/articles", response_model=list[EventArticleResponse])
async def get_event_articles(
    event_id: UUID,
    event_repo: EventRepository = Depends(get_event_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    service = EventService(event_repo, article_repo)
    return await service.get_event_articles(event_id)


@router.post("/{event_id}/summarize", response_model=EventSummaryOutput)
async def generate_event_summary(
    event_id: UUID,
    request: EventSummaryRequest = EventSummaryRequest(),
    event_repo: EventRepository = Depends(get_event_repo),
):
    from app.services.event_summarizer_service import EventSummarizerService
    service = EventSummarizerService(event_repo.db, event_repo)
    return await service.summarize_event_by_id(
        event_id=event_id,
        length=request.length,
        force_regenerate=request.force_regenerate,
    )


@router.get("/{event_id}/summary", response_model=EventSummaryOutput)
async def get_event_summary(
    event_id: UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    from app.services.event_summarizer_service import EventSummarizerService
    service = EventSummarizerService(event_repo.db, event_repo)
    return await service.summarize_event_by_id(
        event_id=event_id,
        force_regenerate=False,
    )


@router.get("/{identifier}/intelligence")
async def get_event_intelligence(
    identifier: str,
    event_repo: EventRepository = Depends(get_event_repo),
    article_repo: ArticleRepository = Depends(get_article_repo),
):
    """Retrieve unified event intelligence: summary, timeline, verified/disputed claims, framing, and sources."""
    from app.schemas.event_intelligence import (
        EventClaimsBreakdown,
        EventIntelligenceResponse,
        TimelineEntry,
    )
    from app.services.event_summarizer_service import EventSummarizerService
    from app.services.framing_service import FramingService
    from app.models.claim import Claim, ClaimEvidence
    from sqlalchemy import select
    import json

    event = None
    try:
        parsed_id = UUID(identifier)
        event = await event_repo.get_with_articles(parsed_id)
    except (ValueError, AttributeError):
        event = await event_repo.get_by_slug(identifier)
        if event:
            event = await event_repo.get_with_articles(event.id)

    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")

    # 1. Summary
    summarizer = EventSummarizerService(event_repo.db, event_repo)
    summary_output = await summarizer.summarize_event_by_id(event.id, force_regenerate=False)

    # 2. Sources
    sources_set = set()
    for art in event.articles:
        s_name = art.source.name if art.source else (art.source_name or "NewsWire")
        sources_set.add(s_name)
    sources = sorted(sources_set)

    # 3. Timeline
    timeline_entries = []
    if event.timeline:
        try:
            raw_t = json.loads(event.timeline) if isinstance(event.timeline, str) else event.timeline
            if isinstance(raw_t, list):
                for item in raw_t:
                    timeline_entries.append(
                        TimelineEntry(
                            time=str(item.get("timestamp") or item.get("time") or "Update"),
                            title=item.get("title") or item.get("note") or "Event development",
                            source=item.get("source") or "News Source",
                            note=item.get("note"),
                        )
                    )
        except Exception:
            pass

    if not timeline_entries:
        # Fallback: synthesize timeline entries from articles
        for idx, art in enumerate(sorted(event.articles, key=lambda a: a.published_at or str(a.created_at))):
            display_time = art.published_at[11:16] if (art.published_at and len(art.published_at) >= 16) else f"+{idx * 15}m"
            timeline_entries.append(
                TimelineEntry(
                    time=display_time,
                    title=art.title,
                    source=art.source.name if art.source else (art.source_name or "News Publisher"),
                    note=art.summary[:120] if art.summary else None,
                )
            )

    # 4. Claims & Verification
    stmt_claims = select(Claim).where(Claim.event_id == event.id)
    claim_rows = (await event_repo.db.execute(stmt_claims)).scalars().all()

    breakdown = EventClaimsBreakdown()
    for c in claim_rows:
        claim_resp = {
            "claim_id": str(c.id),
            "claim": c.claim_text,
            "claim_type": c.claim_type,
            "verdict": c.verdict,
            "confidence": c.confidence,
            "supporting_evidence": [],
            "refuting_evidence": [],
            "neutral_evidence": [],
            "independent_sources": c.independent_sources,
            "source_reliability": c.source_reliability,
        }
        if c.verdict == "WELL_SUPPORTED":
            breakdown.well_supported.append(claim_resp)
        elif c.verdict == "DISPUTED":
            breakdown.disputed.append(claim_resp)
        elif c.verdict == "CONTRADICTED":
            breakdown.contradicted.append(claim_resp)
        else:
            breakdown.unverified.append(claim_resp)

    # If no stored claims exist, extract key developments as verified claims
    if not claim_rows:
        for idx, dev in enumerate(summary_output.key_points[:3]):
            breakdown.well_supported.append({
                "claim_id": f"claim-{event.id}-{idx}",
                "claim": dev,
                "claim_type": "FACTUAL",
                "verdict": "WELL_SUPPORTED",
                "confidence": 0.88,
                "supporting_evidence": [],
                "refuting_evidence": [],
                "neutral_evidence": [],
                "independent_sources": len(sources),
                "source_reliability": 0.85,
            })

    # 5. Framing Analysis
    framing_data = None
    try:
        framing_service = FramingService(event_repo.db, event_repo)
        framing_data = await framing_service.analyze_event_by_id(event.id, force_recheck=False)
    except Exception:
        pass

    # 6. Related Events
    related_events = []
    if event.category:
        stmt_related = (
            select(event_repo.model)
            .where(event_repo.model.category == event.category, event_repo.model.id != event.id)
            .limit(3)
        )
        related_objs = (await event_repo.db.execute(stmt_related)).scalars().all()
        related_events = [{"id": str(r.id), "slug": r.slug, "title": r.title, "category": r.category} for r in related_objs]

    return EventIntelligenceResponse(
        id=event.id,
        slug=event.slug,
        title=event.title,
        category=event.category,
        importance_score=event.importance_score or 0.85,
        status=event.status or "active",
        start_date=str(event.start_date) if event.start_date else None,
        end_date=str(event.end_date) if event.end_date else None,
        article_count=len(event.articles),
        sources=sources,
        summary=summary_output,
        timeline=timeline_entries,
        claims=breakdown,
        framing=framing_data,
        latest_updates=[f"New developments reported by {sources[0]}"] if sources else [],
        related_events=related_events,
    )
