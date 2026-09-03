"""Tests for routing logic — pipeline selection, multi-domain detection, review flagging.

WHY comprehensive routing tests:
- Routing determines which agents process which events.
- Incorrect routing means events get wrong analysis or skip critical steps.
- Multi-domain detection must be accurate to avoid unnecessary processing.
"""

import pytest

from app.pipeline.orchestrator.routing import (
    CATEGORY_PIPELINES,
    DEFAULT_PIPELINE,
    get_multi_domain_agents,
    get_parallel_groups,
    get_pipeline_for_event,
    should_flag_for_review,
    should_skip_verification,
)
from app.pipeline.orchestrator.state import (
    ArticleInfo,
    EventProcessingState,
    EventStatus,
    VerificationResult,
    BiasAnalysis,
)


class TestGetPipelineForEvent:
    """Tests for per-category pipeline selection."""

    def test_politics_pipeline(self):
        """Politics events should have the full verification pipeline."""
        state = EventProcessingState(event_id="EVT-1", category="politics")
        pipeline = get_pipeline_for_event(state)
        assert "politics_agent" in pipeline
        assert "claim_extraction" in pipeline
        assert "evidence_retrieval" in pipeline
        assert "nli_stance" in pipeline
        assert "bias_framing" in pipeline

    def test_sports_pipeline(self):
        """Sports events should skip claim extraction and bias analysis."""
        state = EventProcessingState(event_id="EVT-1", category="sports")
        pipeline = get_pipeline_for_event(state)
        assert "sports_agent" in pipeline
        assert "claim_extraction" not in pipeline
        assert "bias_framing" not in pipeline

    def test_entertainment_pipeline(self):
        """Entertainment should have minimal pipeline."""
        state = EventProcessingState(event_id="EVT-1", category="entertainment")
        pipeline = get_pipeline_for_event(state)
        assert "entertainment_agent" in pipeline
        assert "summarization" in pipeline
        assert "claim_extraction" not in pipeline

    def test_unknown_category_uses_default(self):
        """Unknown categories should fall back to default pipeline."""
        state = EventProcessingState(event_id="EVT-1", category="unknown_category")
        pipeline = get_pipeline_for_event(state)
        assert pipeline == DEFAULT_PIPELINE

    def test_no_category_uses_default(self):
        """No category should fall back to default pipeline."""
        state = EventProcessingState(event_id="EVT-1")
        pipeline = get_pipeline_for_event(state)
        assert pipeline == DEFAULT_PIPELINE

    def test_all_categories_have_pipelines(self):
        """Every known category should have a defined pipeline."""
        known_categories = [
            "politics", "technology", "sports", "science",
            "business", "entertainment", "world_news", "environment",
        ]
        for cat in known_categories:
            assert cat in CATEGORY_PIPELINES, f"Missing pipeline for {cat}"

    def test_pipeline_starts_with_dedup(self):
        """All pipelines should start with deduplication."""
        for cat, pipeline in CATEGORY_PIPELINES.items():
            assert pipeline[0] == "deduplication", f"{cat} pipeline should start with dedup"

    def test_pipeline_ends_with_embedding(self):
        """All pipelines should end with embedding."""
        for cat, pipeline in CATEGORY_PIPELINES.items():
            assert pipeline[-1] == "embedding", f"{cat} pipeline should end with embedding"


class TestGetMultiDomainAgents:
    """Tests for multi-domain agent detection."""

    def test_single_domain_politics(self):
        """Pure politics articles should only route to politics agent."""
        state = EventProcessingState(
            event_id="EVT-1",
            category="politics",
            articles=[
                ArticleInfo(id="A1", title="Congress votes on new bill", url="https://example.com"),
            ],
        )
        agents = get_multi_domain_agents(state)
        assert "politics_agent" in agents

    def test_multi_domain_detection(self):
        """Articles with cross-domain signals should trigger multiple agents."""
        state = EventProcessingState(
            event_id="EVT-1",
            category="politics",
            articles=[
                ArticleInfo(
                    id="A1",
                    title="Government announces major AI investment in tech company market",
                    url="https://example.com",
                ),
            ],
        )
        agents = get_multi_domain_agents(state)
        # Should detect politics (primary) + technology + business (cross-domain)
        assert "politics_agent" in agents
        assert "technology_agent" in agents
        assert "business_agent" in agents

    def test_sports_no_cross_domain(self):
        """Sports should primarily route to sports agent."""
        state = EventProcessingState(
            event_id="EVT-1",
            category="sports",
            articles=[
                ArticleInfo(id="A1", title="Team wins championship", url="https://example.com"),
            ],
        )
        agents = get_multi_domain_agents(state)
        assert "sports_agent" in agents
        # Should not trigger cross-domain agents for simple sports news
        assert "politics_agent" not in agents


