"""Database model for agent execution history.

WHY persist agent runs:
- Enables post-hoc analysis of pipeline performance.
- Provides an audit trail for compliance and debugging.
- Feeds into monitoring dashboards (latency, error rates, throughput).
- Allows replaying failed events by inspecting what went wrong.
"""

from sqlalchemy import Column, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentRun(Base, TimestampMixin, UUIDMixin):
    """Record of a single agent execution within the pipeline."""

    __tablename__ = "agent_runs"

    # --- Identity ---
    event_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    processing_version = Column(String(20), default="1.0.0", nullable=False)
    pipeline_run_id = Column(String(100), nullable=False, index=True)

    # --- Status ---
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending | running | completed | failed | skipped

    # --- Timing ---
    started_at = Column(String(50), nullable=True)
    completed_at = Column(String(50), nullable=True)
    processing_time_ms = Column(Float, default=0.0, nullable=False)

    # --- Results ---
    confidence = Column(Float, nullable=True)
    output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    error_category = Column(String(50), nullable=True)

    # --- Retry tracking ---
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # --- Model info ---
    model_used = Column(String(100), nullable=True)
    token_usage = Column(JSON, nullable=True)

    # --- Input references ---
    input_article_ids = Column(JSON, nullable=True)  # list of article IDs

    def __repr__(self) -> str:
        return (
            f"<AgentRun event={self.event_id} agent={self.agent_name} "
            f"status={self.status}>"
        )
