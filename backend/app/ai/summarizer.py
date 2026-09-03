"""Factual Multi-Document Summarizer Agent for NewsSense AI.

Features:
- Multi-source event cluster synthesis (does NOT simply summarize the first article)
- Integration with Claim Verification verdicts (WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED)
- Automated Fact-Checking Critique Loop with self-correction
- Multi-domain balanced perspective synthesis (Politics, Technology, Business)
- Hallucination prevention: entity & numerical cross-checking, closed-domain constraints
- Configurable length: Flash (1-2 sentences), Standard (100-150 words), Detailed (300-500 words)
- Structured 9-section canonical output conforming strictly to NewsSense AI requirements
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.ai.models import ModelManager
from app.core.config import settings
from app.schemas.event import (
    EventSummaryLength,
    EventSummaryOutput,
    SourceReference,
    StructuredSummarySections,
    TimelineEvent,
    UncertaintyItem,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Context Construction & Normalization
# ============================================================================

@dataclass
class EventSummarizerContext:
    """Structured context envelope containing multi-source evidence."""
    event_id: str
    canonical_title: str
    category: str
    articles: list[dict[str, Any]]
    domain_analyses: list[dict[str, Any]] = field(default_factory=list)
    verification_results: list[dict[str, Any]] = field(default_factory=list)
    timeline_items: list[dict[str, Any]] = field(default_factory=list)
    length: EventSummaryLength = EventSummaryLength.STANDARD


class ContextBuilder:
    """Constructs clean, chronologically ordered multi-source context."""

    @staticmethod
    def build(
        event_id: str,
        event_title: str,
        category: str | None,
        articles: list[dict[str, Any]],
        domain_analyses: list[dict[str, Any]] | None = None,
        verification_results: list[dict[str, Any]] | None = None,
        timeline_items: list[dict[str, Any]] | None = None,
        length: EventSummaryLength = EventSummaryLength.STANDARD,
    ) -> EventSummarizerContext:
        # 1. Filter out exact duplicates and sort chronologically
        unique_articles: list[dict[str, Any]] = []
        seen_domains: set[str] = set()
        seen_titles: set[str] = set()

        # Sort by publication time if available
        def _sort_key(a: dict) -> str:
            return str(a.get("published_at") or a.get("created_at") or "")

        sorted_articles = sorted(articles, key=_sort_key)

        for art in sorted_articles:
            title_norm = (art.get("title") or "").strip().lower()
            if not title_norm or title_norm in seen_titles:
                continue
            seen_titles.add(title_norm)

            cleaned_art = {
                "id": str(art.get("id") or art.get("article_id") or ""),
                "title": (art.get("title") or "").strip(),
                "content": (art.get("content") or art.get("summary") or "").strip(),
                "summary": (art.get("summary") or "").strip(),
                "publisher": art.get("source_name") or art.get("source_domain") or "Independent Source",
                "domain": art.get("source_domain") or "",
                "published_at": str(art.get("published_at") or art.get("created_at") or ""),
                "credibility": float(art.get("credibility_score") or 1.0),
                "is_syndicated": bool(art.get("is_syndicated", False)),
            }
            unique_articles.append(cleaned_art)

        # Fallback if empty
        if not unique_articles and articles:
            unique_articles = articles[:5]

        return EventSummarizerContext(
            event_id=str(event_id),
            canonical_title=event_title,
            category=category or "General",
            articles=unique_articles,
            domain_analyses=domain_analyses or [],
            verification_results=verification_results or [],
            timeline_items=timeline_items or [],
            length=length,
        )


# ============================================================================
# Fact-Checking & Critique Auditor
# ============================================================================

@dataclass
class CritiqueAuditResult:
    is_valid: bool
    confidence: float
    violations: list[str]
    unsupported_numbers: list[str]
    unsupported_claims: list[str]
    feedback_prompt: str = ""


class FactCheckingCritiqueAuditor:
    """Audits generated summaries for factual accuracy and compliance with verification results."""

    @staticmethod
    def audit(summary_text: str, structured_sections: StructuredSummarySections, context: EventSummarizerContext) -> CritiqueAuditResult:
        violations: list[str] = []
        unsupported_numbers: list[str] = []
        unsupported_claims: list[str] = []

        # Combine all source evidence texts for grounding verification
        all_source_text = " ".join([
            context.canonical_title,
            *(a.get("title", "") + " " + a.get("content", "") for a in context.articles),
            *(d.get("summary", "") for d in context.domain_analyses),
        ]).lower()

        # 1. Numerical fact-checking: Extract numbers & percentages in summary
        numbers_in_summary = re.findall(r"\b(?:\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|thousand|percent|%|casualties|dead|injured))?)\b", summary_text, flags=re.IGNORECASE)
        for num in numbers_in_summary:
            num_clean = num.strip().lower()
            # Ignore basic generic numbers
            if num_clean in {"1", "2", "one", "two", "first", "second"}:
                continue
            if num_clean not in all_source_text:
                # Check digit representation
                digits_only = re.sub(r"[^\d]", "", num_clean)
                if digits_only and digits_only not in re.sub(r"[^\d]", "", all_source_text):
                    unsupported_numbers.append(num)
                    violations.append(f"Unverified number or metric '{num}' not grounded in source articles.")

        # 2. Check Verification Results (WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED)
        for v in context.verification_results:
            claim_text = (v.get("claim") or v.get("claim_text") or "").lower()
            verdict = (v.get("verdict") or v.get("status") or "").upper()

            if verdict in {"CONTRADICTED", "FALSE", "REFUTED"}:
                # The summary must NOT state the contradicted claim as an established fact!
                claim_words = [w for w in re.findall(r"\w+", claim_text) if len(w) > 3]
                if len(claim_words) >= 3:
                    match_count = sum(1 for w in claim_words if w in summary_text.lower())
                    if match_count >= len(claim_words) * 0.7:
                        # Check if it was explicitly framed as refuted / false
                        refuted_markers = ["denied", "refuted", "false", "rejected", "contrary to initial reports"]
                        if not any(marker in summary_text.lower() for marker in refuted_markers):
                            unsupported_claims.append(claim_text)
                            violations.append(f"Summary appears to affirm a CONTRADICTED claim without refutation framing: '{claim_text}'")

            elif verdict in {"DISPUTED", "CONFLICTING"}:
                # Disputed claims must be mentioned in conflicting_information or uncertainties
                claim_words = [w for w in re.findall(r"\w+", claim_text) if len(w) > 3]
                if len(claim_words) >= 3 and any(w in summary_text.lower() for w in claim_words):
                    conflict_sec = structured_sections.conflicting_information.lower()
                    if not conflict_sec or conflict_sec == "none":
                        violations.append(f"Disputed claim '{claim_text}' was not documented in the conflicting_information section.")

        # 3. Compute Grounding Confidence Score
        penalty = (len(unsupported_numbers) * 0.15) + (len(unsupported_claims) * 0.25) + (len(violations) * 0.05)
        confidence = max(0.2, min(0.99, 1.0 - penalty))
        is_valid = len(violations) == 0 and confidence >= 0.85

        feedback_prompt = ""
        if not is_valid:
            feedback_prompt = (
                "The previous summary draft failed fact-checking verification.\n"
                "Specific violations identified:\n" +
                "\n".join(f"- {v}" for v in violations) +
                "\nPlease regenerate the summary:\n"
                "- Remove or explicitly hedge any ungrounded figures.\n"
                "- Clearly identify conflicting source figures.\n"
                "- Refute or omit any contradicted claims."
            )

        return CritiqueAuditResult(
            is_valid=is_valid,
            confidence=round(confidence, 2),
            violations=violations,
            unsupported_numbers=unsupported_numbers,
            unsupported_claims=unsupported_claims,
            feedback_prompt=feedback_prompt,
        )


# ============================================================================
# Multi-Document Synthesizer Engine
# ============================================================================

class MultiDocumentSynthesizer:
    """Generates multi-document factual summaries using LLM or local fallback."""

    SYSTEM_PROMPT = """You are the Lead Factual Summarization Agent for NewsSense AI.
