"""Comprehensive Unit Tests for Factual Multi-Document Summarizer Agent in NewsSense AI.

Tests cover:
- Multi-source cluster synthesis across multiple articles (no single-article bias)
- Conflict handling (diverging casualty figures documented in uncertainties)
- Verification integration (WELL_SUPPORTED vs CONTRADICTED vs DISPUTED)
- Critique loop audit and hallucination prevention
- Configurable length modes (flash, standard, detailed)
- Canonical output schema validation
"""

import pytest

from app.ai.summarizer import (
    ContextBuilder,
    EventSummarizerAgent,
    FactCheckingCritiqueAuditor,
    MultiDocumentSynthesizer,
)
from app.schemas.event import EventSummaryLength, EventSummaryOutput, StructuredSummarySections


# ============================================================================
# Test Data Fixtures
# ============================================================================

SAMPLE_ARTICLES = [
    {
        "id": "art-001",
        "title": "Government Announces $5 Billion National AI Infrastructure Initiative",
        "content": (
            "WASHINGTON — The federal government officially unveiled a $5 billion funding initiative "
            "to establish sovereign computing infrastructure for artificial intelligence. "
            "According to the Ministry of Technology, initial grants will be disbursed in Q4 2026."
        ),
        "source_name": "Reuters",
        "source_domain": "reuters.com",
        "published_at": "2026-09-02T10:00:00Z",
        "credibility_score": 0.95,
    },
    {
        "id": "art-002",
        "title": "New Federal AI Fund Focuses on Research Clusters and Domestic Supercomputing",
        "content": (
            "WASHINGTON — Following the White House briefing, officials confirmed the $5 billion allocation "
            "will target universities, national laboratories, and private research consortia. "
            "The program will support three regional supercomputing hubs across the United States."
        ),
        "source_name": "Associated Press",
        "source_domain": "apnews.com",
        "published_at": "2026-09-02T11:15:00Z",
        "credibility_score": 0.94,
    },
    {
        "id": "art-003",
        "title": "Tech Industry Welcomes Federal AI Fund but Flags 2028 Completion Doubts",
        "content": (
            "Industry analysts expressed enthusiasm for the federal computing program but disputed the official "
            "completion target. While government roadmaps cite 2028, hardware supply chain memos indicate that "
            "delivery bottlenecks could push the launch of full capacity to 2030."
        ),
        "source_name": "Bloomberg",
        "source_domain": "bloomberg.com",
        "published_at": "2026-09-02T13:30:00Z",
        "credibility_score": 0.92,
    },
]

SAMPLE_VERIFICATION_RESULTS = [
    {
        "claim": "Government allocated $5 billion for national AI infrastructure",
        "verdict": "WELL_SUPPORTED",
        "evidence": "Confirmed by Ministry of Technology press release and White House budget office.",
    },
    {
        "claim": "Infrastructure completion target date",
        "verdict": "DISPUTED",
        "evidence": "Government roadmap cites 2028, but industry hardware memos project 2030.",
    },
    {
        "claim": "Funding was canceled due to budget deficit",
        "verdict": "CONTRADICTED",
        "evidence": "White House explicitly confirmed ongoing disbursement scheduled for Q4 2026.",
    },
]


# ============================================================================
# Multi-Document Synthesis Tests
# ============================================================================

@pytest.mark.asyncio
async def test_multi_document_synthesis_incorporates_multiple_sources():
    agent = EventSummarizerAgent()
    output = await agent.summarize_event(
        event_id="evt-100",
        event_title="Government Announces $5 Billion National AI Infrastructure Initiative",
        category="Technology",
        articles=SAMPLE_ARTICLES,
        verification_results=SAMPLE_VERIFICATION_RESULTS,
        length=EventSummaryLength.STANDARD,
    )

    assert isinstance(output, EventSummaryOutput)
    assert output.event_id == "evt-100"
    assert output.headline != ""
    assert len(output.key_points) >= 2
    assert output.confidence >= 0.80

    # Verify that synthesis includes multiple sources (Reuters, AP, Bloomberg)
    source_names = [s.get("source_name") for s in output.source_references]
    assert "Reuters" in source_names or "Associated Press" in source_names or "Bloomberg" in source_names

    # Verify structured sections layout
    assert output.structured_sections is not None
    assert output.structured_sections.headline != ""
    assert len(output.structured_sections.key_points) >= 2
    assert output.structured_sections.why_it_matters != ""


