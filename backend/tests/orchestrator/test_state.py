"""Tests for EventProcessingState — state machine, transitions, and validation.

WHY comprehensive state tests:
- The state machine is the core invariant of the orchestrator.
- Invalid transitions must fail loudly (not silently corrupt data).
- Every valid transition path must be covered.
"""

import pytest
from datetime import UTC, datetime

from app.pipeline.orchestrator.state import (
    AgentResult,
    ArticleInfo,
    BiasAnalysis,
    ClaimInfo,
    DomainAnalysis,
    EventProcessingState,
    EventPriority,
    EventStatus,
    EvidenceItem,
    ProcessingMetadata,
    VerificationResult,
    _VALID_TRANSITIONS,
)


class TestEventStatus:
    """Tests for the EventStatus enum."""

    def test_all_statuses_exist(self):
        """Every status in the spec must exist."""
        expected = {
            "new", "ingested", "deduplicated", "clustered", "classified",
            "analyzing", "summarizing", "verifying", "analyzing_framing",
            "indexing", "completed", "failed", "requires_review",
        }
        actual = {s.value for s in EventStatus}
        assert expected == actual

    def test_valid_transitions_cover_all_statuses(self):
        """Every non-terminal status must have at least one valid transition."""
        terminal = {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.REQUIRES_REVIEW}
        for status in EventStatus:
            if status not in terminal:
                assert status in _VALID_TRANSITIONS, f"{status} missing from transitions"
                assert len(_VALID_TRANSITIONS[status]) > 0, f"{status} has no valid transitions"

    def test_terminal_statuses_have_no_transitions(self):
        """Terminal statuses must not allow any transitions."""
        terminal = {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.REQUIRES_REVIEW}
        for status in terminal:
            assert _VALID_TRANSITIONS.get(status, set()) == set(), f"{status} should be terminal"


class TestEventPriority:
    """Tests for the EventPriority enum."""

    def test_priority_ordering(self):
        """Priority ordering must be consistent."""
        assert EventPriority.LOW.numeric < EventPriority.NORMAL.numeric
        assert EventPriority.NORMAL.numeric < EventPriority.HIGH.numeric
        assert EventPriority.HIGH.numeric < EventPriority.BREAKING.numeric

    def test_priority_values(self):
        """Priority values must match spec."""
        assert EventPriority.LOW.value == "low"
        assert EventPriority.NORMAL.value == "normal"
        assert EventPriority.HIGH.value == "high"
        assert EventPriority.BREAKING.value == "breaking"


