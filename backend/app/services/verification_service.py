"""Verification Service for NewsSense AI.

Orchestrates:
- Claim extraction & verification over database events/articles
- Relational persistence of Claim and ClaimEvidence records
- Critique Loop dispatch: flags event and publishes to Redis Stream
"""

from __future__ import annotations

import json
import logging
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.verification_agent import VerificationAgent
from app.db.session import async_session_factory
from app.models.claim import Claim, ClaimEvidence
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.verification import (
    ClaimVerificationOutput,
    EventVerificationResponse,
    EvidenceItemOutput,
    VerificationVerdict,
)

logger = logging.getLogger(__name__)

STREAM_VERIFICATION_REQUIRED = "stream:news:verification_required"


class VerificationService:
    """Service layer coordinating claim verification and critique alerting."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        event_repo: EventRepository | None = None,
        agent: VerificationAgent | None = None,
    ):
        self._owns_session = session is None
        self.session = session or async_session_factory()
        self.event_repo = event_repo or EventRepository(self.session)
        self.agent = agent or VerificationAgent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._owns_session:
            await self.session.close()

    async def verify_event_by_id(self, event_id: UUID | str, force_recheck: bool = False) -> EventVerificationResponse:
        """Verify all claims within an event cluster and persist evidence."""
        parsed_id = UUID(str(event_id))
        event = await self.event_repo.get_with_articles(parsed_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")

        # Check for cached verified claims if not forced
        if not force_recheck:
            stmt = select(Claim).where(Claim.event_id == parsed_id)
            result = await self.session.execute(stmt)
            existing_claims = result.scalars().all()
            if existing_claims:
                return await self._build_response_from_db(event, existing_claims)

        # Build article payload for the agent
        articles_data = []
        for a in event.articles:
            articles_data.append({
                "id": str(a.id),
                "title": a.title,
                "content": a.content or a.summary or "",
                "summary": a.summary or "",
                "source_name": a.source.name if a.source else (a.source_name or "News Source"),
                "source_domain": a.source.domain if a.source else "",
                "published_at": a.published_at or a.created_at,
            })

        # Run verification agent
        response = await self.agent.verify_event_cluster(
            event_id=str(event.id),
            event_title=event.title,
            articles=articles_data,
        )

        # Persist claims & evidence
        await self._persist_verification_results(event, response)

        # Critique Loop: Check for contradicted claims
        if response.contradicted_claims_count > 0 or response.overall_trust_score < 0.65:
            event.status = "flagged_verification"
            await self.session.flush()
            await self._dispatch_critique_alert(event, response)

        if self._owns_session:
            await self.session.commit()

        return response

    async def verify_standalone_claim(self, claim_text: str, context: str | None = None) -> ClaimVerificationOutput:
        """Verify an isolated user-submitted claim."""
        cluster_mock = []
        if context:
            cluster_mock.append({
                "title": "Context Reference",
                "content": context,
                "source_name": "Provided Context",
                "source_domain": "context.local",
            })

        return await self.agent.verify_claim(
            claim_text=claim_text,
            cluster_articles=cluster_mock,
        )

    async def _persist_verification_results(self, event: Event, response: EventVerificationResponse):
        """Save Claim and ClaimEvidence records to the database."""
        for c_out in response.claims:
            claim_orm = Claim(
                id=uuid.uuid4(),
                event_id=event.id,
                claim_text=c_out.claim,
                claim_type=c_out.claim_type,
                verdict=c_out.verdict,
                confidence=c_out.confidence,
                independent_sources=c_out.independent_sources,
                source_reliability=c_out.source_reliability,
            )
            self.session.add(claim_orm)
            await self.session.flush()

            # Add all evidence items
            all_evidence = c_out.supporting_evidence + c_out.refuting_evidence + c_out.neutral_evidence
            for ev in all_evidence:
                ev_orm = ClaimEvidence(
                    id=uuid.uuid4(),
                    claim_id=claim_orm.id,
                    source_name=ev.source_name,
                    url=ev.url,
                    passage=ev.passage,
                    publication_date=ev.publication_date,
                    source_reliability=ev.source_reliability,
                    retrieval_score=ev.retrieval_score,
                    nli_stance=ev.stance,
                    nli_confidence=ev.confidence,
                    independence_weight=ev.independence_weight,
                )
                self.session.add(ev_orm)

        await self.session.flush()

    async def _build_response_from_db(self, event: Event, claims: list[Claim]) -> EventVerificationResponse:
        """Reconstruct verification response from database cache."""
        outputs: list[ClaimVerificationOutput] = []
        supp_count = 0
        contra_count = 0
        disp_count = 0
        unver_count = 0
        alerts: list[str] = []

        for c in claims:
            # Query evidence
            stmt = select(ClaimEvidence).where(ClaimEvidence.claim_id == c.id)
            ev_result = await self.session.execute(stmt)
            evidence_rows = ev_result.scalars().all()

            supp_ev, ref_ev, neu_ev = [], [], []
            for e in evidence_rows:
                out_e = EvidenceItemOutput(
                    source_name=e.source_name,
                    url=e.url,
                    passage=e.passage,
                    publication_date=e.publication_date,
                    source_reliability=e.source_reliability,
                    retrieval_score=e.retrieval_score,
                    stance=e.nli_stance,
                    confidence=e.nli_confidence,
                    independence_weight=e.independence_weight,
                )
                if e.nli_stance == "SUPPORTS":
                    supp_ev.append(out_e)
                elif e.nli_stance == "REFUTES":
                    ref_ev.append(out_e)
                else:
                    neu_ev.append(out_e)

            if c.verdict == VerificationVerdict.WELL_SUPPORTED.value:
                supp_count += 1
            elif c.verdict == VerificationVerdict.CONTRADICTED.value:
                contra_count += 1
                alerts.append(f"CONTRADICTED claim: {c.claim_text}")
            elif c.verdict == VerificationVerdict.DISPUTED.value:
                disp_count += 1
                alerts.append(f"DISPUTED claim: {c.claim_text}")
            else:
                unver_count += 1

            outputs.append(
                ClaimVerificationOutput(
                    claim_id=str(c.id),
                    claim=c.claim_text,
                    claim_type=c.claim_type,
                    verdict=c.verdict,
                    confidence=c.confidence,
                    supporting_evidence=supp_ev,
                    refuting_evidence=ref_ev,
                    neutral_evidence=neu_ev,
                    independent_sources=c.independent_sources,
                    source_reliability=c.source_reliability,
                )
            )

        trust = (supp_count * 1.0 + unver_count * 0.5 + disp_count * 0.3) / max(len(claims), 1)
        if contra_count > 0:
            trust = max(0.1, trust - (contra_count * 0.25))

        return EventVerificationResponse(
            event_id=str(event.id),
            overall_trust_score=round(trust, 2),
            total_claims=len(claims),
            supported_claims_count=supp_count,
            contradicted_claims_count=contra_count,
            disputed_claims_count=disp_count,
            unverified_claims_count=unver_count,
            claims=outputs,
            critique_alerts=alerts,
        )

    async def _dispatch_critique_alert(self, event: Event, response: EventVerificationResponse):
        """Notify pipeline and summarizer agent about disputed or contradicted claims."""
        try:
            from app.pipeline.queue.redis_stream_producer import RedisStreamProducer
            producer = RedisStreamProducer()
            client = await producer._get_client()

            payload = {
                "event_id": str(event.id),
                "event_title": event.title,
                "contradicted_count": response.contradicted_claims_count,
                "disputed_count": response.disputed_claims_count,
                "alerts": response.critique_alerts,
                "action": "hedge_or_remove_claims",
            }
            await client.xadd(STREAM_VERIFICATION_REQUIRED, fields={"data": json.dumps(payload)}, maxlen=5000, approximate=True)
            await producer.close()
            logger.info("Dispatched critique alert for event %s to %s", event.id, STREAM_VERIFICATION_REQUIRED)
        except Exception as exc:
            logger.debug("Redis stream alert skipped: %s", exc)
