"""Error handling, retry policies, and failure classification.

WHY a dedicated error module:
- Centralises retry logic so every agent uses the same backoff policy.
- Classifies errors to decide between retry, skip, or fail.
- Provides structured error context for observability.
"""

from __future__ import annotations

import enum
import logging
import random
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

class ErrorCategory(str, enum.Enum):
    """Classify errors to decide the appropriate response.

    WHY classify:
    - Transient errors (timeout, rate limit) → retry with backoff.
    - Permanent errors (malformed output) → fail, don't retry.
    - Degradable errors (DB down) → skip non-critical step, continue.
    """
    TRANSIENT = "transient"        # API timeout, network blip
    RATE_LIMIT = "rate_limit"      # External API rate limit
    PERMANENT = "permanent"        # Bad input, malformed output
    DEGRADABLE = "degradable"      # Non-critical service unavailable
    UNKNOWN = "unknown"


class PipelineError(Exception):
    """Base exception for pipeline processing errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        agent_name: str | None = None,
        event_id: str | None = None,
        retryable: bool = False,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.agent_name = agent_name
        self.event_id = event_id
        self.retryable = retryable
        self.metadata = metadata or {}
        self.timestamp = datetime.now(UTC)


class AgentTimeoutError(PipelineError):
    """Agent execution exceeded time limit."""

    def __init__(self, agent_name: str, timeout_seconds: float, **kwargs: Any):
        super().__init__(
            f"Agent '{agent_name}' timed out after {timeout_seconds}s",
            category=ErrorCategory.TRANSIENT,
            agent_name=agent_name,
            retryable=True,
            **kwargs,
        )


class AgentRateLimitError(PipelineError):
    """Agent hit an external API rate limit."""

    def __init__(self, agent_name: str, retry_after: float | None = None, **kwargs: Any):
        super().__init__(
            f"Agent '{agent_name}' rate limited",
            category=ErrorCategory.RATE_LIMIT,
            agent_name=agent_name,
            retryable=True,
            metadata={"retry_after": retry_after},
            **kwargs,
        )


class AgentOutputError(PipelineError):
    """Agent returned malformed or invalid output."""

    def __init__(self, agent_name: str, detail: str, **kwargs: Any):
        super().__init__(
            f"Agent '{agent_name}' returned invalid output: {detail}",
            category=ErrorCategory.PERMANENT,
            agent_name=agent_name,
            retryable=False,
            **kwargs,
        )


class AgentDependencyError(PipelineError):
    """A required dependency service is unavailable."""

    def __init__(self, agent_name: str, dependency: str, **kwargs: Any):
        super().__init__(
            f"Agent '{agent_name}' dependency '{dependency}' unavailable",
            category=ErrorCategory.DEGRADABLE,
            agent_name=agent_name,
            retryable=True,
            metadata={"dependency": dependency},
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

class RetryPolicy:
    """Configurable retry policy with exponential backoff and jitter.

    WHY exponential backoff with jitter:
    - Backoff prevents hammering a failing service.
    - Jitter prevents thundering herd when multiple workers retry simultaneously.
    - Maximum retry count prevents infinite loops.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay in seconds for a given retry attempt (0-indexed)."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
        return delay

    def should_retry(self, attempt: int, error: PipelineError) -> bool:
        """Decide whether to retry based on attempt count and error type."""
        if attempt >= self.max_retries:
            return False
        if not error.retryable:
            return False
        return True

    def next_delay(self, attempt: int, error: PipelineError) -> float | None:
        """Return the delay before the next retry, or None if no retry."""
        if self.should_retry(attempt, error):
            return self.delay_for_attempt(attempt)
        return None


# ---------------------------------------------------------------------------
# Error context builder
# ---------------------------------------------------------------------------

def build_error_context(
    error: Exception,
    agent_name: str,
    event_id: str,
    attempt: int,
) -> dict[str, Any]:
    """Build structured error context for logging and DB persistence.

    WHY structured context:
    - Enables querying errors by agent, event, category.
    - Makes debugging production issues tractable.
    - Feeds into observability dashboards.
    """
    category = ErrorCategory.UNKNOWN
    retryable = False

    if isinstance(error, PipelineError):
        category = error.category
        retryable = error.retryable

    return {
        "agent": agent_name,
        "event_id": event_id,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "category": category.value,
        "retryable": retryable,
        "attempt": attempt,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an exception into an error category.

    Maps common exception types to appropriate categories.
    """
    error_name = type(error).__name__.lower()

    # Timeouts
    if "timeout" in error_name or "timed out" in str(error).lower():
        return ErrorCategory.TRANSIENT

    # Rate limits
    if "rate" in error_name or "429" in str(error):
        return ErrorCategory.RATE_LIMIT

    # Network / connection
    if any(k in error_name for k in ("connection", "connect", "network", "dns")):
        return ErrorCategory.TRANSIENT

    # Validation / schema
    if any(k in error_name for k in ("validation", "schema", "type", "value")):
        return ErrorCategory.PERMANENT

    # Database
    if any(k in error_name for k in ("database", "db", "sql", "integrity")):
        return ErrorCategory.DEGRADABLE

    return ErrorCategory.UNKNOWN


# Default retry policy used across the system
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
)
