"""Core Orchestrator implemented as a LangGraph StateGraph.

WHY LangGraph:
- Declarative graph definition: nodes = processing stages, edges = routing logic.
- Built-in state management with checkpointing (Redis-backed).
- Conditional edges enable dynamic routing based on event state.
- Parallel execution via fan-out/fan-in patterns.
- Time-travel debugging: replay any state snapshot.
- Native support for human-in-the-loop (REQUIRES_REVIEW state).

WHY not just plain asyncio:
- LangGraph provides state persistence, which plain asyncio does not.
- Graph structure is self-documenting and inspectable at runtime.
- Conditional routing is cleaner than nested if/else in async code.
- LangGraph handles the complexity of parallel branch coordination.

Architecture Notes:
- Multi-domain events (e.g., "Government announces AI investment") fan out
  to Politics + Technology + Business agents in parallel, then fan in.
- The corroboration node aggregates verification results from all evidence.
- Every decision point checks for human review flagging.
- Checkpointing uses MemorySaver in dev, Redis-backed in production.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any, Annotated

from langgraph.graph import END, StateGraph

from app.pipeline.orchestrator.errors import (
    DEFAULT_RETRY_POLICY,
    PipelineError,
    classify_error,
)
from app.pipeline.orchestrator.idempotency import IdempotencyGuard
from app.pipeline.orchestrator.registry import AgentRegistry, get_registry
from app.pipeline.orchestrator.routing import (
    get_multi_domain_agents,
    get_pipeline_for_event,
    should_flag_for_review,
    should_skip_verification,
)
from app.pipeline.orchestrator.schemas import (
    AgentTaskPayload,
    AgentTaskResult,
    PipelineStatusMessage,
)
from app.pipeline.orchestrator.state import (
    AgentResult,
    ArticleInfo,
    ClaimInfo,
    DomainAnalysis,
    EventProcessingState,
    EventPriority,
    EventStatus,
    EvidenceItem,
    VerificationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangGraph checkpoint configuration
# ---------------------------------------------------------------------------

def get_checkpointer():
    """Return the appropriate checkpoint backend.

    WHY configurable:
    - Development: MemorySaver is simple, no external deps.
    - Production: Redis-backed checkpointer survives restarts.
    - Enables time-travel debugging in dev.
    """
    try:
        from langgraph.checkpoint.redis import RedisSaver
        from app.core.config import settings
        return RedisSaver.from_conn_string(settings.redis_url)
    except (ImportError, Exception):
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


# ---------------------------------------------------------------------------
# Parallel fan-out / fan-in helpers
# ---------------------------------------------------------------------------

def _determine_domain_agents(state: EventProcessingState) -> list[str]:
    """Determine which domain agents to invoke for this event.

    WHY multi-domain support:
    - Real-world events span multiple domains.
    - "Government announces AI investment" → Politics + Tech + Business.
    - Each domain agent provides specialized analysis.
    - Results are merged for a richer understanding.

    The function examines:
    1. Primary category (from classification)
    2. Subcategory hints
    3. Cross-domain signals (e.g., technology keywords in politics)
    """
    category = (state.category or "").lower()
    subcategory = (state.subcategory or "").lower()
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

    # Cross-domain detection: if article titles/content mention domains
    # outside the primary category, add those agents too.
    # This is a heuristic — domain agents will confirm or reject relevance.
    cross_domain_keywords = {
        "politics_agent": ["government", "policy", "election", "legislation", "congress", "parliament", "regulation"],
        "technology_agent": ["ai", "artificial intelligence", "software", "tech", "startup", "algorithm", "compute"],
        "business_agent": ["market", "stock", "revenue", "company", "startup", "investment", "economy", "gdp"],
        "science_agent": ["research", "study", "experiment", "discovery", "peer-reviewed", "journal"],
        "environment_agent": ["climate", "carbon", "emissions", "sustainability", "renewable", "pollution"],
    }

    # Collect text signals from articles
    all_text = " ".join(
        (a.title or "").lower() + " " + (a.source_name or "").lower()
        for a in state.articles
    )

    for agent, keywords in cross_domain_keywords.items():
        if agent not in agents:
            # Need at least 2 keyword matches to trigger cross-domain
            matches = sum(1 for kw in keywords if kw in all_text)
            if matches >= 2:
                agents.append(agent)

    return agents


async def _run_parallel_domain_agents(
    state: EventProcessingState,
    agent_names: list[str],
) -> EventProcessingState:
    """Execute multiple domain agents concurrently.

    WHY async parallel:
    - Independent agents have no data dependencies between them.
    - Running sequentially would add O(N) latency for N agents.
    - asyncio.gather runs them concurrently on the event loop.
    - Each agent has its own timeout to prevent one slow agent from blocking.
    """
    if not agent_names:
        return state

    registry = get_registry()
    start_time = time.monotonic()

    async def _run_one(agent_name: str) -> AgentTaskResult:
        """Run a single domain agent with timeout and error handling."""
        descriptor = registry.get(agent_name)
        if descriptor is None or descriptor.handler is None:
            logger.warning(f"Agent '{agent_name}' not registered, skipping")
            return AgentTaskResult(
                event_id=state.event_id,
                agent_name=agent_name,
                status="skipped",
                error=f"Agent '{agent_name}' not registered",
            )

        payload = AgentTaskPayload(
            event_id=state.event_id,
            article_ids=state.article_ids,
            articles=[a.model_dump() for a in state.articles],
            agent_name=agent_name,
            priority=(
                state.priority.value
                if isinstance(state.priority, EventPriority)
                else state.priority
            ),
        )

        agent_start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                descriptor.handler(payload),
                timeout=descriptor.timeout_seconds,
            )
            elapsed_ms = (time.monotonic() - agent_start) * 1000

            if isinstance(result, AgentTaskResult):
                result.processing_time_ms = elapsed_ms
                return result
            elif isinstance(result, dict):
                return AgentTaskResult(
                    event_id=state.event_id,
                    agent_name=agent_name,
                    status="completed",
                    output=result,
                    confidence=result.get("confidence", 0.0),
                    processing_time_ms=elapsed_ms,
                )
            return AgentTaskResult(
                event_id=state.event_id,
                agent_name=agent_name,
                status="completed",
                processing_time_ms=elapsed_ms,
            )

        except asyncio.TimeoutError:
            elapsed_ms = (time.monotonic() - agent_start) * 1000
            logger.error(f"Agent '{agent_name}' timed out for {state.event_id}")
            return AgentTaskResult(
                event_id=state.event_id,
                agent_name=agent_name,
                status="failed",
                error=f"Timeout after {descriptor.timeout_seconds}s",
                processing_time_ms=elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.monotonic() - agent_start) * 1000
            logger.error(f"Agent '{agent_name}' failed for {state.event_id}: {exc}")
            return AgentTaskResult(
                event_id=state.event_id,
                agent_name=agent_name,
                status="failed",
                error=str(exc),
                error_type=type(exc).__name__,
                processing_time_ms=elapsed_ms,
            )

    # Run all agents concurrently
    results = await asyncio.gather(*[_run_one(name) for name in agent_names])

    # Merge results into state (convert AgentTaskResult → AgentResult)
    for result in results:
        agent_result = AgentResult(
            agent_name=result.agent_name,
            status=result.status,
            confidence=result.confidence,
            output=result.output,
            started_at=result.started_at,
            completed_at=result.completed_at,
            processing_time_ms=result.processing_time_ms,
            error=result.error,
            retry_count=result.retry_count,
            model_used=result.model_used,
            token_usage=result.token_usage,
        )
        state.add_agent_result(agent_result)

        # Extract domain analysis from completed agents
        if result.status == "completed" and result.output:
            domain_analysis = DomainAnalysis(
                domain=result.agent_name.replace("_agent", ""),
                confidence=result.confidence,
                subcategory=result.output.get("subcategory"),
                key_entities=result.output.get("key_entities", []),
                summary=result.output.get("summary"),
                metadata=result.output,
            )
            state.domain_analyses.append(domain_analysis)

    total_ms = (time.monotonic() - start_time) * 1000
    logger.info(
        f"Event {state.event_id}: Parallel domain analysis complete "
        f"({len(agent_names)} agents, {total_ms:.0f}ms)"
    )

    return state


# ---------------------------------------------------------------------------
# Node functions — each node is a processing stage
# ---------------------------------------------------------------------------

async def _ingestion_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Ingestion — articles have already been created by the ingestion service.

    This node validates articles exist and transitions to INGESTED.
    """
    if not state.article_ids:
        state.mark_failed("No articles to process")
        return state

    state.transition_to(EventStatus.INGESTED)
    state.current_stage = "ingestion"
    state.processing_metadata.agents_invoked.append("ingestion")
    logger.info(f"Event {state.event_id}: Ingestion complete, {len(state.article_ids)} articles")
    return state


