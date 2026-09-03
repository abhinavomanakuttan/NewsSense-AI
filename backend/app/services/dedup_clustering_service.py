"""Deduplication and Event Clustering Service for NewsSense AI.

Orchestrates:
1. Stage 1: Exact Duplicate Detection (O(1) hashes)
2. Stage 2: Near Duplicate Detection & Syndication Detection (with wire discounting)
3. Stage 3 & 4: Multi-Field Semantic Embeddings & Composite Event Clustering
4. Online Event Lifecycle Management (Creation, Evolution, Centroid Update, Contradiction Flagging)
5. Event Distribution via Redis Streams (stream:news:clustered)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.deduplicator import DeduplicationEngine
from app.ai.event_detector import EventDetector
from app.db.session import async_session_factory
from app.models.article import Article
from app.models.event import Event
from app.repositories.article_repository import ArticleRepository
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventClusterMatchResult
from app.utils.text_utils import slugify

logger = logging.getLogger(__name__)

STREAM_NEWS_CLUSTERED = "stream:news:clustered"
STREAM_NEWS_VERIFICATION = "stream:news:verification_required"


class DedupClusteringService:
    """Master service coordinating deduplication and event clustering."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        article_repo: ArticleRepository | None = None,
        event_repo: EventRepository | None = None,
        dedup_engine: DeduplicationEngine | None = None,
        event_detector: EventDetector | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.article_repo = article_repo or ArticleRepository(self.session)
        self.event_repo = event_repo or EventRepository(self.session)
        self.dedup_engine = dedup_engine or DeduplicationEngine()
        self.event_detector = event_detector or EventDetector()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._owns_session:
            await self.session.close()

    async def process_article(self, article: Article | dict | UUID | str) -> EventClusterMatchResult:
        """Process an article through the entire deduplication and clustering pipeline."""
        article_obj = await self._resolve_article(article)
        if not article_obj:
            raise ValueError(f"Article {article} could not be resolved")

        # --------------------------------------------------------------
        # Fetch candidate articles in recent window (last 72h)
        # --------------------------------------------------------------
        candidate_articles = await self._get_recent_articles(hours=72, exclude_id=article_obj.id)

        # --------------------------------------------------------------
        # Stage 1: Exact Duplicate Detection
        # --------------------------------------------------------------
        candidate_hashes = {
            "url_hash": article_obj.url_hash,
            "content_hash": article_obj.content_hash,
            "normalized_title": article_obj.normalized_title,
            "source_domain": article_obj.source.domain if article_obj.source else None,
        }
        exact_match = self.dedup_engine.check_exact_duplicate(candidate_hashes, candidate_articles)
        if exact_match and exact_match.is_duplicate:
            matched_article = await self.article_repo.get_by_id(UUID(exact_match.matched_article_id))
            event_id = matched_article.event_id if matched_article else None

            article_obj.is_duplicate = True
            article_obj.duplicate_of_id = UUID(exact_match.matched_article_id) if exact_match.matched_article_id else None
            article_obj.match_type = "exact_duplicate"
            article_obj.event_id = event_id
            await self._commit_if_needed()

            result = EventClusterMatchResult(
                article_id=str(article_obj.id),
                event_id=str(event_id) if event_id else None,
                match_type="exact_duplicate",
                similarity=1.0,
                confidence=1.0,
                is_duplicate=True,
                is_syndicated=False,
                details={"reason": exact_match.reason, "duplicate_of": exact_match.matched_article_id},
            )
            await self._publish_clustering_event(result, article_obj)
            return result

        # --------------------------------------------------------------
        # Stage 2: Near Duplicate Detection & Syndication
        # --------------------------------------------------------------
        near_match = self.dedup_engine.check_near_duplicate(
            title=article_obj.title,
            content=article_obj.content or article_obj.summary or "",
            existing_articles=candidate_articles,
        )
        if near_match and near_match.is_near_duplicate:
            matched_article = await self.article_repo.get_by_id(UUID(near_match.matched_article_id))
            event_id = matched_article.event_id if matched_article else None

            article_obj.is_duplicate = True
            article_obj.duplicate_of_id = UUID(near_match.matched_article_id) if near_match.matched_article_id else None
            article_obj.match_type = "near_duplicate"
            article_obj.event_id = event_id
            await self._commit_if_needed()

            result = EventClusterMatchResult(
                article_id=str(article_obj.id),
                event_id=str(event_id) if event_id else None,
                match_type="near_duplicate",
                similarity=near_match.similarity_score,
                confidence=near_match.confidence,
                is_duplicate=True,
                is_syndicated=False,
                details={"reason": near_match.reason, "duplicate_of": near_match.matched_article_id},
            )
            await self._publish_clustering_event(result, article_obj)
            return result

        # Check Syndication (reprinted wire copy across publishers)
        cand_dict = self._article_to_dict(article_obj)
        synd_match = self.dedup_engine.check_syndication(cand_dict, candidate_articles)
        if synd_match and synd_match.is_syndicated:
            matched_article = await self.article_repo.get_by_id(UUID(synd_match.matched_article_id))
            event_id = matched_article.event_id if matched_article else None

            article_obj.is_syndicated = True
            article_obj.source_independence_score = synd_match.source_independence_score
            article_obj.match_type = "syndicated"
            article_obj.event_id = event_id

            if event_id:
                event = await self.event_repo.get_by_id(event_id)
                if event:
                    await self._attach_article_to_event(
                        event=event,
                        article=article_obj,
                        is_syndicated=True,
                        independence_score=synd_match.source_independence_score,
                        update_note=f"Syndicated report via {article_obj.source_name or 'wire'}",
                    )

            await self._commit_if_needed()

            result = EventClusterMatchResult(
                article_id=str(article_obj.id),
                event_id=str(event_id) if event_id else None,
                match_type="syndicated",
                similarity=synd_match.similarity_score,
                confidence=synd_match.confidence,
                is_duplicate=False,
                is_syndicated=True,
                details={
                    "reason": synd_match.reason,
                    "source_independence_score": synd_match.source_independence_score,
                },
            )
            await self._publish_clustering_event(result, article_obj)
            return result

        # --------------------------------------------------------------
        # Stage 3 & 4: Semantic Embeddings & Composite Event Clustering
        # --------------------------------------------------------------
        article_embedding = await self._generate_composite_embedding(article_obj)
        article_data = self._article_to_dict(article_obj)
        article_data["composite_embedding"] = article_embedding

        # Fetch active events in sliding temporal window
        active_events = await self.event_repo.get_active_events_in_window(hours=72)
        active_event_dicts = [self._event_to_dict(e) for e in active_events]

        decision = self.event_detector.evaluate_article_for_events(article_data, active_event_dicts)

        if decision.event_id:
            # Match found: attach to existing event and evolve lifecycle
            event = await self.event_repo.get_by_id(UUID(decision.event_id))
            if event:
                await self._attach_article_to_event(
                    event=event,
                    article=article_obj,
                    is_syndicated=False,
                    independence_score=1.0,
                    is_contradiction=decision.is_contradiction,
                    article_embedding=article_embedding,
                    update_note=f"Report added from {article_obj.source_name or 'independent source'}",
                )

            article_obj.event_id = UUID(decision.event_id)
            article_obj.match_type = decision.match_type
            await self._commit_if_needed()

            result = EventClusterMatchResult(
                article_id=str(article_obj.id),
                event_id=str(decision.event_id),
                match_type=decision.match_type,
                similarity=decision.similarity,
                confidence=decision.confidence,
                is_duplicate=False,
                is_syndicated=False,
                details=decision.details,
            )
            await self._publish_clustering_event(result, article_obj)
            return result

        # No match found: create new event
        new_event = await self._create_new_event(article_obj, article_embedding)
        article_obj.event_id = new_event.id
        article_obj.match_type = "new_event"
        await self._commit_if_needed()

        result = EventClusterMatchResult(
            article_id=str(article_obj.id),
            event_id=str(new_event.id),
            match_type="new_event",
            similarity=0.0,
            confidence=1.0,
            is_duplicate=False,
            is_syndicated=False,
            details={"canonical_title": new_event.title, "event_status": new_event.status},
        )
        await self._publish_clustering_event(result, article_obj)
        return result

    # ------------------------------------------------------------------
    # Lifecycle Mutation Helpers
    # ------------------------------------------------------------------

    async def _attach_article_to_event(
        self,
        event: Event,
        article: Article,
        is_syndicated: bool = False,
        independence_score: float = 1.0,
        is_contradiction: bool = False,
        article_embedding: list[float] | None = None,
        update_note: str = "",
    ):
        """Evolve event: update centroid embedding, timeline history, and source counts."""
        now_dt = datetime.now(UTC)
        event.latest_update = now_dt

        # Count updates
        curr_count = int(event.article_count or "1")
        new_count = curr_count + 1
        event.article_count = str(new_count)
        event.source_count = (event.source_count or 1) + 1
        event.independent_source_count = round((event.independent_source_count or 1.0) + independence_score, 2)

        # Centroid update
        if article_embedding:
            evt_emb = json.loads(event.embedding) if event.embedding else None
            updated_emb = self.event_detector.update_event_centroid(evt_emb, article_embedding, curr_count)
            event.embedding = json.dumps(updated_emb)

        # Contradiction check
        if is_contradiction:
            event.status = "flagged_verification"
            event_type = "contradiction"
            note = f"Contradicting report detected: {article.title}"
        else:
            event_type = self.event_detector.classify_update_type(article.title, is_first=False)
            note = update_note or f"Updated with report: {article.title}"

        event.append_timeline_event(
            timestamp=now_dt.isoformat(),
            article_id=str(article.id),
            event_type=event_type,
            note=note,
        )

        # Merge entities
        if article.entities:
            self._merge_event_entities(event, article.entities)

    async def _create_new_event(self, article: Article, embedding: list[float]) -> Event:
        """Create a new Event entity from an initial article."""
        now_dt = datetime.now(UTC)
        slug_base = slugify(article.title)[:450] or f"event-{uuid4().hex[:8]}"
        slug = f"{slug_base}-{now_dt.strftime('%Y%m%d')}"

        # Timeline initial report
        timeline_list = [{
            "timestamp": now_dt.isoformat(),
            "article_id": str(article.id),
            "type": "initial_report",
            "note": f"Initial report from {article.source_name or 'news source'}",
        }]

        new_event = Event(
            title=article.title.strip(),
            slug=slug,
            summary=article.summary or (article.content[:300] if article.content else None),
            category=article.category_name,
            category_id=article.category_name,
            start_date=now_dt,
            end_date=now_dt,
            article_count="1",
            source_count=1,
            independent_source_count=1.0,
            importance_score=article.credibility_score or 0.5,
            embedding=json.dumps(embedding) if embedding else None,
            status="active",
            timeline=json.dumps(timeline_list),
            entities=article.entities,
            locations=json.dumps([article.country]) if article.country else "[]",
            is_active=True,
        )
        self.session.add(new_event)
        await self.session.flush()
        return new_event

    def _merge_event_entities(self, event: Event, article_entities_str: str):
        try:
            art_ents = json.loads(article_entities_str)
            evt_ents = json.loads(event.entities) if event.entities else []
            if isinstance(evt_ents, list) and isinstance(art_ents, list):
                seen_texts = {e.get("text") for e in evt_ents if isinstance(e, dict)}
                for item in art_ents:
                    if isinstance(item, dict) and item.get("text") not in seen_texts:
                        evt_ents.append(item)
                        seen_texts.add(item.get("text"))
                event.entities = json.dumps(evt_ents[:50])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Embedding Generator Integration
    # ------------------------------------------------------------------

    async def _generate_composite_embedding(self, article: Article) -> list[float]:
        """Generate weighted composite embedding using SentenceTransformers or fallback."""
        try:
            from app.ai.embeddings import EmbeddingGenerator
            generator = EmbeddingGenerator()
            await generator.initialize()

            # Encode title, summary, and content head
            title_text = article.title or ""
            summary_text = article.summary or ""
            content_text = (article.content or "")[:1500]

            texts = [title_text, summary_text, content_text]
            embeddings = await generator.process_batch(texts)

            composite = self.event_detector.compute_composite_embedding(
                title_emb=embeddings[0],
                summary_emb=embeddings[1],
                content_emb=embeddings[2],
            )
            return composite
        except Exception as exc:
            logger.debug("Falling back on deterministic embedding representation: %s", exc)
            return self._deterministic_fallback_embedding(article.title)

    @staticmethod
    def _deterministic_fallback_embedding(text: str, dims: int = 384) -> list[float]:
        """Deterministic pseudo-embedding for environments without PyTorch/model downloads."""
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(dims):
            byte_val = h[i % len(h)]
            vec.append(float((byte_val / 127.5) - 1.0))
        norm = sum(x**2 for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0 else vec

    # ------------------------------------------------------------------
    # Queue & Event Streaming
    # ------------------------------------------------------------------

    async def _publish_clustering_event(self, result: EventClusterMatchResult, article: Article):
        """Stream clustering decision to Redis Streams for downstream NLP and verification agents."""
        try:
            from app.pipeline.queue.redis_stream_producer import RedisStreamProducer
            producer = RedisStreamProducer()
            client = await producer._get_client()

            payload = {
                "article_id": result.article_id,
                "event_id": result.event_id,
                "match_type": result.match_type,
                "similarity": result.similarity,
                "confidence": result.confidence,
                "is_duplicate": result.is_duplicate,
                "is_syndicated": result.is_syndicated,
                "title": article.title,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            stream_entry = {
                "event_type": "article_clustered",
                "data": json.dumps(payload),
            }
            await client.xadd(STREAM_NEWS_CLUSTERED, fields=stream_entry, maxlen=10000, approximate=True)

            if result.match_type == "contradiction":
                await client.xadd(STREAM_NEWS_VERIFICATION, fields=stream_entry, maxlen=10000, approximate=True)

            await producer.close()
        except Exception as exc:
            logger.debug("Redis Stream publish skipped in local environment: %s", exc)

    # ------------------------------------------------------------------
    # Serialization and Query Helpers
    # ------------------------------------------------------------------

    async def _resolve_article(self, article: Article | dict | UUID | str) -> Article | None:
        if isinstance(article, Article):
            return article
        if isinstance(article, (UUID, str)):
            return await self.article_repo.get_by_id(UUID(str(article)))
        if isinstance(article, dict):
            art_id = article.get("id") or article.get("article_id")
            if art_id:
                return await self.article_repo.get_by_id(UUID(str(art_id)))
        return None

    async def _get_recent_articles(self, hours: int = 72, exclude_id: UUID | None = None) -> list[dict]:
        stmt = select(Article).order_by(Article.created_at.desc()).limit(150)
        if exclude_id:
            stmt = stmt.where(Article.id != exclude_id)
        result = await self.session.execute(stmt)
        articles = result.scalars().all()
        return [self._article_to_dict(a) for a in articles]

    def _article_to_dict(self, article: Article) -> dict:
        return {
            "id": str(article.id),
            "article_id": str(article.id),
            "title": article.title,
            "normalized_title": article.normalized_title,
            "content": article.content,
            "summary": article.summary,
            "url": article.url,
            "url_hash": article.url_hash,
            "content_hash": article.content_hash,
            "source_domain": article.source.domain if getattr(article, "source", None) else None,
            "published_at": article.published_at,
            "category": article.category_name,
            "entities": article.entities,
            "country": article.country,
            "event_id": str(article.event_id) if article.event_id else None,
        }

    def _event_to_dict(self, event: Event) -> dict:
        return {
            "id": str(event.id),
            "event_id": str(event.id),
            "title": event.title,
            "category": event.category,
            "entities": event.entities,
            "locations": event.locations,
            "start_time": event.start_date,
            "latest_update": event.end_date,
            "embedding": event.embedding,
            "article_count": event.article_count,
            "status": event.status,
        }

    async def _commit_if_needed(self):
        await self.session.flush()
        if self._owns_session:
            await self.session.commit()