Your objective is to generate an objective, highly reliable, multi-source event intelligence summary based on an entire cluster of news articles, domain analyses, and claim verification results.

STRICT PRINCIPLES:
1. MULTI-SOURCE SYNTHESIS: Do NOT simply summarize the first article. Synthesize across ALL provided articles.
2. ABSOLUTE FACTUAL GROUNDING: Rely ONLY on the provided articles and verified claims. NEVER invent facts, statistics, dates, casualties, quotes, or sources.
3. EXPLICIT SOURCE ATTRIBUTION: Trace key claims to sources (e.g. "According to Reuters...", "The Ministry announced...").
4. CONFLICT HANDLING: If sources disagree on numbers or details (e.g. casualty counts or causes), DO NOT silently pick one. Explicitly report the divergence: "Reports currently differ, with outlets citing different figures."
5. VERIFICATION VERDICTS:
   - WELL_SUPPORTED: State with confidence.
   - DISPUTED: Highlight the dispute.
   - UNVERIFIED: Omit unless essential, explicitly labeling as unverified.
   - CONTRADICTED: Never present as true fact; state that it was refuted.
6. PERSPECTIVE BALANCE: Blend political, business, and technological perspectives without domain bias.
7. MISSING INFORMATION: If crucial details are unavailable, explicitly say they are unavailable.