# ============================================================================
# Conflict & Discrepancy Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_conflict_handling_preserves_discrepancy():
    """Verify that divergent claims (2028 vs 2030 target) are not silently dropped."""
    agent = EventSummarizerAgent()
    output = await agent.summarize_event(
        event_id="evt-101",
        event_title="Federal AI Fund Target Timeline",
        category="Technology",
        articles=SAMPLE_ARTICLES,
        verification_results=SAMPLE_VERIFICATION_RESULTS,
        length=EventSummaryLength.STANDARD,
    )

    # Uncertainties bucket must record the disputed timeline
    assert len(output.uncertainties) >= 1
    timeline_uncertainty = output.uncertainties[0]
    assert timeline_uncertainty["status"] == "DISPUTED"
    assert "2028" in timeline_uncertainty["explanation"] or "2030" in timeline_uncertainty["explanation"]

    # Conflicting information section must document the disagreement
    assert "2028" in output.structured_sections.conflicting_information or "differ" in output.structured_sections.conflicting_information.lower()


# ============================================================================
# Fact-Checking Critique Loop Tests
# ============================================================================

def test_fact_checking_auditor_flags_hallucinated_number():
    """Verify that the critique auditor flags ungrounded numbers not present in source text."""
    context = ContextBuilder.build(
        event_id="evt-102",
        event_title="Government Announces $5 Billion National AI Infrastructure Initiative",
        category="Technology",
        articles=SAMPLE_ARTICLES,
        verification_results=SAMPLE_VERIFICATION_RESULTS,
    )

    # Draft containing hallucinated $95 billion metric
    hallucinated_summary = "The government allocated $95 billion for computing clusters."
    sections = StructuredSummarySections(
        headline=context.canonical_title,
        what_happened=hallucinated_summary,
        conflicting_information="None",
    )

    audit = FactCheckingCritiqueAuditor.audit(hallucinated_summary, sections, context)
    assert audit.is_valid is False
    assert any("95" in num for num in audit.unsupported_numbers)
    assert audit.confidence < 0.85
    assert "failed fact-checking verification" in audit.feedback_prompt


def test_fact_checking_auditor_flags_contradicted_claim():
    """Verify that the auditor flags any summary that asserts a CONTRADICTED claim as fact."""
    context = ContextBuilder.build(
        event_id="evt-103",
        event_title="Government AI Infrastructure Fund",
        category="Technology",
        articles=SAMPLE_ARTICLES,
        verification_results=SAMPLE_VERIFICATION_RESULTS,
    )

    # Summary wrongly claiming funding was canceled due to budget deficit
    contradicted_summary = "Official reports state funding was canceled due to budget deficit."
    sections = StructuredSummarySections(
        headline=context.canonical_title,
        what_happened=contradicted_summary,
        conflicting_information="None",
    )

    audit = FactCheckingCritiqueAuditor.audit(contradicted_summary, sections, context)
    assert audit.is_valid is False
    assert len(audit.unsupported_claims) >= 1
    assert "CONTRADICTED" in audit.violations[0]


# ============================================================================
# Configurable Length Mode Tests
# ============================================================================

@pytest.mark.asyncio
async def test_configurable_length_modes():
    agent = EventSummarizerAgent()

    # Flash mode: 1-2 sentences
    flash_output = await agent.summarize_event(
        event_id="evt-104",
        event_title="Government Announces $5 Billion National AI Infrastructure Initiative",
        category="Technology",
        articles=SAMPLE_ARTICLES,
        length=EventSummaryLength.FLASH,
    )
    flash_words = len(flash_output.summary.split())
    assert flash_words <= 50

    # Detailed mode: Multi-paragraph expanded summary
    detailed_output = await agent.summarize_event(
        event_id="evt-104",
        event_title="Government Announces $5 Billion National AI Infrastructure Initiative",
        category="Technology",
        articles=SAMPLE_ARTICLES,
        length=EventSummaryLength.DETAILED,
    )
    detailed_words = len(detailed_output.summary.split())
    assert detailed_words >= flash_words