async def _deduplication_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Deduplication — check for and remove duplicate articles.

    WHY early dedup:
    - Prevents downstream agents from processing the same content twice.
    - Reduces API costs for LLM-based agents.
    - Improves cluster quality by removing noise.
    """
    state.current_stage = "deduplication"

    # Dedup via content_hash within the event
    seen_hashes: set[str] = set()
    unique_ids: list[str] = []
    dup_count = 0

    for article in state.articles:
        if article.content_hash and article.content_hash in seen_hashes:
            dup_count += 1
            continue
        if article.content_hash:
            seen_hashes.add(article.content_hash)
        unique_ids.append(article.id)

    if dup_count > 0:
        logger.info(f"Event {state.event_id}: Removed {dup_count} duplicates")
        state.article_ids = unique_ids
        state.articles = [a for a in state.articles if a.id in unique_ids]

    state.transition_to(EventStatus.DEDUPLICATED)
    state.processing_metadata.agents_invoked.append("deduplication")
    return state


async def _clustering_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Event Clustering — group articles into coherent events.

    WHY clustering:
    - Multiple sources report the same story with different angles.
    - Clustering enables cross-source analysis and fact-checking.
    - Prevents treating 50 articles about the same event as 50 separate events.
    """
    state.current_stage = "event_clustering"

    # Clustering is delegated to the EventClusterer agent via the registry.
    # Articles are already associated with an event by the ingestion service.

    state.transition_to(EventStatus.CLUSTERED)
    state.processing_metadata.agents_invoked.append("event_clustering")
    logger.info(f"Event {state.event_id}: Clustering complete")
    return state


