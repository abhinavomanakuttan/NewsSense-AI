"""Master Bias & Media Framing Agent for NewsSense AI.

Analyzes how multiple news publishers frame the SAME EVENT:
- Analyzes headlines, lead paragraphs, entity emphasis, and fact omission.
- Profiles linguistic markers: emotional terms, sensationalism, voice, and certainty.
- Enforces political safeguards: strictly avoids crude ideological labeling
  ('left', 'right', 'pro-government', 'anti-government') without empirical evidence.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.ai.framing_analyzer import (
    CrossSourceSynthesizer,
    OmissionMatrixBuilder,
    SourceDiscourseProfiler,
)
from app.schemas.framing import (
    EventFramingResponse,
    FramingFeatures,
    SourceComparison,
)

logger = logging.getLogger(__name__)


class FramingAgent:
    """Master agent for cross-publisher media framing and discourse analysis."""

    PROHIBITED_POLITICAL_TAGS = [
        "left-wing", "right-wing", "far-left", "far-right", "liberal bias",
        "conservative bias", "pro-government propaganda", "anti-government bias",
        "biased publisher", "partisan hack"
    ]

    def __init__(self):
        self.profiler = SourceDiscourseProfiler()
        self.omission_builder = OmissionMatrixBuilder()
        self.synthesizer = CrossSourceSynthesizer()

    def analyze_event_framing(
        self,
        event_id: str,
        event_title: str,
        articles: list[dict[str, Any]],
        verified_claims: list[str] | None = None,
    ) -> EventFramingResponse:
        """Execute full multi-source framing analysis across cluster articles."""
        if not articles:
            return EventFramingResponse(
                event_id=event_id,
                sources=[],
                comparisons=[],
                framing_patterns=["Insufficient articles to establish comparative framing."],
                language_patterns=[],
                areas_of_agreement=[],
                areas_of_difference=[],
                confidence=0.50,
            )

        comparisons: list[SourceComparison] = []
        source_names: list[str] = []

        for art in articles:
            src_name = art.get("source_name") or art.get("source", {}).get("name") or "News Publisher"
            headline = art.get("title", "")
            content = art.get("content", "") or art.get("summary", "")
            lead_para = self._extract_lead_paragraph(content)

            # 1. Linguistic & Discourse Profile
            profile = self.profiler.profile_article(
                headline=headline,
                lead_paragraph=lead_para,
                full_content=content,
            )

            # 2. Key Facts vs Omissions
            key_facts, omitted_facts = self.omission_builder.analyze_facts(
                source_text=f"{headline} {content}",
                all_articles=articles,
                verified_claims=verified_claims,
            )

            # 3. Extract Emphasized Entities (prominence in headline & lead)
            entities = self._extract_salient_entities(headline, lead_para)

            # 4. Assemble Source Comparison
            features = FramingFeatures(
                primary_frame=profile.primary_frame,
                narrative_emphasis=profile.narrative_emphasis,
                emotional_intensity=profile.emotional_intensity,
                sensationalism_score=profile.sensationalism_score,
                active_voice_ratio=profile.active_voice_ratio,
                certainty_level=profile.certainty_level,
                quoted_actors=profile.quoted_actors,
            )

            comp = SourceComparison(
                source=src_name,
                headline=headline,
                dominant_topics=profile.dominant_topics,
                entities_emphasized=entities,
                tone=profile.tone,
                sentiment=profile.sentiment,
                key_facts=key_facts,
                omitted_or_less_emphasized_facts=omitted_facts,
                framing_features=features,
            )
            comparisons.append(comp)
            if src_name not in source_names:
                source_names.append(src_name)

        # 5. Cross-Source Synthesis
        comp_dicts = [c.model_dump() for c in comparisons]
        agreement, differences, framing_patterns, language_patterns = self.synthesizer.synthesize_event(
            comparisons=comp_dicts,
            event_title=event_title,
        )

        # 6. Apply Political Safeguard Filter
        clean_framing_patterns = [self._enforce_safeguards(p) for p in framing_patterns]
        clean_differences = [self._enforce_safeguards(d) for d in differences]

        # Calculate confidence based on source count and article depth
        conf = min(0.95, 0.70 + (len(comparisons) * 0.08))

        return EventFramingResponse(
            event_id=event_id,
            sources=source_names,
            comparisons=comparisons,
            framing_patterns=clean_framing_patterns,
            language_patterns=language_patterns,
            areas_of_agreement=agreement,
            areas_of_difference=clean_differences,
            confidence=round(conf, 2),
        )

    @classmethod
    def _extract_lead_paragraph(cls, text: str) -> str:
        """Extract the first substantial paragraph."""
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 30]
        if paragraphs:
            return paragraphs[0]
        # If no explicit line breaks, take first 2 sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return " ".join(sentences[:2]) if sentences else text[:300]

    @classmethod
    def _extract_salient_entities(cls, headline: str, lead: str) -> list[str]:
        """Extract high-salience entities prioritized in headline and lead paragraph."""
        combined = f"{headline}. {lead}"
        caps = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", combined)
        stopwords = {"The", "This", "That", "When", "After", "Before", "According", "Officials", "Government"}
        entities: list[str] = []
        for c in caps:
            if c not in stopwords and len(c) > 3 and c not in entities:
                entities.append(c)
        return entities[:4]

    @classmethod
    def _enforce_safeguards(cls, text: str) -> str:
        """Ensure no crude ideological slurs or unsupported labels exist in generated output."""
        sanitized = text
        for tag in cls.PROHIBITED_POLITICAL_TAGS:
            sanitized = re.sub(re.escape(tag), "divergent editorial perspective", sanitized, flags=re.IGNORECASE)
        return sanitized