class TestShouldSkipVerification:
    """Tests for verification skip logic."""

    def test_skip_for_high_confidence_high_credibility(self):
        """High confidence + high credibility sources should skip verification."""
        state = EventProcessingState(
            event_id="EVT-1",
            classification_confidence=0.98,
            articles=[
                ArticleInfo(id="A1", title="Test", url="https://example.com",
                           source_credibility=0.9),
            ],
        )
        assert should_skip_verification(state) is True

    def test_no_skip_for_low_confidence(self):
        """Low confidence should not skip verification."""
        state = EventProcessingState(
            event_id="EVT-1",
            classification_confidence=0.5,
            articles=[
                ArticleInfo(id="A1", title="Test", url="https://example.com",
                           source_credibility=0.9),
            ],
        )
        assert should_skip_verification(state) is False

    def test_no_skip_for_low_credibility(self):
        """Low credibility sources should not skip verification."""
        state = EventProcessingState(
            event_id="EVT-1",
            classification_confidence=0.98,
            articles=[
                ArticleInfo(id="A1", title="Test", url="https://example.com",
                           source_credibility=0.5),
            ],
        )
        assert should_skip_verification(state) is False


class TestShouldFlagForReview:
    """Tests for human review flagging logic."""

    def test_flag_for_low_confidence_with_verifications(self):
        """Low confidence with verification results should flag for review."""
        state = EventProcessingState(
            event_id="EVT-1",
            confidence=0.2,
            verification_results=[
                VerificationResult(claim_id="C1", verdict="disputed", confidence=0.3),
            ],
        )
        assert should_flag_for_review(state) is True

    def test_flag_for_contradictory_verdicts(self):
        """Mixed verified/false verdicts should flag for review."""
        state = EventProcessingState(
            event_id="EVT-1",
            confidence=0.7,
            verification_results=[
                VerificationResult(claim_id="C1", verdict="verified", confidence=0.9),
                VerificationResult(claim_id="C2", verdict="false", confidence=0.8),
            ],
        )
        assert should_flag_for_review(state) is True

    def test_flag_for_low_source_agreement(self):
        """Low source agreement should flag for review."""
        state = EventProcessingState(
            event_id="EVT-1",
            confidence=0.7,
            verification_results=[
                VerificationResult(claim_id="C1", verdict="verified", confidence=0.9),
            ],
            bias_analysis=BiasAnalysis(source_agreement_score=0.2),
        )
        assert should_flag_for_review(state) is True

    def test_no_flag_for_high_confidence(self):
        """High confidence with consistent results should not flag."""
        state = EventProcessingState(
            event_id="EVT-1",
            confidence=0.9,
            verification_results=[
                VerificationResult(claim_id="C1", verdict="verified", confidence=0.95),
            ],
        )
        assert should_flag_for_review(state) is False

    def test_no_flag_without_verifications(self):
        """No verification results means no flag (can't assess)."""
        state = EventProcessingState(
            event_id="EVT-1",
            confidence=0.5,
        )
        assert should_flag_for_review(state) is False


class TestGetParallelGroups:
    """Tests for parallel group detection."""

    def test_parallel_groups_for_multi_domain(self):
        """Multiple domain agents should form a parallel group."""
        pipeline = [
            "deduplication", "event_clustering", "domain_classification",
            "politics_agent", "technology_agent", "business_agent",
            "summarization", "verification",
        ]
        groups = get_parallel_groups(pipeline)
        # Domain agents should be in a parallel group
        assert len(groups) >= 1
        for group in groups:
            if "politics_agent" in group:
                assert "technology_agent" in group
                assert "business_agent" in group