async def _classification_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Domain Classification — determine the event's category.

    WHY classify before domain analysis:
    - Classification determines WHICH domain agents to invoke.
    - A "Sports" event should not be sent to the Politics agent.
    - Classification confidence influences downstream decisions.
    """
    state.current_stage = "domain_classification"

    if not state.category:
        state.category = "world_news"
        state.classification_confidence = 0.5
        logger.warning(f"Event {state.event_id}: No category, defaulting to world_news")

    state.transition_to(EventStatus.CLASSIFIED)
    state.processing_metadata.agents_invoked.append("domain_classification")
    logger.info(
        f"Event {state.event_id}: Classified as {state.category} "
        f"(confidence={state.classification_confidence:.2f})"
    )
    return state


async def _domain_analysis_node(
    state: EventProcessingState,
) -> EventProcessingState:
    """Node: Domain-specific analysis — fan-out to all relevant agents in parallel.

    WHY a single node that fans out internally:
    - LangGraph's fan-out requires static graph edges (known at build time).
    - Domain agents are dynamic (registered at runtime).
    - So we handle parallelism inside the node via asyncio.gather.
    - Each domain agent runs concurrently with its own timeout.
    """
    state.current_stage = "domain_analysis"

    # Determine which domain agents to invoke (supports multi-domain)
    agent_names = _determine_domain_agents(state)

    if not agent_names:
        logger.info(f"Event {state.event_id}: No domain agents matched, skipping")
        state.transition_to(EventStatus.ANALYZING)
        return state

    logger.info(f"Event {state.event_id}: Routing to domain agents: {agent_names}")
    state.processing_metadata.agents_invoked.extend(agent_names)

    # Run all domain agents in parallel
    state = await _run_parallel_domain_agents(state, agent_names)

    state.transition_to(EventStatus.ANALYZING)
    return state


async def _summarization_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Summarization — generate a coherent summary from all articles.

    WHY summarise after domain analysis:
    - Domain analysis provides context that improves summary quality.
    - Summary should incorporate domain-specific insights.
    - Enables event-level summaries, not just article-level.
    """
    state.current_stage = "summarization"

    if state.summary and len(state.summary.split()) >= 25:
        # Already has a good summary, skip
        state.processing_metadata.agents_invoked.append("summarization:skipped")
        state.transition_to(EventStatus.SUMMARIZING)
        return state

    registry = get_registry()
    handler = registry.get_handler("summarizer")
    if handler is None:
        logger.warning("Summarizer agent not registered, skipping")
        state.transition_to(EventStatus.SUMMARIZING)
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        article_ids=state.article_ids,
        articles=[a.model_dump() for a in state.articles],
        agent_name="summarizer",
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=60.0)
        if isinstance(result, dict) and result.get("summary"):
            state.summary = result["summary"]
        elif isinstance(result, AgentTaskResult) and result.output.get("summary"):
            state.summary = result.output["summary"]
    except Exception as exc:
        logger.error(f"Summarization failed for {state.event_id}: {exc}")

    state.transition_to(EventStatus.SUMMARIZING)
    state.processing_metadata.agents_invoked.append("summarization")
    return state


