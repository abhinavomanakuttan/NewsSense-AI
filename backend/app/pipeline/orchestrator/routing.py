"""Routing logic for the orchestrator.

WHY a separate routing module:
- Keeps the graph definition clean: the graph defines structure, routing decides flow.
- Routing rules can evolve independently of the graph topology.
- Makes it easy to add new categories or modify pipeline paths.
- Enables conditional skipping of stages (e.g., skip verification for low-credibility sources).
"""

from __future__ import annotations

import logging
from typing import Any

from app.pipeline.orchestrator.state import EventProcessingState, EventStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline stage definitions per category
# ---------------------------------------------------------------------------

# Default pipeline stages for each category.
# The orchestrator will skip stages that have already been completed.
# Agents within a stage may run in parallel if they are independent.

CATEGORY_PIPELINES: dict[str, list[str]] = {
    "politics": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "politics_agent",
        "summarization",
        "claim_extraction",
        "evidence_retrieval",
        "nli_stance",
        "corroboration",
        "verification",
        "bias_framing",
        "embedding",
    ],
    "technology": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "technology_agent",
        "summarization",
        "claim_extraction",
        "evidence_retrieval",
        "nli_stance",
        "corroboration",
        "verification",
        "bias_framing",
        "embedding",
    ],
    "sports": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "sports_agent",
        "summarization",
        "verification",  # Simplified: skip claim extraction for sports
        "embedding",
    ],
    "science": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "science_agent",
        "summarization",
        "claim_extraction",
        "evidence_retrieval",
        "nli_stance",
        "verification",
        "embedding",
    ],
    "business": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "business_agent",
        "summarization",
        "claim_extraction",
        "verification",
        "bias_framing",
        "embedding",
    ],
    "entertainment": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "entertainment_agent",
        "summarization",
        "embedding",
    ],
    "world_news": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "world_news_agent",
        "summarization",
        "claim_extraction",
        "evidence_retrieval",
        "nli_stance",
        "corroboration",
        "verification",
        "bias_framing",
        "embedding",
    ],
    "environment": [
        "deduplication",
        "event_clustering",
        "domain_classification",
        "environment_agent",
        "summarization",
        "claim_extraction",
        "evidence_retrieval",
        "nli_stance",
        "verification",
        "bias_framing",
        "embedding",
    ],
}

# Default pipeline for unknown categories
DEFAULT_PIPELINE = [
    "deduplication",
    "event_clustering",
    "domain_classification",
    "summarization",
    "claim_extraction",
    "evidence_retrieval",
    "nli_stance",
    "corroboration",
    "verification",
    "bias_framing",
    "embedding",
]

# Mapping from pipeline stage name to the event status it produces
STAGE_TO_STATUS: dict[str, EventStatus] = {
    "deduplication": EventStatus.DEDUPLICATED,
    "event_clustering": EventStatus.CLUSTERED,
    "domain_classification": EventStatus.CLASSIFIED,
    "politics_agent": EventStatus.ANALYZING,
    "technology_agent": EventStatus.ANALYZING,
    "sports_agent": EventStatus.ANALYZING,
    "science_agent": EventStatus.ANALYZING,
    "business_agent": EventStatus.ANALYZING,
    "entertainment_agent": EventStatus.ANALYZING,
    "world_news_agent": EventStatus.ANALYZING,
    "environment_agent": EventStatus.ANALYZING,
    "summarization": EventStatus.SUMMARIZING,
    "claim_extraction": EventStatus.VERIFYING,
    "evidence_retrieval": EventStatus.VERIFYING,
    "nli_stance": EventStatus.VERIFYING,
    "corroboration": EventStatus.VERIFYING,
    "verification": EventStatus.VERIFYING,
    "bias_framing": EventStatus.ANALYZING_FRAMING,
    "embedding": EventStatus.INDEXING,
}

# Stages that can run in parallel within a group
PARALLEL_GROUPS: list[list[str]] = [
    # Domain agents can run in parallel for multi-domain events
    ["politics_agent", "technology_agent", "business_agent", "sports_agent",
     "science_agent", "entertainment_agent", "world_news_agent", "environment_agent"],
    # Claim analysis stages are sequential by design (each depends on the previous)
]


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def get_pipeline_for_event(state: EventProcessingState) -> list[str]:
    """Determine the pipeline stages needed for an event.

    WHY per-category pipelines:
    - Sports don't need full claim extraction / evidence retrieval.
    - Entertainment doesn't need bias analysis.
    - This avoids wasting compute on irrelevant stages.
    """
    category = (state.category or "").lower()
    pipeline = CATEGORY_PIPELINES.get(category, DEFAULT_PIPELINE)

    # Filter out already-completed stages
    completed_stages = _get_completed_stages(state)
    remaining = [s for s in pipeline if s not in completed_stages]

    logger.debug(
        f"Pipeline for event {state.event_id} (category={category}): "
        f"{len(remaining)} stages remaining out of {len(pipeline)}"
    )
    return remaining