class TestEventProcessingState:
    """Tests for the main state model."""

    def test_default_state(self):
        """New state should have sensible defaults."""
        state = EventProcessingState(event_id="EVT-001")
        assert state.event_id == "EVT-001"
        assert state.status == EventStatus.NEW
        assert state.priority == EventPriority.NORMAL
        assert state.article_ids == []
        assert state.confidence == 0.0
        assert state.retry_count == 0
        assert state.max_retries == 3
        assert state.created_at is not None
        assert state.updated_at is not None

    def test_valid_transition(self):
        """Valid transitions should succeed."""
        state = EventProcessingState(event_id="EVT-001")
        state.transition_to(EventStatus.INGESTED)
        assert state.status == EventStatus.INGESTED
        assert state.updated_at > state.created_at

    def test_invalid_transition_raises(self):
        """Invalid transitions should raise ValueError."""
        state = EventProcessingState(event_id="EVT-001")
        with pytest.raises(ValueError, match="Invalid transition"):
            state.transition_to(EventStatus.COMPLETED)

    def test_full_pipeline_transition_path(self):
        """Test the complete valid transition path."""
        state = EventProcessingState(event_id="EVT-001")

        path = [
            EventStatus.INGESTED,
            EventStatus.DEDUPLICATED,
            EventStatus.CLUSTERED,
            EventStatus.CLASSIFIED,
            EventStatus.ANALYZING,
            EventStatus.SUMMARIZING,
            EventStatus.VERIFYING,
            EventStatus.ANALYZING_FRAMING,
            EventStatus.INDEXING,
            EventStatus.COMPLETED,
        ]

        for status in path:
            state.transition_to(status)
            assert state.status == status

    def test_transition_to_requires_review_from_verifying(self):
        """Can transition from VERIFYING to REQUIRES_REVIEW."""
        state = EventProcessingState(event_id="EVT-001")
        state.transition_to(EventStatus.INGESTED)
        state.transition_to(EventStatus.DEDUPLICATED)
        state.transition_to(EventStatus.CLUSTERED)
        state.transition_to(EventStatus.CLASSIFIED)
        state.transition_to(EventStatus.VERIFYING)
        state.transition_to(EventStatus.REQUIRES_REVIEW)
        assert state.status == EventStatus.REQUIRES_REVIEW

    def test_transition_to_requires_review_from_analyzing_framing(self):
        """Can transition from ANALYZING_FRAMING to REQUIRES_REVIEW."""
        state = EventProcessingState(event_id="EVT-001")
        state.transition_to(EventStatus.INGESTED)
        state.transition_to(EventStatus.DEDUPLICATED)
        state.transition_to(EventStatus.CLUSTERED)
        state.transition_to(EventStatus.CLASSIFIED)
        state.transition_to(EventStatus.ANALYZING_FRAMING)
        state.transition_to(EventStatus.REQUIRES_REVIEW)
        assert state.status == EventStatus.REQUIRES_REVIEW

    def test_add_agent_result_completed(self):
        """Adding a completed result should update confidence."""
        state = EventProcessingState(event_id="EVT-001")
        result = AgentResult(
            agent_name="test_agent",
            status="completed",
            confidence=0.85,
        )
        state.add_agent_result(result)
        assert len(state.agent_results) == 1
        assert state.confidence == 0.85

    def test_add_agent_result_failed(self):
        """Adding a failed result should track in agent_errors."""
        state = EventProcessingState(event_id="EVT-001")
        result = AgentResult(
            agent_name="test_agent",
            status="failed",
            error="Something went wrong",
        )
        state.add_agent_result(result)
        assert len(state.agent_results) == 1
        assert len(state.agent_errors) == 1
        assert state.agent_errors[0]["agent"] == "test_agent"

    def test_confidence_averaging(self):
        """Confidence should be average of successful agents."""
        state = EventProcessingState(event_id="EVT-001")
        state.add_agent_result(AgentResult(agent_name="a", status="completed", confidence=0.8))
        state.add_agent_result(AgentResult(agent_name="b", status="completed", confidence=0.6))
        assert abs(state.confidence - 0.7) < 0.01

    def test_is_terminal(self):
        """is_terminal should return True for terminal states."""
        state = EventProcessingState(event_id="EVT-001")
        assert not state.is_terminal()

        state.status = EventStatus.COMPLETED
        assert state.is_terminal()

        state.status = EventStatus.FAILED
        assert state.is_terminal()

        state.status = EventStatus.REQUIRES_REVIEW
        assert state.is_terminal()

    def test_needs_retry(self):
        """needs_retry should return True for failed states under max retries."""
        state = EventProcessingState(event_id="EVT-001")
        state.status = EventStatus.FAILED
        state.retry_count = 0
        assert state.needs_retry()

        state.retry_count = 3
        assert not state.needs_retry()

    def test_mark_failed(self):
        """mark_failed should set status and error."""
        state = EventProcessingState(event_id="EVT-001")
        state.mark_failed("Test error")
        assert state.status == EventStatus.FAILED
        assert state.last_error == "Test error"

    def test_mark_completed(self):
        """mark_completed should set status and timestamps."""
        state = EventProcessingState(event_id="EVT-001")
        state.mark_completed()
        assert state.status == EventStatus.COMPLETED
        assert state.completed_at is not None

    def test_checkpoint_roundtrip(self):
        """State should survive serialization roundtrip."""
        state = EventProcessingState(
            event_id="EVT-001",
            article_ids=["ART-1", "ART-2"],
            category="technology",
            priority=EventPriority.HIGH,
            summary="Test summary",
        )
        state.transition_to(EventStatus.INGESTED)
        state.add_agent_result(AgentResult(
            agent_name="test", status="completed", confidence=0.9,
        ))

        checkpoint = state.to_checkpoint()
        restored = EventProcessingState.from_checkpoint(checkpoint)

        assert restored.event_id == state.event_id
        assert restored.article_ids == state.article_ids
        assert restored.category == state.category
        assert restored.summary == state.summary
        assert len(restored.agent_results) == 1
        assert restored.confidence == 0.9


class TestSubModels:
    """Tests for Pydantic sub-models."""

    def test_article_info(self):
        article = ArticleInfo(id="A1", title="Test", url="https://example.com")
        assert article.id == "A1"
        assert article.language == "en"

    def test_claim_info(self):
        claim = ClaimInfo(text="The earth is round")
        assert claim.id is not None
        assert len(claim.id) == 12

    def test_evidence_item(self):
        evidence = EvidenceItem(claim_id="C1", snippet="Evidence text")
        assert evidence.relevance_score == 0.0

    def test_verification_result(self):
        vr = VerificationResult(claim_id="C1", verdict="verified", confidence=0.95)
        assert vr.verdict == "verified"

    def test_bias_analysis(self):
        bias = BiasAnalysis(overall_bias="center", bias_score=0.2)
        assert bias.framing_patterns == []

    def test_domain_analysis(self):
        da = DomainAnalysis(domain="technology", confidence=0.9)
        assert da.key_entities == []

    def test_agent_result(self):
        ar = AgentResult(agent_name="test", status="completed")
        assert ar.processing_time_ms == 0.0
        assert ar.retry_count == 0

    def test_processing_metadata(self):
        pm = ProcessingMetadata()
        assert pm.processing_version == "1.0.0"
        assert pm.pipeline_run_id is not None