async def _claim_extraction_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Claim Extraction — identify factual claims from articles.

    WHY a separate node (not buried in verification):
    - Claim extraction is itself an LLM call that can fail independently.
    - Extracted claims are reusable by multiple downstream agents.
    - Enables incremental processing: re-extract claims without re-verifying.
    """
    state.current_stage = "claim_extraction"

    if should_skip_verification(state):
        state.processing_metadata.agents_invoked.append("claim_extraction:skipped")
        state.transition_to(EventStatus.VERIFYING)
        return state

    registry = get_registry()
    handler = registry.get_handler("claim_extraction")
    if handler is None:
        logger.warning("Claim extraction agent not registered, skipping")
        state.transition_to(EventStatus.VERIFYING)
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        article_ids=state.article_ids,
        articles=[a.model_dump() for a in state.articles],
        agent_name="claim_extraction",
        summary=state.summary,
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=60.0)
        if isinstance(result, dict) and result.get("claims"):
            state.claims = [ClaimInfo(**c) for c in result["claims"]]
        elif isinstance(result, AgentTaskResult) and result.output.get("claims"):
            state.claims = [ClaimInfo(**c) for c in result.output["claims"]]
    except Exception as exc:
        logger.error(f"Claim extraction failed for {state.event_id}: {exc}")

    state.transition_to(EventStatus.VERIFYING)
    state.processing_metadata.agents_invoked.append("claim_extraction")
    return state


async def _evidence_retrieval_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Evidence Retrieval — find corroborating/contradicting sources for claims.

    WHY separate from claim extraction:
    - Evidence retrieval may involve web search or vector DB queries.
    - Different timeout/retry characteristics than claim extraction.
    - Can be re-run independently if new evidence sources become available.
    """
    state.current_stage = "evidence_retrieval"

    if not state.claims:
        state.processing_metadata.agents_invoked.append("evidence_retrieval:skipped")
        return state

    registry = get_registry()
    handler = registry.get_handler("evidence_retrieval")
    if handler is None:
        logger.warning("Evidence retrieval agent not registered, skipping")
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        claims=[c.model_dump() for c in state.claims],
        agent_name="evidence_retrieval",
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=90.0)
        if isinstance(result, dict) and result.get("evidence"):
            state.evidence = [EvidenceItem(**e) for e in result["evidence"]]
        elif isinstance(result, AgentTaskResult) and result.output.get("evidence"):
            state.evidence = [EvidenceItem(**e) for e in result.output["evidence"]]
    except Exception as exc:
        logger.error(f"Evidence retrieval failed for {state.event_id}: {exc}")

    state.processing_metadata.agents_invoked.append("evidence_retrieval")
    return state


