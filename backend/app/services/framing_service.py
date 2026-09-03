"""Service layer coordinating media framing analysis, database persistence, and vector indexing."""

from __future__ import annotations

import json
import logging
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.framing_agent import FramingAgent
from app.db.session import async_session_factory
from app.models.claim import Claim
from app.models.event import Event
from app.models.framing import EventFramingAnalysis
from app.repositories.event_repository import EventRepository
from app.schemas.framing import (
    ArticleInput,
    EventFramingResponse,
    FramingFeatures,
    SourceComparison,
)
from app.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class FramingService:
    """Coordinates event framing analysis, persistence, and vector indexing."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        event_repo: EventRepository | None = None,
        agent: FramingAgent | None = None,
        vector_store: VectorStoreService | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.event_repo = event_repo or EventRepository(self.session)
        self.agent = agent or FramingAgent()
        self.vector_store = vector_store or VectorStoreService()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._owns_session:
            await self.session.close()

    async def analyze_event_by_id(
        self, event_id: UUID | str, force_recheck: bool = False
    ) -> EventFramingResponse:
        """Analyze multi-source framing for an event, persist results and index into vector store."""
        parsed_id = UUID(str(event_id))
        event = await self.event_repo.get_with_articles(parsed_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")

        # 1. Check existing cached analysis if force_recheck is False
        if not force_recheck:
            stmt = select(EventFramingAnalysis).where(EventFramingAnalysis.event_id == parsed_id).order_by(EventFramingAnalysis.created_at.desc())
            result = await self.session.execute(stmt)
            cached = result.scalars().first()
            if cached:
                return self._build_response_from_orm(event, cached)

        # 2. Retrieve verified claims for the event
        stmt_claims = select(Claim).where(Claim.event_id == parsed_id)
        claim_rows = (await self.session.execute(stmt_claims)).scalars().all()
        verified_claim_texts = [c.claim_text for c in claim_rows]

        # 3. Format article payloads
        articles_data = []
        for a in event.articles:
            articles_data.append({
                "id": str(a.id),
                "title": a.title,
                "content": a.content or a.summary or "",
                "summary": a.summary or "",
                "source_name": a.source.name if a.source else (a.source_name or "News Source"),
                "published_at": a.published_at or a.created_at,
            })

        # 4. Run Framing Agent
        response = self.agent.analyze_event_framing(
            event_id=str(event.id),
            event_title=event.title,
            articles=articles_data,
            verified_claims=verified_claim_texts,
        )

        # 5. Persist to DB
        await self._persist_framing_analysis(event, response)

        # 6. Index into Vector Store
        await self._index_in_vector_store(event, response)

        if self._owns_session:
            await self.session.commit()

        return response

    async def compare_arbitrary_articles(
        self, event_title: str, articles: list[ArticleInput]
    ) -> EventFramingResponse:
        """Perform framing comparison over user-provided arbitrary articles."""
        art_dicts = [
            {
                "source_name": a.source_name,
                "title": a.headline,
                "content": a.content or a.lead_paragraph,
                "lead_paragraph": a.lead_paragraph,
            }
            for a in articles
        ]
        return self.agent.analyze_event_framing(
            event_id=f"standalone-{uuid.uuid4().hex[:8]}",
            event_title=event_title,
            articles=art_dicts,
        )

    async def _persist_framing_analysis(self, event: Event, response: EventFramingResponse):
        """Save analysis to event_framing_analyses and cache JSON on event."""
        # Convert Pydantic comparisons to dicts
        comp_dicts = [c.model_dump() for c in response.comparisons]

        analysis_orm = EventFramingAnalysis(
            id=uuid.uuid4(),
            event_id=event.id,
            sources_analyzed=json.dumps(response.sources),
            comparisons=json.dumps(comp_dicts),
            framing_patterns=json.dumps(response.framing_patterns),
            language_patterns=json.dumps(response.language_patterns),
            areas_of_agreement=json.dumps(response.areas_of_agreement),
            areas_of_difference=json.dumps(response.areas_of_difference),
            confidence=response.confidence,
        )
        self.session.add(analysis_orm)

        # Cache on event
        event.framing_analysis = json.dumps(response.model_dump())
        await self.session.flush()

    def _build_response_from_orm(self, event: Event, cached: EventFramingAnalysis) -> EventFramingResponse:
        """Reconstruct Pydantic response from ORM record."""
        comparisons = []
        for d in cached.get_comparisons_list():
            ff = d.get("framing_features", {})
            features = FramingFeatures(
                primary_frame=ff.get("primary_frame", "POLICY_AND_TECHNICAL_DETAILS"),
                narrative_emphasis=ff.get("narrative_emphasis", ""),
                emotional_intensity=ff.get("emotional_intensity", 0.0),
                sensationalism_score=ff.get("sensationalism_score", 0.0),
                active_voice_ratio=ff.get("active_voice_ratio", 0.8),
                certainty_level=ff.get("certainty_level", "high"),
                quoted_actors=ff.get("quoted_actors", []),
            )
            comparisons.append(
                SourceComparison(
                    source=d.get("source", "Publisher"),
                    headline=d.get("headline", ""),
                    dominant_topics=d.get("dominant_topics", []),
                    entities_emphasized=d.get("entities_emphasized", []),
                    tone=d.get("tone", "objective_analytical"),
                    sentiment=d.get("sentiment", "neutral"),
                    key_facts=d.get("key_facts", []),
                    omitted_or_less_emphasized_facts=d.get("omitted_or_less_emphasized_facts", []),
                    framing_features=features,
                )
            )

        return EventFramingResponse(
            event_id=str(event.id),
            sources=cached.get_sources_list(),
            comparisons=comparisons,
            framing_patterns=cached.get_framing_patterns_list(),
            language_patterns=cached.get_language_patterns_list(),
            areas_of_agreement=cached.get_areas_of_agreement_list(),
            areas_of_difference=cached.get_areas_of_difference_list(),
            confidence=cached.confidence,
        )

    async def _index_in_vector_store(self, event: Event, response: EventFramingResponse):
        """Index framing synthesis into vector store if available."""
        try:
            if not self.vector_store.is_available():
                return

            # Combine framing narrative text
            framing_summary = f"Event: {event.title}. " + " ".join(response.framing_patterns) + " " + " ".join(response.areas_of_difference)

            # Build metadata payload
            metadata = {
                "event_id": str(event.id),
                "title": event.title,
                "sources": response.sources,
                "confidence": response.confidence,
                "type": "framing_analysis",
            }

            # Embed using local sentence transformer or deterministic embedding
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            vector = model.encode(framing_summary[:1000]).tolist()

            client = self.vector_store._get_client()
            from qdrant_client.models import PointStruct
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=metadata,
            )
            client.upsert(
                collection_name=self.vector_store.COLLECTION if hasattr(self.vector_store, "COLLECTION") else "articles",
                points=[point],
            )
            logger.info("Indexed framing analysis into vector store for event %s", event.id)
        except Exception as exc:
            logger.debug("Vector store indexing skipped for framing analysis: %s", exc)
