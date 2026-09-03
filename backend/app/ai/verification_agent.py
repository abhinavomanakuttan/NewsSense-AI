"""Master Fact-Checking and Verification Agent for NewsSense AI.

Integrates Stages 1 to 5:
1. Atomic Claim Extraction & Classification (ClaimExtractor)
2. Multi-Channel Evidence Retrieval (EvidenceRetriever)
3. Cross-Encoder NLI Stance Classification (NLIVerifier)
4. Source Independence Discounting
5. Corroboration Scoring and Strict 4-State Verdict Generation
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.claim_extractor import ClaimExtractor
from app.ai.evidence_retriever import EvidenceRetriever
from app.ai.nli_verifier import NLIVerifier
from app.schemas.verification import (
    ClaimVerificationOutput,
    EventVerificationResponse,
    VerificationVerdict,
)

logger = logging.getLogger(__name__)


class VerificationAgent:
    """Master fact-checking and claim verification agent."""

    def __init__(
        self,
        claim_extractor: ClaimExtractor | None = None,
        evidence_retriever: EvidenceRetriever | None = None,
        nli_verifier: NLIVerifier | None = None,
    ):
        self.extractor = claim_extractor or ClaimExtractor()
        self.retriever = evidence_retriever or EvidenceRetriever()
        self.nli = nli_verifier or NLIVerifier()

    async def verify_claim(
        self,
        claim_text: str,
        claim_type: str = "FACTUAL",
        cluster_articles: list[dict[str, Any]] | None = None,
    ) -> ClaimVerificationOutput:
        """Verify a single atomic claim using multi-channel evidence and NLI."""
        evidence_list = await self.retriever.retrieve_evidence(
            claim_text=claim_text,
            cluster_articles=cluster_articles,
            max_passages=6,
        )

        return self.nli.evaluate_claim_corroboration(
            claim_id=f"clm-{hash(claim_text) & 0xffffffff:08x}",
            claim_text=claim_text,
            claim_type=claim_type,
            evidence_list=evidence_list,
        )

    async def verify_event_cluster(
        self,
        event_id: str,
        event_title: str,
        articles: list[dict[str, Any]],
        max_claims_to_check: int = 8,
    ) -> EventVerificationResponse:
        """Extract checkable claims across all articles in an event and verify each."""
        # 1. Combine salient text from cluster articles
        combined_text = event_title + ". " + " ".join(
            (a.get("title", "") + ". " + (a.get("content", "") or a.get("summary", ""))[:600])
            for a in articles[:4]
        )

        # 2. Stage 1: Extract atomic claims
        extracted = self.extractor.extract_claims(combined_text, max_claims=max_claims_to_check)
        checkable = [c for c in extracted if c.is_checkable]

        # 3. Stage 2-5: Verify each claim
        verified_claims: list[ClaimVerificationOutput] = []
        contradicted_count = 0
        disputed_count = 0
        supported_count = 0
        unverified_count = 0
        critique_alerts: list[str] = []

        for c in checkable:
            out = await self.verify_claim(
                claim_text=c.text,
                claim_type=c.claim_type.value,
                cluster_articles=articles,
            )
            verified_claims.append(out)

            if out.verdict == VerificationVerdict.WELL_SUPPORTED.value:
                supported_count += 1
            elif out.verdict == VerificationVerdict.CONTRADICTED.value:
                contradicted_count += 1
                critique_alerts.append(f"CONTRADICTED claim detected: '{c.text}'")
            elif out.verdict == VerificationVerdict.DISPUTED.value:
                disputed_count += 1
                critique_alerts.append(f"DISPUTED claim detected: '{c.text}'")
            else:
                unverified_count += 1

        # 4. Overall event trust score calculation
        total = max(len(verified_claims), 1)
        trust = (supported_count * 1.0 + unverified_count * 0.5 + disputed_count * 0.3) / total
        if contradicted_count > 0:
            trust = max(0.1, trust - (contradicted_count * 0.25))

        return EventVerificationResponse(
            event_id=event_id,
            overall_trust_score=round(trust, 2),
            total_claims=len(verified_claims),
            supported_claims_count=supported_count,
            contradicted_claims_count=contradicted_count,
            disputed_claims_count=disputed_count,
            unverified_claims_count=unverified_count,
            claims=verified_claims,
            critique_alerts=critique_alerts,
        )