async def _nli_stance_node(state: EventProcessingState) -> EventProcessingState:
    """Node: NLI / Stance Detection — determine logical relationship between claims and evidence.

    WHY separate from evidence retrieval:
    - NLI models are specialized and computationally expensive.
    - Can run in batch mode for all claim-evidence pairs.
    - Stance detection adds nuance beyond binary verified/false.
    """
    state.current_stage = "nli_stance"

    if not state.claims or not state.evidence:
        state.processing_metadata.agents_invoked.append("nli_stance:skipped")
        return state

    registry = get_registry()
    handler = registry.get_handler("nli_stance")
    if handler is None:
        logger.warning("NLI/Stance agent not registered, skipping")
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        claims=[c.model_dump() for c in state.claims],
        evidence=[e.model_dump() for e in state.evidence],
        agent_name="nli_stance",
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=60.0)
        if isinstance(result, dict) and result.get("verification_results"):
            state.verification_results = [
                VerificationResult(**v) for v in result["verification_results"]
            ]
        elif isinstance(result, AgentTaskResult) and result.output.get("verification_results"):
            state.verification_results = [
                VerificationResult(**v) for v in result.output["verification_results"]
            ]
    except Exception as exc:
        logger.error(f"NLI/Stance detection failed for {state.event_id}: {exc}")

    state.processing_metadata.agents_invoked.append("nli_stance")
    return state


async def _corroboration_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Corroboration — aggregate verification signals into a final confidence score.

    WHY a separate corroboration step:
    - NLI gives per-claim verdicts; corroboration synthesizes across all claims.
    - Different claims may have conflicting verdicts — corroboration resolves this.
    - Produces the final confidence score used for review flagging.
    - Can apply domain-specific weighting (e.g., official statements weigh more).
    """
    state.current_stage = "corroboration"

    if not state.verification_results:
        state.processing_metadata.agents_invoked.append("corroboration:skipped")
        return state

    registry = get_registry()
    handler = registry.get_handler("corroboration")
    if handler is None:
        # Fallback: compute confidence from verification results directly
        _compute_corroboration_fallback(state)
        state.processing_metadata.agents_invoked.append("corroboration:fallback")
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        claims=[c.model_dump() for c in state.claims],
        evidence=[e.model_dump() for e in state.evidence],
        verification_results=[v.model_dump() for v in state.verification_results],
        agent_name="corroboration",
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=60.0)
        if isinstance(result, dict):
            state.confidence = result.get("confidence", state.confidence)
            # Update verification results with corroboration verdicts
            if result.get("verification_results"):
                state.verification_results = [
                    VerificationResult(**v) for v in result["verification_results"]
                ]
    except Exception as exc:
        logger.error(f"Corroboration failed for {state.event_id}: {exc}")
        _compute_corroboration_fallback(state)

    state.processing_metadata.agents_invoked.append("corroboration")
    return state


def _compute_corroboration_fallback(state: EventProcessingState) -> None:
    """Fallback corroboration: compute confidence from verification results.

    WHY a fallback:
    - If the corroboration agent is not registered, we still need a confidence score.
    - Simple heuristic: average of individual claim confidences.
    """
    if not state.verification_results:
        return

    verdict_weights = {
        "verified": 1.0,
        "disputed": 0.5,
        "unverifiable": 0.3,
        "false": 0.0,
    }

    scores = []
    for vr in state.verification_results:
        weight = verdict_weights.get(vr.verdict, 0.3)
        scores.append(weight * vr.confidence)

    if scores:
        state.confidence = sum(scores) / len(scores)


async def _verification_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Verification pipeline — orchestrates claim extraction → evidence → NLI → corroboration.

    This is a convenience node that runs the full verification sub-pipeline.
    Individual steps are also available as separate nodes for targeted reprocessing.
    """
    state.current_stage = "verification"

    if should_skip_verification(state):
        logger.info(f"Event {state.event_id}: Skipping verification (high confidence)")
        state.transition_to(EventStatus.VERIFYING)
        state.processing_metadata.agents_invoked.append("verification:skipped")
        return state

    # Run the verification sub-pipeline steps
    state = await _claim_extraction_node(state)
    state = await _evidence_retrieval_node(state)
    state = await _nli_stance_node(state)
    state = await _corroboration_node(state)

    state.transition_to(EventStatus.VERIFYING)
    return state