def get_parallel_groups(pipeline: list[str]) -> list[list[str]]:
    """Identify which stages in the pipeline can run in parallel.

    WHY parallel execution:
    - Independent domain agents (Politics, Tech, Business) can run simultaneously.
    - Reduces total processing time for multi-domain events from O(n) to O(1) for
      the parallel portion.
    """
    groups: list[list[str]] = []
    used: set[str] = set()

    for parallel_group in PARALLEL_GROUPS:
        concurrent = [s for s in pipeline if s in parallel_group and s not in used]
        if len(concurrent) > 1:
            groups.append(concurrent)
            used.update(concurrent)

    return groups


def should_skip_verification(state: EventProcessingState) -> bool:
    """Decide if verification can be skipped for this event.

    WHY skip:
    - Very high-confidence events from highly credible sources don't need
      full claim extraction / evidence retrieval.
    - Saves compute for clearly factual, well-sourced events.
    """
    # Skip if all sources have high credibility and event confidence is high
    if state.classification_confidence > 0.95:
        sources = [a for a in state.articles if a.source_credibility is not None]
        if sources and all(s.source_credibility and s.source_credibility > 0.85 for s in sources):
            return True
    return False


def should_flag_for_review(state: EventProcessingState) -> bool:
    """Decide if the event should be flagged for human review.

    WHY flag:
    - Contradictory evidence from multiple sources.
    - Very low confidence after full processing.
    - Conflicting claims from high-profile sources.
    """
    # Low confidence after processing
    if 0 < state.confidence < 0.3 and len(state.verification_results) > 0:
        return True

    # Contradictory verification results
    if state.verification_results:
        verdicts = [v.verdict for v in state.verification_results]
        if "verified" in verdicts and "false" in verdicts:
            return True

    # High-credibility sources disagree
    if state.bias_analysis and state.bias_analysis.source_agreement_score < 0.3:
        return True

    return False


def determine_priority_from_content(state: EventProcessingState) -> str:
    """Determine event priority based on content signals.

    WHY content-based priority:
    - Breaking news should be processed first.
    - Multiple sources reporting the same event signals importance.
    - Keywords like "breaking", "urgent" indicate time-sensitivity.
    """
    article_count = len(state.article_ids)

    # Multiple sources = important event
    if article_count >= 10:
        return "breaking"
    elif article_count >= 5:
        return "high"
    elif article_count >= 2:
        return "normal"
    else:
        return "low"


def get_multi_domain_agents(state: EventProcessingState) -> list[str]:
    """Determine which domain agents are relevant for a multi-domain event.

    WHY multi-domain:
    - "Government announces AI investment" → Politics + Tech + Business.
    - Each agent provides specialized analysis from its domain perspective.
    - Results are merged for a richer, multi-perspective understanding.
    """
    category = (state.category or "").lower()
    agents: list[str] = []

    # Primary domain agent
    category_agent_map = {
        "politics": "politics_agent",
        "technology": "technology_agent",
        "tech": "technology_agent",
        "sports": "sports_agent",
        "science": "science_agent",
        "business": "business_agent",
        "finance": "business_agent",
        "entertainment": "entertainment_agent",
        "world": "world_news_agent",
        "world_news": "world_news_agent",
        "environment": "environment_agent",
        "climate": "environment_agent",
    }

    primary = category_agent_map.get(category)
    if primary:
        agents.append(primary)

    # Cross-domain keyword detection
    cross_domain_keywords = {
        "politics_agent": ["government", "policy", "election", "legislation", "congress", "parliament", "regulation"],
        "technology_agent": ["ai", "artificial intelligence", "software", "tech", "startup", "algorithm", "compute"],
        "business_agent": ["market", "stock", "revenue", "company", "startup", "investment", "economy", "gdp"],
        "science_agent": ["research", "study", "experiment", "discovery", "peer-reviewed", "journal"],
        "environment_agent": ["climate", "carbon", "emissions", "sustainability", "renewable", "pollution"],
    }

    all_text = " ".join(
        (a.title or "").lower()
        for a in state.articles
    )

    for agent, keywords in cross_domain_keywords.items():
        if agent not in agents:
            matches = sum(1 for kw in keywords if kw in all_text)
            if matches >= 2:
                agents.append(agent)

    return agents


def _get_completed_stages(state: EventProcessingState) -> set[str]:
    """Infer which stages have already been completed from agent results."""
    completed: set[str] = set()

    # Check agent results for completed stages
    for result in state.agent_results:
        if result.status == "completed":
            completed.add(result.agent_name)

    # Infer from status
    status = EventStatus(state.status)
    if status.value in ("deduplicated", "clustered", "classified", "analyzing",
                        "summarizing", "verifying", "analyzing_framing",
                        "indexing", "completed"):
        completed.add("deduplication")
    if status.value in ("clustered", "classified", "analyzing", "summarizing",
                        "verifying", "analyzing_framing", "indexing", "completed"):
        completed.add("event_clustering")
    if status.value in ("classified", "analyzing", "summarizing", "verifying",
                        "analyzing_framing", "indexing", "completed"):
        completed.add("domain_classification")
    if status.value in ("summarizing", "verifying", "analyzing_framing",
                        "indexing", "completed"):
        completed.add("summarization")

    return completed
