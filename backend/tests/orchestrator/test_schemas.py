"""Tests for inter-agent communication schemas.

WHY test schemas:
- Schema violations cause silent failures in agent communication.
- Every message must have required metadata fields.
- Roundtrip serialization must preserve all data.
"""

import pytest
from datetime import UTC, datetime

from app.pipeline.orchestrator.schemas import (
    AgentTaskPayload,
    AgentTaskResult,
    EventUpdateMessage,
    OrchestratorCommand,
    PipelineStatusMessage,
)


class TestAgentTaskPayload:
    """Tests for the task payload sent to agents."""

    def test_minimal_payload(self):
        """Should create with just event_id and agent_name."""
        payload = AgentTaskPayload(event_id="EVT-1", agent_name="test_agent")
        assert payload.event_id == "EVT-1"
        assert payload.agent_name == "test_agent"
        assert payload.article_ids == []
        assert payload.priority == "normal"
        assert payload.is_reprocessing is False
        assert payload.task_id is not None

    def test_full_payload(self):
        """Should accept all optional fields."""
        payload = AgentTaskPayload(
            event_id="EVT-1",
            article_ids=["A1", "A2"],
            articles=[{"id": "A1", "title": "Test"}],
            agent_name="test_agent",
            priority="high",
            is_reprocessing=True,
            trigger="new_article",
            classification={"category": "tech"},
            summary="Test summary",
        )
        assert len(payload.article_ids) == 2
        assert payload.priority == "high"
        assert payload.is_reprocessing is True

    def test_payload_serialization(self):
        """Should serialize to dict and back."""
        payload = AgentTaskPayload(
            event_id="EVT-1",
            article_ids=["A1"],
            agent_name="test_agent",
        )
        data = payload.model_dump()
        restored = AgentTaskPayload(**data)
        assert restored.event_id == payload.event_id
        assert restored.task_id == payload.task_id


class TestAgentTaskResult:
    """Tests for the result returned by agents."""

    def test_minimal_result(self):
        """Should create with required fields."""
        result = AgentTaskResult(
            event_id="EVT-1",
            agent_name="test_agent",
            status="completed",
        )
        assert result.event_id == "EVT-1"
        assert result.status == "completed"
        assert result.confidence == 0.0
        assert result.output == {}

    def test_result_with_output(self):
        """Should carry agent-specific output."""
        result = AgentTaskResult(
            event_id="EVT-1",
            agent_name="test_agent",
            status="completed",
            confidence=0.92,
            output={"summary": "Test summary", "key_entities": ["AI", "Google"]},
            processing_time_ms=1234.5,
            model_used="gpt-4o-mini",
            token_usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
        assert result.confidence == 0.92
        assert result.output["summary"] == "Test summary"
        assert result.model_used == "gpt-4o-mini"

    def test_failed_result(self):
        """Should capture error information."""
        result = AgentTaskResult(
            event_id="EVT-1",
            agent_name="test_agent",
            status="failed",
            error="API timeout",
            error_type="TimeoutError",
        )
        assert result.status == "failed"
        assert result.error == "API timeout"

    def test_result_serialization_roundtrip(self):
        """Should survive serialization."""
        result = AgentTaskResult(
            event_id="EVT-1",
            agent_name="test",
            status="completed",
            confidence=0.8,
            output={"key": "value"},
        )
        data = result.model_dump()
        restored = AgentTaskResult(**data)
        assert restored.event_id == result.event_id
        assert restored.confidence == result.confidence


class TestOrchestratorCommand:
    """Tests for orchestrator commands."""

    def test_command(self):
        """Should carry command type and metadata."""
        cmd = OrchestratorCommand(
            command="process",
            event_id="EVT-1",
            agent_name="test_agent",
            reason="New article arrived",
        )
        assert cmd.command == "process"
        assert cmd.reason == "New article arrived"
        assert cmd.timestamp is not None

    def test_retry_command(self):
        """Should support retry commands."""
        cmd = OrchestratorCommand(
            command="retry",
            event_id="EVT-1",
            agent_name="test_agent",
            payload=AgentTaskPayload(event_id="EVT-1", agent_name="test_agent"),
        )
        assert cmd.command == "retry"
        assert cmd.payload is not None


class TestEventUpdateMessage:
    """Tests for event update messages."""

    def test_update_message(self):
        """Should carry new article information."""
        msg = EventUpdateMessage(
            event_id="EVT-1",
            new_article_ids=["A4", "A5"],
            existing_article_count=3,
        )
        assert msg.event_id == "EVT-1"
        assert len(msg.new_article_ids) == 2
        assert msg.existing_article_count == 3
        assert msg.trigger == "new_article"


class TestPipelineStatusMessage:
    """Tests for pipeline status messages."""

    def test_status_message(self):
        """Should carry status update information."""
        msg = PipelineStatusMessage(
            event_id="EVT-1",
            status="summarizing",
            current_stage="summarization",
            confidence=0.75,
            progress_pct=60.0,
            message="Processing summaries",
        )
        assert msg.status == "summarizing"
        assert msg.confidence == 0.75
        assert msg.progress_pct == 60.0

    def test_status_serialization(self):
        """Should serialize to JSON-compatible dict."""
        msg = PipelineStatusMessage(
            event_id="EVT-1",
            status="completed",
        )
        data = msg.model_dump(mode="json")
        assert isinstance(data["timestamp"], str)