async def _bias_framing_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Bias/Framing analysis — detect source bias and framing patterns.

    WHY analyse framing:
    - Same event can be presented very differently by different sources.
    - Readers deserve to know about potential bias.
    - Enables "multi-perspective" summaries.
    """
    state.current_stage = "analyzing_framing"

    registry = get_registry()
    handler = registry.get_handler("bias_framing")
    if handler is None:
        logger.warning("Bias/Framing agent not registered, skipping")
        state.transition_to(EventStatus.ANALYZING_FRAMING)
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        article_ids=state.article_ids,
        articles=[a.model_dump() for a in state.articles],
        agent_name="bias_framing",
        summary=state.summary,
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=60.0)
        if isinstance(result, dict):
            from app.pipeline.orchestrator.state import BiasAnalysis
            state.bias_analysis = BiasAnalysis(
                overall_bias=result.get("overall_bias"),
                bias_score=result.get("bias_score", 0.0),
                framing_patterns=result.get("framing_patterns", []),
                source_agreement_score=result.get("source_agreement_score", 0.0),
            )
        elif isinstance(result, AgentTaskResult) and result.output:
            from app.pipeline.orchestrator.state import BiasAnalysis
            state.bias_analysis = BiasAnalysis(
                overall_bias=result.output.get("overall_bias"),
                bias_score=result.output.get("bias_score", 0.0),
                framing_patterns=result.output.get("framing_patterns", []),
                source_agreement_score=result.output.get("source_agreement_score", 0.0),
            )
    except Exception as exc:
        logger.error(f"Bias/Framing analysis failed for {state.event_id}: {exc}")

    # Check if human review is needed after framing analysis
    if should_flag_for_review(state):
        state.transition_to(EventStatus.REQUIRES_REVIEW)
        logger.warning(
            f"Event {state.event_id} flagged for human review "
            f"(confidence={state.confidence:.2f})"
        )
    else:
        state.transition_to(EventStatus.ANALYZING_FRAMING)

    state.processing_metadata.agents_invoked.append("bias_framing")
    return state


async def _embedding_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Embedding — generate vector embeddings and store in vector DB.

    WHY last:
    - Embedding should reflect the final, enriched state of the event.
    - Re-embedding after every change would be wasteful.
    - Vector quality improves with more context (summary, claims, etc.).
    """
    state.current_stage = "embedding"

    registry = get_registry()
    handler = registry.get_handler("embedding")
    if handler is None:
        state.embedding_status = "skipped"
        state.transition_to(EventStatus.INDEXING)
        state.processing_metadata.agents_invoked.append("embedding:skipped")
        return state

    payload = AgentTaskPayload(
        event_id=state.event_id,
        article_ids=state.article_ids,
        articles=[a.model_dump() for a in state.articles],
        agent_name="embedding",
        summary=state.summary,
    )

    try:
        result = await asyncio.wait_for(handler(payload), timeout=60.0)
        if isinstance(result, dict):
            state.embedding_status = result.get("status", "completed")
        elif isinstance(result, AgentTaskResult):
            state.embedding_status = "completed" if result.status == "completed" else "failed"
        else:
            state.embedding_status = "completed" if result else "failed"
    except Exception as exc:
        logger.error(f"Embedding failed for {state.event_id}: {exc}")
        state.embedding_status = "failed"

    state.transition_to(EventStatus.INDEXING)
    state.processing_metadata.agents_invoked.append("embedding")
    return state


