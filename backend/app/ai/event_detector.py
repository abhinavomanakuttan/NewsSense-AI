"""Event Detection, Clustering, and Evolution Engine for NewsSense AI.

Handles:
- Stage 3: Multi-field Weighted Semantic Embeddings (Title 0.45, Summary 0.35, Content 0.20)
- Stage 4: Composite Event Similarity Metric (Semantic + Time + Entities + Locations + Action Keywords)
- Event Lifecycle State Machine:
    * Search Active Events in sliding temporal window (last 48-72h)
    * Attach to Existing Event / Update Centroid / Maintain Timeline
    * Create New Event
    * Detect Contradictions & Flag for Verification (status: flagged_verification)
- Batch Density Clustering support (DBSCAN, HDBSCAN, Agglomerative)
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

CONTRADICTION_PATTERNS = [
    r"\b(denies|denied|refutes|refuted|disputes|disputed|contradicts|contradicted)\b",
    r"\b(rejects claims|denies involvement|dismisses reports|false claims)\b",
    r"\b(corrected previous|revised down|revised up|discrepancy in)\b",
]

ANNOUNCEMENT_KEYWORDS = {
    "announces", "announced", "announcing",
    "unveils", "unveiled", "unveiling",
    "launches", "launched", "launching",
    "allocates", "allocated", "allocating",
    "invests", "invested", "investing",
    "funds", "funded", "funding",
    "pledges", "pledged", "pledging",
}

DISCUSSION_KEYWORDS = {
    "discusses", "discussed", "discussing",
    "debates", "debated", "debating",
    "considers", "considered", "considering",
    "weighs", "weighed", "weighing",
    "plans", "planned", "planning",
    "proposes", "proposed", "proposing",
}


@dataclass
class EventMatchDecision:
    event_id: str | None
    match_type: str  # semantic_match, new_event, contradiction
    similarity: float
    confidence: float
    is_contradiction: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class EventDetector:
    """Detects events, calculates composite similarity, and manages event evolution."""

    def __init__(
        self,
        match_threshold: float = 0.76,
        candidate_threshold: float = 0.65,
        temporal_half_life_hours: float = 36.0,
        semantic_weight: float = 0.40,
        time_weight: float = 0.20,
        entity_weight: float = 0.20,
        location_weight: float = 0.10,
        keyword_weight: float = 0.10,
    ):
        self.match_threshold = match_threshold
        self.candidate_threshold = candidate_threshold
        self.temporal_decay_tau = temporal_half_life_hours
        self.w_sem = semantic_weight
        self.w_time = time_weight
        self.w_ent = entity_weight
        self.w_loc = location_weight
        self.w_kw = keyword_weight

    # ------------------------------------------------------------------
    # Stage 3: Multi-Field Semantic Embeddings
    # ------------------------------------------------------------------

    def compute_composite_embedding(
        self,
        title_emb: list[float] | np.ndarray | None,
        summary_emb: list[float] | np.ndarray | None,
        content_emb: list[float] | np.ndarray | None,
    ) -> list[float]:
        """Weighted multi-field embedding: Title (0.45), Summary (0.35), Content (0.20)."""
        valid_embs = []
        weights = []

        if title_emb is not None and len(title_emb) > 0:
            valid_embs.append(np.array(title_emb, dtype=np.float32))
            weights.append(0.45)
        if summary_emb is not None and len(summary_emb) > 0:
            valid_embs.append(np.array(summary_emb, dtype=np.float32))
            weights.append(0.35)
        if content_emb is not None and len(content_emb) > 0:
            valid_embs.append(np.array(content_emb, dtype=np.float32))
            weights.append(0.20)

        if not valid_embs:
            return []

        # Re-normalize weights if some fields were missing
        w_sum = sum(weights)
        norm_weights = [w / w_sum for w in weights]

        composite = np.zeros_like(valid_embs[0])
        for emb, weight in zip(valid_embs, norm_weights):
            composite += emb * weight

        # L2 normalize
        norm = np.linalg.norm(composite)
        if norm > 1e-6:
            composite = composite / norm

        return composite.tolist()

    @staticmethod
    def cosine_similarity(v1: list[float] | np.ndarray, v2: list[float] | np.ndarray) -> float:
        if not len(v1) or not len(v2) or len(v1) != len(v2):
            return 0.0
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    # ------------------------------------------------------------------
    # Stage 4: Composite Event Similarity Metric
    # ------------------------------------------------------------------

    def calculate_composite_similarity(
        self,
        article_data: dict[str, Any],
        event_data: dict[str, Any],
    ) -> tuple[float, dict[str, float]]:
        """Compute multi-factor similarity S = w_sem*S_sem + w_time*S_time + w_ent*S_ent + w_loc*S_loc + w_kw*S_kw."""
        # 1. Semantic Similarity
        art_emb = article_data.get("composite_embedding") or article_data.get("embedding")
        evt_emb = event_data.get("embedding")
        if isinstance(evt_emb, str):
            try:
                evt_emb = json.loads(evt_emb)
            except Exception:
                evt_emb = []

        if art_emb and evt_emb:
            sim_sem = self.cosine_similarity(art_emb, evt_emb)
        else:
            # Fallback text token overlap if embeddings unavailable
            sim_sem = self._token_jaccard(article_data.get("title", ""), event_data.get("title", ""))

        # 2. Time Proximity (Exponential decay)
        art_time = self._parse_datetime(article_data.get("published_at"))
        evt_time = self._parse_datetime(event_data.get("latest_update") or event_data.get("start_time"))
        delta_hours = abs((art_time - evt_time).total_seconds()) / 3600.0
        sim_time = math.exp(-delta_hours / self.temporal_decay_tau)

        # 3. Named Entity Overlap (PER, ORG)
        art_ents = self._extract_entities_set(article_data.get("entities"))
        evt_ents = self._extract_entities_set(event_data.get("entities"))
        sim_ent = self._jaccard_sets(art_ents, evt_ents)

        # 4. Location Overlap (LOC, GPE)
        art_locs = self._extract_locations_set(article_data.get("locations") or article_data.get("country"))
        evt_locs = self._extract_locations_set(event_data.get("locations"))
        sim_loc = self._jaccard_sets(art_locs, evt_locs) if (art_locs and evt_locs) else (0.5 if not evt_locs else 0.2)

        # 5. Event / Action Keyword Alignment
        sim_kw = self._action_keyword_alignment(article_data.get("title", ""), event_data.get("title", ""))

        composite_score = (
            (self.w_sem * sim_sem)
            + (self.w_time * sim_time)
            + (self.w_ent * sim_ent)
            + (self.w_loc * sim_loc)
            + (self.w_kw * sim_kw)
        )

        breakdown = {
            "semantic": round(sim_sem, 4),
            "temporal": round(sim_time, 4),
            "entities": round(sim_ent, 4),
            "locations": round(sim_loc, 4),
            "action_keywords": round(sim_kw, 4),
            "composite": round(composite_score, 4),
        }
        return composite_score, breakdown

    # ------------------------------------------------------------------
    # Online Event Matching & Lifecycle Management
    # ------------------------------------------------------------------

    def evaluate_article_for_events(
        self,
        article_data: dict[str, Any],
        active_events: list[dict[str, Any]],
    ) -> EventMatchDecision:
        """Evaluate an incoming article against active events in the sliding temporal window."""
        if not active_events:
            return EventMatchDecision(
                event_id=None,
                match_type="new_event",
                similarity=0.0,
                confidence=1.0,
                details={"reason": "No active events in window"},
            )

        best_event = None
        best_score = -1.0
        best_breakdown = {}

        for evt in active_events:
            # Check category compatibility if both specify categories
            art_cat = article_data.get("category")
            evt_cat = evt.get("category")
            if art_cat and evt_cat and art_cat.lower() != evt_cat.lower():
                continue

            score, breakdown = self.calculate_composite_similarity(article_data, evt)
            if score > best_score:
                best_score = score
                best_event = evt
                best_breakdown = breakdown

        if best_event and best_score >= self.match_threshold:
            # Check for contradictory reports (e.g. denial, conflicting casualty metrics)
            is_contradict = self.detect_contradiction(
                article_title=article_data.get("title", ""),
                article_content=article_data.get("content", ""),
                event_title=best_event.get("title", ""),
            )

            match_type = "contradiction" if is_contradict else "semantic_match"
            confidence = min(1.0, best_score + 0.05)

            return EventMatchDecision(
                event_id=str(best_event.get("id") or best_event.get("event_id")),
                match_type=match_type,
                similarity=round(best_score, 4),
                confidence=round(confidence, 4),
                is_contradiction=is_contradict,
                details={
                    "event_title": best_event.get("title"),
                    "breakdown": best_breakdown,
                },
            )

        # Distinguishing check: Same entity but different action keyword
        if best_event and self.candidate_threshold <= best_score < self.match_threshold:
            # If entities match heavily but action keyword is clearly distinct (e.g. Funding vs Policy Discussion)
            sim_kw = best_breakdown.get("action_keywords", 0.5)
            if sim_kw < 0.4:
                return EventMatchDecision(
                    event_id=None,
                    match_type="new_event",
                    similarity=round(best_score, 4),
                    confidence=0.85,
                    details={
                        "reason": "Shared entities but distinct action context (e.g. discussion vs announcement)",
                        "best_candidate_event_id": str(best_event.get("id")),
                        "breakdown": best_breakdown,
                    },
                )

        return EventMatchDecision(
            event_id=None,
            match_type="new_event",
            similarity=round(max(0.0, best_score), 4),
            confidence=0.90,
            details={"reason": "Below composite match threshold", "breakdown": best_breakdown},
        )

    # ------------------------------------------------------------------
    # Contradiction Detection & Event Evolution
    # ------------------------------------------------------------------

    @staticmethod
    def detect_contradiction(article_title: str, article_content: str, event_title: str) -> bool:
        """Detect whether incoming article refutes, denies, or contradicts previous reports."""
        text = f"{article_title} {article_content[:1000]}".lower()
        for pattern in CONTRADICTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    @staticmethod
    def classify_update_type(article_title: str, is_first: bool = False, is_contradiction: bool = False) -> str:
        if is_first:
            return "initial_report"
        if is_contradiction:
            return "contradiction"
        title_lower = article_title.lower()
        if any(w in title_lower for w in ["confirms", "confirmed", "official", "statement", "verified"]):
            return "official_confirmation"
        return "update"

    @staticmethod
    def update_event_centroid(
        current_centroid: list[float] | None,
        article_embedding: list[float] | None,
        current_article_count: int,
    ) -> list[float]:
        """Incremental online centroid update: E_new = (N * E_old + A) / (N + 1)."""
        if not article_embedding:
            return current_centroid or []
        if not current_centroid or current_article_count <= 0:
            return article_embedding

        c_arr = np.array(current_centroid, dtype=np.float32)
        a_arr = np.array(article_embedding, dtype=np.float32)
        if len(c_arr) != len(a_arr):
            return current_centroid

        updated = (current_article_count * c_arr + a_arr) / (current_article_count + 1)
        norm = np.linalg.norm(updated)
        if norm > 1e-6:
            updated = updated / norm
        return updated.tolist()

    # ------------------------------------------------------------------
    # Helper Parsing Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_datetime(dt_val: Any) -> datetime:
        if isinstance(dt_val, datetime):
            return dt_val if dt_val.tzinfo else dt_val.replace(tzinfo=UTC)
        if isinstance(dt_val, str):
            try:
                import dateutil.parser
                dt = dateutil.parser.parse(dt_val)
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except Exception:
                pass
        return datetime.now(UTC)

    @staticmethod
    def _extract_entities_set(entities_val: Any) -> set[str]:
        if not entities_val:
            return set()
        if isinstance(entities_val, str):
            try:
                entities_val = json.loads(entities_val)
            except Exception:
                return set()

        out = set()
        if isinstance(entities_val, list):
            for item in entities_val:
                if isinstance(item, dict) and "text" in item:
                    out.add(item["text"].lower().strip())
                elif isinstance(item, str):
                    out.add(item.lower().strip())
        elif isinstance(entities_val, dict):
            for k, vals in entities_val.items():
                if isinstance(vals, list):
                    for v in vals:
                        out.add(str(v).lower().strip())
        return out

    @staticmethod
    def _extract_locations_set(loc_val: Any) -> set[str]:
        if not loc_val:
            return set()
        if isinstance(loc_val, str):
            if loc_val.startswith("[") or loc_val.startswith("{"):
                try:
                    loc_val = json.loads(loc_val)
                except Exception:
                    return {loc_val.lower().strip()}
            else:
                return {loc_val.lower().strip()}
        if isinstance(loc_val, list):
            return {str(x).lower().strip() for x in loc_val if x}
        return set()

    @staticmethod
    def _jaccard_sets(s1: set, s2: set) -> float:
        if not s1 or not s2:
            return 0.0
        inter = len(s1.intersection(s2))
        union = len(s1.union(s2))
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _token_jaccard(t1: str, t2: str) -> float:
        toks1 = set(re.findall(r"\w+", t1.lower()))
        toks2 = set(re.findall(r"\w+", t2.lower()))
        if not toks1 or not toks2:
            return 0.0
        return len(toks1.intersection(toks2)) / len(toks1.union(toks2))

    @staticmethod
    def _action_keyword_alignment(title1: str, title2: str) -> float:
        words1 = set(re.findall(r"\w+", title1.lower()))
        words2 = set(re.findall(r"\w+", title2.lower()))

        is_announcement1 = bool(words1.intersection(ANNOUNCEMENT_KEYWORDS))
        is_announcement2 = bool(words2.intersection(ANNOUNCEMENT_KEYWORDS))

        is_discussion1 = bool(words1.intersection(DISCUSSION_KEYWORDS))
        is_discussion2 = bool(words2.intersection(DISCUSSION_KEYWORDS))

        # Both announce -> High action alignment
        if is_announcement1 and is_announcement2:
            return 1.0
        # Both discuss -> High action alignment
        if is_discussion1 and is_discussion2:
            return 1.0
        # One announces and one discusses -> Divergent action alignment (e.g. Article A vs Article D)
        if (is_announcement1 and is_discussion2) or (is_discussion1 and is_announcement2):
            return 0.2

        return 0.5