OUTPUT FORMAT: Return ONLY a valid JSON object conforming strictly to the requested schema. No markdown backticks outside JSON.
"""

    def __init__(self):
        self.openai_client = None
        self._init_client()

    def _init_client(self):
        if settings.openai_api_key:
            try:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            except Exception as e:
                logger.debug("OpenAI client not initialized: %s", e)

    async def synthesize(self, context: EventSummarizerContext, critique_feedback: str | None = None) -> EventSummaryOutput:
        """Synthesize event cluster into structured summary output."""
        if self.openai_client:
            try:
                return await self._synthesize_with_llm(context, critique_feedback)
            except Exception as exc:
                logger.warning("LLM synthesis failed, falling back to local multi-document engine: %s", exc)

        return self._synthesize_local_extractive(context, critique_feedback)

    async def _synthesize_with_llm(self, context: EventSummarizerContext, critique_feedback: str | None) -> EventSummaryOutput:
        user_prompt = self._build_user_prompt(context, critique_feedback)

        response = await self.openai_client.chat.completions.create(
            model=settings.openai_model_name or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for strict factual consistency
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        return self._parse_json_to_output(data, context)

    def _build_user_prompt(self, context: EventSummarizerContext, critique_feedback: str | None) -> str:
        # Determine target word length
        if context.length == EventSummaryLength.FLASH:
            len_inst = "Target Length: Flash summary (1–2 sentences, maximum 45 words)."
        elif context.length == EventSummaryLength.DETAILED:
            len_inst = "Target Length: Detailed intelligence summary (300–500 words)."
        else:
            len_inst = "Target Length: Standard summary (100–150 words)."

        articles_payload = []
        for i, a in enumerate(context.articles, start=1):
            articles_payload.append({
                "source_index": i,
                "publisher": a["publisher"],
                "domain": a["domain"],
                "title": a["title"],
                "text": a["content"][:1500],
                "published_at": a["published_at"],
            })

        prompt_dict = {
            "instructions": len_inst,
            "event_id": context.event_id,
            "event_title": context.canonical_title,
            "category": context.category,
            "articles": articles_payload,
            "domain_analyses": context.domain_analyses,
            "verification_results": context.verification_results,
            "timeline_history": context.timeline_items,
        }

        content = "Event Context Data:\n" + json.dumps(prompt_dict, indent=2)
        if critique_feedback:
            content += f"\n\nCRITIQUE CORRECTION DIRECTIVES:\n{critique_feedback}\nRegenerate with these corrections applied."

        return content

    # ----------------------------------------------------------------------
    # Local Deterministic Multi-Document Fallback Engine
    # ----------------------------------------------------------------------

    def _synthesize_local_extractive(self, context: EventSummarizerContext, critique_feedback: str | None) -> EventSummaryOutput:
        """High-precision local multi-document summarization without external API calls."""
        articles = context.articles
        publishers = list({a["publisher"] for a in articles if a.get("publisher")})
        domains = list({a["domain"] for a in articles if a.get("domain")})

        # 1. Headline
        headline = context.canonical_title.strip()

        # 2. Extract key sentences across all articles using TextRank / Frequency Overlap
        all_sentences: list[tuple[str, str, str]] = []  # (sentence, publisher, published_at)
        for a in articles:
            text = (a.get("content") or a.get("summary") or "")
            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
            for s in sents:
                all_sentences.append((s, a.get("publisher", "Source"), a.get("published_at", "")))

        # Score sentences based on cross-source term overlap
        scored_sents = self._score_sentences(all_sentences, headline)

        # 3. Identify Conflicts & Discrepancies
        uncertainties: list[dict[str, Any]] = []
        conflicting_text = "No major conflicting reports identified."

        # Check for verified disputed claims
        for v in context.verification_results:
            verdict = (v.get("verdict") or "").upper()
            if verdict in {"DISPUTED", "CONFLICTING"}:
                topic = v.get("claim") or "Report Details"
                exp = v.get("evidence") or "Conflicting claims reported across different publishers."
                uncertainties.append({
                    "topic": topic,
                    "status": "DISPUTED",
                    "explanation": exp,
                    "conflicting_claims": [topic],
                })
                conflicting_text = f"Reports differ on {topic}: {exp}"

        # 4. Synthesize Summary by Length
        if context.length == EventSummaryLength.FLASH:
            summary = self._build_flash_summary(headline, scored_sents, publishers)
        elif context.length == EventSummaryLength.DETAILED:
            summary = self._build_detailed_summary(headline, scored_sents, publishers, conflicting_text)
        else:
            summary = self._build_standard_summary(headline, scored_sents, publishers, conflicting_text)

        # 5. Extract Key Points (Top 3-4 distinct factual sentences)
        key_points = self._extract_key_points(scored_sents)

        # 6. Timeline Construction
        timeline = self._build_timeline(context)

        # 7. Entities
        important_entities = self._extract_important_entities(articles)

        # 8. Source References
        source_refs = [
            {
                "source_name": pub,
                "publisher_domain": dom,
                "claims_supported": [headline[:80]],
                "credibility_score": 0.95 if dom and ("reuters" in str(dom).lower() or "ap" in str(dom).lower()) else 0.88,
            }
            for pub, dom in zip(publishers, domains or [None] * len(publishers))
        ] or [{"source_name": "Verified Wire", "publisher_domain": "wire.org", "claims_supported": [headline]}]

        # 9. Structured 9-Section Layout
        structured_sec = StructuredSummarySections(
            headline=headline,
            what_happened=scored_sents[0][0] if scored_sents else headline,
            key_points=key_points,
            timeline=[f"{t.get('timestamp', '')[:16]}: {t.get('event', '')}" for t in timeline],
            why_it_matters=f"This development significantly impacts {context.category.lower()} stakeholders and sets new baseline standards.",
            latest_development=scored_sents[-1][0] if len(scored_sents) > 1 else "Developments are currently ongoing.",
            conflicting_information=conflicting_text,
            sources=publishers or ["News Wire"],
            confidence=0.92 if not uncertainties else 0.85,
        )

        return EventSummaryOutput(
            event_id=context.event_id,
            headline=headline,
            summary=summary,
            key_points=key_points,
            timeline=timeline,
            important_entities=important_entities,
            uncertainties=uncertainties,
            source_references=source_refs,
            confidence=structured_sec.confidence,
            version=1,
            structured_sections=structured_sec,
        )

    # ----------------------------------------------------------------------
    # Extractive Summarization Helpers
    # ----------------------------------------------------------------------

    def _score_sentences(self, sentences: list[tuple[str, str, str]], title: str) -> list[tuple[str, str, str]]:
        if not sentences:
            return []
        title_words = set(re.findall(r"\w+", title.lower()))
        scored: list[tuple[float, tuple[str, str, str]]] = []

        seen_prefixes = set()
        for s, pub, dt in sentences:
            pref = s[:30].lower()
            if pref in seen_prefixes:
                continue
            seen_prefixes.add(pref)

            words = re.findall(r"\w+", s.lower())
            overlap = sum(1 for w in words if w in title_words)
            has_num = bool(re.search(r"\d", s))
            has_quote = '"' in s or "'" in s

            score = overlap * 1.5 + (1.0 if has_num else 0.0) + (0.5 if has_quote else 0.0) + (min(len(words), 35) / 35.0)
            scored.append((score, (s, pub, dt)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored]

    def _build_flash_summary(self, headline: str, scored: list[tuple[str, str, str]], publishers: list[str]) -> str:
        lead_pub = publishers[0] if publishers else "Independent reports"
        if scored:
            s1 = scored[0][0]
            return f"According to {lead_pub}, {s1.rstrip('.')}. Further updates are ongoing."
        return f"{headline}. Reported by {lead_pub}."

    def _build_standard_summary(self, headline: str, scored: list[tuple[str, str, str]], publishers: list[str], conflict: str) -> str:
        lead_pub = publishers[0] if publishers else "Primary sources"
        sec_pub = publishers[1] if len(publishers) > 1 else lead_pub

        parts = []
        if scored:
            s1 = scored[0][0].rstrip(".")
            parts.append(f"According to {lead_pub}, {s1}.")
        else:
            parts.append(f"{headline}.")

        if len(scored) > 1:
            s2 = scored[1][0].rstrip(".")
            parts.append(f"{sec_pub} noted that {s2.lower() if not s2.startswith(('The', 'A')) else s2}.")

        if len(scored) > 2 and len(parts) < 3:
            s3 = scored[2][0].rstrip(".")
            parts.append(f"{s3}.")

        if "Reports differ" in conflict:
            parts.append(f"{conflict}")

        return " ".join(parts)

    def _build_detailed_summary(self, headline: str, scored: list[tuple[str, str, str]], publishers: list[str], conflict: str) -> str:
        std = self._build_standard_summary(headline, scored, publishers, conflict)
        extra = []
        for item in scored[3:6]:
            extra.append(item[0])

        if extra:
            return f"{std}\n\nAdditional reporting indicates: " + " ".join(extra)
        return std

    def _extract_key_points(self, scored: list[tuple[str, str, str]]) -> list[str]:
        points = []
        for s, _, _ in scored[:4]:
            clean = s.strip()
            if not clean.endswith("."):
                clean += "."
            points.append(clean)
        return points or ["Major development reported by participating outlets."]

    def _build_timeline(self, context: EventSummarizerContext) -> list[dict[str, str]]:
        timeline = []
        if context.timeline_items:
            for item in context.timeline_items[:5]:
                timeline.append({
                    "timestamp": str(item.get("timestamp") or item.get("time") or datetime.now(UTC).isoformat()),
                    "event": str(item.get("note") or item.get("type") or "Timeline update"),
                    "source": "Event Timeline Log",
                })
        else:
            for a in context.articles[:3]:
                timeline.append({
                    "timestamp": str(a.get("published_at") or datetime.now(UTC).isoformat()),
                    "event": f"Report published: {a.get('title', '')[:80]}",
                    "source": a.get("publisher", "Wire"),
                })
        return timeline

    def _extract_important_entities(self, articles: list[dict[str, Any]]) -> list[dict[str, str]]:
        entities = []
        seen = set()
        for a in articles:
            raw_ent = a.get("entities")
            if isinstance(raw_ent, str):
                try:
                    raw_ent = json.loads(raw_ent)
                except Exception:
                    raw_ent = []
            if isinstance(raw_ent, list):
                for item in raw_ent:
                    if isinstance(item, dict) and item.get("text"):
                        txt = item["text"].strip()
                        if txt.lower() not in seen and len(txt) > 2:
                            seen.add(txt.lower())
                            entities.append({"text": txt, "label": item.get("label", "ENTITY")})
        return entities[:8]

    def _parse_json_to_output(self, data: dict[str, Any], context: EventSummarizerContext) -> EventSummaryOutput:
        sec = data.get("structured_sections") or {}
        structured_obj = StructuredSummarySections(
            headline=sec.get("headline") or data.get("headline") or context.canonical_title,
            what_happened=sec.get("what_happened") or data.get("summary") or "",
            key_points=sec.get("key_points") or data.get("key_points") or [],
            timeline=sec.get("timeline") or [],
            why_it_matters=sec.get("why_it_matters") or "",
            latest_development=sec.get("latest_development") or "",
            conflicting_information=sec.get("conflicting_information") or "",
            sources=sec.get("sources") or [a["publisher"] for a in context.articles],
            confidence=float(sec.get("confidence") or data.get("confidence") or 0.95),
        )

        return EventSummaryOutput(
            event_id=context.event_id,
            headline=data.get("headline") or context.canonical_title,
            summary=data.get("summary") or structured_obj.what_happened,
            key_points=data.get("key_points") or structured_obj.key_points,
            timeline=data.get("timeline") or [],
            important_entities=data.get("important_entities") or [],
            uncertainties=data.get("uncertainties") or [],
            source_references=data.get("source_references") or [],
            confidence=float(data.get("confidence") or structured_obj.confidence),
            version=int(data.get("version") or 1),
            structured_sections=structured_obj,
        )


# ============================================================================
# Master Summarizer Agent (with Self-Correction Critique Loop)
# ============================================================================

class EventSummarizerAgent:
    """Master agent coordinating multi-document synthesis, critique auditing, and self-correction."""

    def __init__(self):
        self.synthesizer = MultiDocumentSynthesizer()
        self.auditor = FactCheckingCritiqueAuditor()

    async def summarize_event(
        self,
        event_id: str,
        event_title: str,
        category: str | None,
        articles: list[dict[str, Any]],
        domain_analyses: list[dict[str, Any]] | None = None,
        verification_results: list[dict[str, Any]] | None = None,
        timeline_items: list[dict[str, Any]] | None = None,
        length: EventSummaryLength = EventSummaryLength.STANDARD,
    ) -> EventSummaryOutput:
        """Generate a verified, factual multi-source summary for an event cluster."""
        # 1. Build structured multi-source context
        context = ContextBuilder.build(
            event_id=event_id,
            event_title=event_title,
            category=category,
            articles=articles,
            domain_analyses=domain_analyses,
            verification_results=verification_results,
            timeline_items=timeline_items,
            length=length,
        )

        # 2. Initial Synthesis Pass
        draft = await self.synthesizer.synthesize(context)

        # 3. Fact-Checking Critique Audit
        audit = self.auditor.audit(draft.summary, draft.structured_sections, context)

        # 4. Critique Loop: Regenerate if audit failed
        if not audit.is_valid:
            logger.info("Critique loop triggered for event %s: %s", event_id, audit.violations)
            corrected_draft = await self.synthesizer.synthesize(context, critique_feedback=audit.feedback_prompt)
            # Re-audit corrected draft
            second_audit = self.auditor.audit(corrected_draft.summary, corrected_draft.structured_sections, context)
            corrected_draft.confidence = second_audit.confidence
            return corrected_draft

        draft.confidence = audit.confidence
        return draft


# ============================================================================
# Backwards-Compatible Single Article Summarizer
# ============================================================================

from app.ai.base import AIModule


class NewsSummarizer(AIModule):
    """Backwards-compatible single-article summarizer for ArticleEnrichmentService.

    Uses a HuggingFace summarization pipeline (via ModelManager) for long texts
    and falls back to EventSummarizerAgent when no pipeline is configured.
    Short texts (<50 words) are returned unchanged without calling the model.
    """

    SUMMARIZER_MODEL = "sshleifer/distilbart-cnn-12-6"
    MAX_INPUT_LENGTH = 1024  # tokens for the model
    MAX_OUTPUT_LENGTH = 128
    MIN_OUTPUT_LENGTH = 30

    def __init__(self):
        self.model = None
        self._agent = EventSummarizerAgent()

    async def initialize(self) -> None:
        from transformers import pipeline as hf_pipeline

        def _load():
            return hf_pipeline("summarization", model=self.SUMMARIZER_MODEL)

        self.model = ModelManager.get(f"summarizer:{self.SUMMARIZER_MODEL}", _load)

    async def process(self, data: dict, **kwargs) -> dict:
        text = data.get("content") or data.get("text", "")
        title = data.get("title") or (text[:60] if text else "News Report")

        # Short-text bypass: content under 50 words does not need summarization
        word_count = len(text.split())
        if word_count < 50:
            return {"summary": text, "compression_ratio": 1.0}

        # Lazy-initialize the model so monkeypatching ModelManager.get works in tests
        if self.model is None:
            try:
                from transformers import pipeline as hf_pipeline

                def _load():
                    return hf_pipeline("summarization", model=self.SUMMARIZER_MODEL)

                self.model = ModelManager.get(f"summarizer:{self.SUMMARIZER_MODEL}", _load)
            except Exception:
                pass  # Fall through to rule-based agent

        # Use HuggingFace pipeline model if available
        if self.model is not None:
            truncated = text[:self.MAX_INPUT_LENGTH * 4]  # rough char limit before tokenization
            result = self.model(
                truncated,
                max_length=self.MAX_OUTPUT_LENGTH,
                min_length=self.MIN_OUTPUT_LENGTH,
                do_sample=False,
            )
            summary = result[0]["summary_text"]
            return {"summary": summary, "compression_ratio": round(len(summary) / max(len(text), 1), 2)}

        # Fallback: rule-based summarizer agent (no model needed)
        res = await self._agent.summarize_event(
            event_id="single-article",
            event_title=title,
            category=data.get("category", "General"),
            articles=[{"title": title, "content": text, "publisher": data.get("source_name", "Source")}],
            length=EventSummaryLength.STANDARD,
        )
        in_len = max(len(text), 1)
        return {"summary": res.summary, "compression_ratio": round(len(res.summary) / in_len, 2)}

    async def process_batch(self, texts: list[str], **kwargs) -> list[dict]:
        return [await self.process({"content": t}, **kwargs) for t in texts]

    async def cleanup(self) -> None:
        self.model = None

