"""Tests for error handling, retry policies, and failure classification.

WHY test error handling:
- Retry logic must not create infinite loops.
- Error classification determines whether to retry, skip, or fail.
- Exponential backoff must produce reasonable delays.
"""

import pytest

from app.pipeline.orchestrator.errors import (
    DEFAULT_RETRY_POLICY,
    AgentDependencyError,
    AgentOutputError,
    AgentRateLimitError,
    AgentTimeoutError,
    ErrorCategory,
    PipelineError,
    RetryPolicy,
    build_error_context,
    classify_error,
)


class TestErrorClassification:
    """Tests for error type hierarchy."""

    def test_pipeline_error_base(self):
        """PipelineError should carry metadata."""
        err = PipelineError(
            "test error",
            category=ErrorCategory.TRANSIENT,
            agent_name="agent1",
            event_id="EVT-1",
            retryable=True,
        )
        assert str(err) == "test error"
        assert err.category == ErrorCategory.TRANSIENT
        assert err.agent_name == "agent1"
        assert err.event_id == "EVT-1"
        assert err.retryable is True
        assert err.timestamp is not None

    def test_timeout_error(self):
        """Timeout errors should be transient and retryable."""
        err = AgentTimeoutError("agent1", timeout_seconds=30.0)
        assert err.category == ErrorCategory.TRANSIENT
        assert err.retryable is True
        assert "30.0s" in str(err)

    def test_rate_limit_error(self):
        """Rate limit errors should be retryable."""
        err = AgentRateLimitError("agent1", retry_after=5.0)
        assert err.category == ErrorCategory.RATE_LIMIT
        assert err.retryable is True
        assert err.metadata["retry_after"] == 5.0

    def test_output_error(self):
        """Output errors should be permanent (not retryable)."""
        err = AgentOutputError("agent1", "missing required field 'text'")
        assert err.category == ErrorCategory.PERMANENT
        assert err.retryable is False

    def test_dependency_error(self):
        """Dependency errors should be degradable and retryable."""
        err = AgentDependencyError("agent1", "vector_store")
        assert err.category == ErrorCategory.DEGRADABLE
        assert err.retryable is True
        assert err.metadata["dependency"] == "vector_store"


class TestRetryPolicy:
    """Tests for retry policy behavior."""

    def test_delay_increases_with_attempts(self):
        """Delay should increase exponentially."""
        policy = RetryPolicy(max_retries=5, base_delay=1.0, jitter=False)
        d0 = policy.delay_for_attempt(0)
        d1 = policy.delay_for_attempt(1)
        d2 = policy.delay_for_attempt(2)
        assert d0 < d1 < d2

    def test_delay_respects_max(self):
        """Delay should not exceed max_delay."""
        policy = RetryPolicy(max_retries=10, base_delay=1.0, max_delay=5.0, jitter=False)
        d = policy.delay_for_attempt(100)
        assert d <= 5.0

    def test_jitter_adds_variance(self):
        """Jitter should produce different delays."""
        policy = RetryPolicy(base_delay=1.0, jitter=True)
        delays = {policy.delay_for_attempt(0) for _ in range(20)}
        # With jitter, we should see some variance
        assert len(delays) > 1

    def test_should_retry_within_limit(self):
        """Should retry when under max and error is retryable."""
        policy = RetryPolicy(max_retries=3)
        err = PipelineError("test", retryable=True)
        assert policy.should_retry(0, err) is True
        assert policy.should_retry(1, err) is True
        assert policy.should_retry(2, err) is True

    def test_should_not_retry_at_limit(self):
        """Should not retry when at max retries."""
        policy = RetryPolicy(max_retries=3)
        err = PipelineError("test", retryable=True)
        assert policy.should_retry(3, err) is False

    def test_should_not_retry_permanent_error(self):
        """Should not retry non-retryable errors."""
        policy = RetryPolicy(max_retries=5)
        err = PipelineError("test", retryable=False)
        assert policy.should_retry(0, err) is False

    def test_next_delay_returns_none_when_no_retry(self):
        """next_delay should return None when retry is not appropriate."""
        policy = RetryPolicy(max_retries=3)
        err = PipelineError("test", retryable=False)
        assert policy.next_delay(0, err) is None

    def test_next_delay_returns_float_when_retry(self):
        """next_delay should return a float when retry is appropriate."""
        policy = RetryPolicy(max_retries=3)
        err = PipelineError("test", retryable=True)
        delay = policy.next_delay(0, err)
        assert delay is not None
        assert isinstance(delay, float)
        assert delay > 0


class TestClassifyError:
    """Tests for exception classification."""

    def test_timeout_classification(self):
        """Timeout exceptions should be classified as TRANSIENT."""
        exc = TimeoutError("Connection timed out")
        assert classify_error(exc) == ErrorCategory.TRANSIENT

    def test_connection_error_classification(self):
        """Connection errors should be TRANSIENT."""
        exc = ConnectionError("Connection refused")
        assert classify_error(exc) == ErrorCategory.TRANSIENT

    def test_value_error_classification(self):
        """Value errors should be PERMANENT."""
        exc = ValueError("Invalid input")
        assert classify_error(exc) == ErrorCategory.PERMANENT

    def test_rate_limit_in_message(self):
        """Rate limit strings should be classified as RATE_LIMIT."""
        exc = Exception("HTTP 429 Too Many Requests")
        assert classify_error(exc) == ErrorCategory.RATE_LIMIT


class TestBuildErrorContext:
    """Tests for structured error context."""

    def test_basic_context(self):
        """Should build context from exception and metadata."""
        exc = ValueError("bad input")
        ctx = build_error_context(exc, "agent1", "EVT-1", attempt=2)

        assert ctx["agent"] == "agent1"
        assert ctx["event_id"] == "EVT-1"
        assert ctx["attempt"] == 2
        assert ctx["error_type"] == "ValueError"
        assert ctx["error_message"] == "bad input"
        assert ctx["timestamp"] is not None

    def test_pipeline_error_context(self):
        """PipelineError should preserve category and retryable flag."""
        err = AgentTimeoutError("agent1", 30.0)
        ctx = build_error_context(err, "agent1", "EVT-1", attempt=1)

        assert ctx["category"] == "transient"
        assert ctx["retryable"] is True


class TestDefaultRetryPolicy:
    """Tests for the default retry policy configuration."""

    def test_default_policy_exists(self):
        """DEFAULT_RETRY_POLICY should be importable."""
        assert DEFAULT_RETRY_POLICY is not None
        assert DEFAULT_RETRY_POLICY.max_retries == 3
        assert DEFAULT_RETRY_POLICY.base_delay == 2.0
        assert DEFAULT_RETRY_POLICY.max_delay == 60.0