async def _completion_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Final completion — validate state and mark as done.

    WHY a dedicated completion node:
    - Centralises the "is this event done?" decision.
    - Updates aggregate metrics (total processing time, overall confidence).
    - Triggers downstream notifications (API cache invalidation, WebSocket push).
    """
    state.current_stage = None  # No longer in any stage

    # Calculate total processing time
    state.processing_metadata.total_processing_time_ms = sum(
        r.processing_time_ms for r in state.agent_results
    )

    # Check if we should flag for review instead of completing
    if should_flag_for_review(state):
        state.transition_to(EventStatus.REQUIRES_REVIEW)
        logger.warning(f"Event {state.event_id} flagged for review at completion check")
        return state

    state.mark_completed()
    logger.info(
        f"Event {state.event_id}: Pipeline completed "
        f"(confidence={state.confidence:.2f}, "
        f"time={state.processing_metadata.total_processing_time_ms:.0f}ms)"
    )
    return state


async def _failure_node(state: EventProcessingState) -> EventProcessingState:
    """Node: Handle failures — retry or escalate."""
    state.retry_count += 1

    if state.retry_count < state.max_retries:
        logger.info(
            f"Event {state.event_id}: Retrying (attempt {state.retry_count}/{state.max_retries})"
        )
        # Reset status to allow reprocessing from the failed stage
        state.status = EventStatus.NEW
    else:
        logger.error(
            f"Event {state.event_id}: Max retries ({state.max_retries}) exceeded, "
            f"marking as failed"
        )
        state.mark_failed(
            f"Max retries exceeded after {state.max_retries} attempts. "
            f"Last error: {state.last_error}"
        )

    return state


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def _route_after_classification(state: EventProcessingState) -> str:
    """Route to domain analysis after classification.

    Always goes to the unified domain_analysis node, which internally
    fans out to the appropriate domain agents.
    """
    return "domain_analysis"


def _route_after_domain(state: EventProcessingState) -> str:
    """After domain analysis, decide next step."""
    if should_flag_for_review(state):
        return "review"
    return "summarization"


def _route_after_verification(state: EventProcessingState) -> str:
    """After verification, decide next step."""
    if should_flag_for_review(state):
        return "review"
    return "bias_framing"


def _route_after_bias(state: EventProcessingState) -> str:
    """After bias analysis, decide next step."""
    if should_flag_for_review(state):
        return "review"
    return "embedding"


# ---------------------------------------------------------------------------
# Orchestrator Graph builder
# ---------------------------------------------------------------------------

class OrchestratorGraph:
    """Builds and manages the LangGraph processing graph.

    WHY a class (not just a function):
    - Encapsulates the graph construction (complex).
    - Provides clean API: `graph.process(state)`.
    - Supports runtime inspection of the graph structure.
    - Can be extended with additional nodes without modifying core.

    Graph topology:
        ingestion → deduplication → clustering → classification
            → domain_analysis → summarization → verification
            → bias_framing → embedding → completion → END

    With conditional edges for:
        - Human review at any decision point
        - Failure handling
        - Skipping stages based on event characteristics
    """

    def __init__(self, registry: AgentRegistry | None = None):
        self.registry = registry or get_registry()
        self._graph: StateGraph | None = None
        self._compiled = None
        self._build()

    def _build(self) -> None:
        """Construct the LangGraph state graph."""
        graph = StateGraph(EventProcessingState)

        # --- Core pipeline nodes ---
        graph.add_node("ingestion", _ingestion_node)
        graph.add_node("deduplication", _deduplication_node)
        graph.add_node("clustering", _clustering_node)
        graph.add_node("classification", _classification_node)
        graph.add_node("domain_analysis", _domain_analysis_node)
        graph.add_node("summarization", _summarization_node)
        graph.add_node("claim_extraction", _claim_extraction_node)
        graph.add_node("evidence_retrieval", _evidence_retrieval_node)
        graph.add_node("nli_stance", _nli_stance_node)
        graph.add_node("corroboration", _corroboration_node)
        graph.add_node("verification", _verification_node)
        graph.add_node("bias_framing", _bias_framing_node)
        graph.add_node("embedding", _embedding_node)
        graph.add_node("completion", _completion_node)
        graph.add_node("failure", _failure_node)

        # --- Edges ---
        # Entry point
        graph.set_entry_point("ingestion")

        # Linear pipeline: ingestion → dedup → clustering → classification
        graph.add_edge("ingestion", "deduplication")
        graph.add_edge("deduplication", "clustering")
        graph.add_edge("clustering", "classification")

        # Classification → Domain Analysis (always, domain_analysis fans out internally)
        graph.add_conditional_edges(
            "classification",
            _route_after_classification,
            {
                "domain_analysis": "domain_analysis",
            },
        )

        # Domain Analysis → summarization (with review check)
        graph.add_conditional_edges(
            "domain_analysis",
            _route_after_domain,
            {
                "summarization": "summarization",
                "review": "completion",  # completion will flag for review
            },
        )

        # Summarization → Verification
        graph.add_edge("summarization", "verification")

        # Verification → Bias/Framing (with review check)
        graph.add_conditional_edges(
            "verification",
            _route_after_verification,
            {
                "bias_framing": "bias_framing",
                "review": "completion",
            },
        )

        # Bias/Framing → Embedding (with review check)
        graph.add_conditional_edges(
            "bias_framing",
            _route_after_bias,
            {
                "embedding": "embedding",
                "review": "completion",
            },
        )

        # Embedding → Completion
        graph.add_edge("embedding", "completion")

        # Completion → END
        graph.add_edge("completion", END)

        # Failure handling
        graph.add_edge("failure", END)

        self._graph = graph

        # Compile with checkpoint support
        try:
            checkpointer = get_checkpointer()
            self._compiled = graph.compile(checkpointer=checkpointer)
        except Exception as exc:
            logger.warning(f"Could not set up checkpointer, using default: {exc}")
            self._compiled = graph.compile()

    async def process(self, state: EventProcessingState) -> EventProcessingState:
        """Run the full pipeline for an event.

        Returns the final state after processing.
        """
        start_time = time.monotonic()

        try:
            # Build config with thread_id for checkpointing
            config = {"configurable": {"thread_id": state.event_id}}

            # Run the graph
            result = await self._compiled.ainvoke(state, config=config)
            if isinstance(result, dict):
                state = EventProcessingState(**result)
            elif isinstance(result, EventProcessingState):
                state = result
        except Exception as exc:
            logger.error(f"Graph execution failed for {state.event_id}: {exc}")
            state.mark_failed(str(exc))

        # Ensure total time is recorded
        total_ms = (time.monotonic() - start_time) * 1000
        state.processing_metadata.total_processing_time_ms = total_ms

        return state

    async def process_with_retry(
        self,
        state: EventProcessingState,
        retry_policy: Any | None = None,
    ) -> EventProcessingState:
        """Process with automatic retry on failure.

        WHY retry at the orchestrator level:
        - Some failures are transient (DB timeout, API rate limit).
        - Retry with backoff prevents overwhelming the failing service.
        - Max retries prevent infinite loops.
        """
        policy = retry_policy or DEFAULT_RETRY_POLICY
        attempt = 0

        while attempt <= policy.max_retries:
            state = await self.process(state)

            if state.status in (EventStatus.COMPLETED, EventStatus.REQUIRES_REVIEW):
                break

            if state.status == EventStatus.FAILED:
                attempt += 1
                error = PipelineError(
                    state.last_error or "Unknown error",
                    retryable=True,
                )
                delay = policy.next_delay(attempt - 1, error)
                if delay is not None:
                    logger.info(
                        f"Retrying event {state.event_id} in {delay:.1f}s "
                        f"(attempt {attempt}/{policy.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    state.retry_count = attempt
                    state.status = EventStatus.NEW  # Reset for retry
                else:
                    break

        return state

    def get_compiled(self) -> Any:
        """Return the compiled graph for inspection."""
        return self._compiled

    def get_graph_png(self) -> bytes | None:
        """Generate a PNG visualization of the graph (if mermaid is available)."""
        try:
            return self._compiled.get_graph().draw_mermaid_png()
        except Exception:
            return None
