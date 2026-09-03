"""Atomic Claim Extractor and Classification Module for NewsSense AI.

Stage 1: Extract atomic, independently checkable claims.
- Preserves names, numbers, dates, locations, attribution.
- Classifies claims into:
  * FACTUAL: Real-world state of affairs or historical occurrences.
  * ATTRIBUTION: Statements about who reported or announced what.
  * NUMERICAL: Quantitative measurements, statistics, counts, casualty figures.
  * PREDICTION: Future projections and forecasts.
  * OPINION: Subjective value judgements, moral assertions, rhetoric (skipped from factual checks).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.schemas.verification import ClaimType


@dataclass
class ExtractedClaim:
    claim_id: str
    text: str
    claim_type: ClaimType
    entities: list[str] = field(default_factory=list)
    source_attribution: str | None = None
    is_checkable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class ClaimExtractor:
    """Extracts atomic checkable claims from news texts."""

    ATTRIBUTION_VERBS = {
        "said", "stated", "announced", "reported", "claimed", "alleged",
        "declared", "confirmed", "denied", "noted", "emphasized", "testified"
    }

    OPINION_MARKERS = {
        "i believe", "in my opinion", "we feel", "arguably", "beautiful",
        "terrible", "wonderful", "should", "ought to", "disgraceful",
        "outrageous", "heroic", "must ensure", "hopefully"
    }

    PREDICTION_MARKERS = {
        "will likely", "projected to", "forecast to", "expected to by",
        "will reach", "predicted to", "anticipates that by", "is poised to"
    }

    @classmethod
    def extract_claims(cls, text: str, max_claims: int = 10) -> list[ExtractedClaim]:
        """Parse raw article text and extract atomic, typed claims."""
        if not text:
            return []

        # 1. Clean and split into candidate sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]

        extracted: list[ExtractedClaim] = []
        for sent in sentences:
            sub_claims = cls._decompose_sentence(sent)
            for sc_text, c_type, attr in sub_claims:
                if len(extracted) >= max_claims:
                    break

                entities = cls._extract_entities(sc_text)
                is_checkable = (c_type != ClaimType.OPINION)

                extracted.append(
                    ExtractedClaim(
                        claim_id=f"clm-{uuid.uuid4().hex[:8]}",
                        text=sc_text,
                        claim_type=c_type,
                        entities=entities,
                        source_attribution=attr,
                        is_checkable=is_checkable,
                    )
                )

            if len(extracted) >= max_claims:
                break

        return extracted

    @classmethod
    def _decompose_sentence(cls, sentence: str) -> list[tuple[str, ClaimType, str | None]]:
        """Decomposes a sentence into atomic claims (e.g. Attribution vs Core assertion)."""
        results: list[tuple[str, ClaimType, str | None]] = []
        s_lower = sentence.lower()

        # Check for OPINION first
        if any(marker in s_lower for marker in cls.OPINION_MARKERS):
            return [(sentence, ClaimType.OPINION, None)]

        # Check for ATTRIBUTION pattern: "[Subject] [said/announced/reported] (that) [Clause]"
        attr_match = re.search(
            r"^([A-Z][a-zA-Z\s\.,\-]+?)\s+(said|stated|announced|reported|claimed|confirmed|testified)\s+(?:that\s+)?(.+)$",
            sentence,
            flags=re.IGNORECASE,
        )

        if attr_match:
            speaker = attr_match.group(1).strip()
            verb = attr_match.group(2).strip().lower()
            inner_assertion = attr_match.group(3).strip()

            # Claim 1: Attribution Claim
            attribution_claim = f"{speaker} {verb} that {inner_assertion}"
            results.append((attribution_claim, ClaimType.ATTRIBUTION, speaker))

            # Claim 2: Underlying Factual/Numerical/Prediction Claim
            inner_type = cls._classify_claim_text(inner_assertion)
            results.append((inner_assertion, inner_type, speaker))
            return results

        # Single clause assertion
        claim_type = cls._classify_claim_text(sentence)
        results.append((sentence, claim_type, None))
        return results

    @classmethod
    def _classify_claim_text(cls, text: str) -> ClaimType:
        """Classify an atomic assertion into its taxonomy."""
        t_lower = text.lower()

        # Prediction check
        if any(p in t_lower for p in cls.PREDICTION_MARKERS) or re.search(r"\bwill\s+\w+\s+in\s+20\d\d\b", t_lower):
            return ClaimType.PREDICTION

        # Numerical check: contains numbers, percentages, currency, casualties
        if re.search(r"\b(?:\$?\d+(?:,\d{3})*(?:\.\d+)?%?|\b(?:billion|million|thousand|percent)\b)\b", text, flags=re.IGNORECASE):
            return ClaimType.NUMERICAL

        return ClaimType.FACTUAL

    @classmethod
    def _extract_entities(cls, text: str) -> list[str]:
        """Extract key named entities, numbers, and proper nouns."""
        entities = []
        # Proper nouns & capital sequences
        proper_nouns = re.findall(r"\b[A-Z][a-zA-Z0-9_\-\.]{2,}(?:\s+[A-Z][a-zA-Z0-9_\-\.]+)*\b", text)
        for p in proper_nouns:
            if p.lower() not in {"the", "according", "after", "yesterday", "today", "tomorrow"}:
                entities.append(p)

        # Numbers & currency
        numbers = re.findall(r"\b(?:\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|percent|%))?)\b", text, flags=re.IGNORECASE)
        for n in numbers:
            if n not in {"1", "2"}:
                entities.append(n)

        return list(dict.fromkeys(entities))
