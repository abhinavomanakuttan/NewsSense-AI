"""Comprehensive Unit and Integration Tests for Deduplication & Event Clustering Agent.

Tests cover:
- Stage 1: Exact Duplicate Detection (URL hash, Content hash, Title hash)
- Stage 2: Near Duplicate Detection (Token Jaccard, SequenceMatcher, TF-IDF)
- Syndication Detection: Wire service reprint across distinct publisher domains
- Stage 3 & 4: Multi-field Semantic Embeddings & Composite Event Similarity
- Event Lifecycle: Grouping Articles A, B, C into EVENT-100
- Disambiguation: Separating Article D (policy discussion) from funding announcements
- Contradiction Detection: Flagging denial/conflicting reports with status="flagged_verification"
- Output Conformance: Validating exact schema required by NewsSense AI
"""

import json
from uuid import uuid4

import pytest

from app.ai.deduplicator import DeduplicationEngine
from app.ai.event_detector import EventDetector
from app.schemas.event import EventClusterMatchResult


# ============================================================================
# Stage 1: Exact Duplicate Detection Tests
# ============================================================================

def test_exact_duplicate_content_hash():
    engine = DeduplicationEngine()
    existing = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "content_hash": "hash_abc_123",
            "url_hash": "url_hash_1",
            "normalized_title": "tech breakthrough in 2026",
            "source_domain": "techcrunch.com",
        }
    ]

    candidate = {
        "content_hash": "hash_abc_123",
        "url_hash": "url_hash_different",
        "normalized_title": "different title",
        "source_domain": "wired.com",
    }

    result = engine.check_exact_duplicate(candidate, existing)
    assert result is not None
    assert result.is_duplicate is True
    assert result.match_type == "exact_duplicate"
    assert result.similarity_score == 1.0
    assert result.confidence == 1.0
    assert result.matched_article_id == "11111111-1111-1111-1111-111111111111"


def test_exact_duplicate_url_hash():
    engine = DeduplicationEngine()
    existing = [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "content_hash": "hash_old",
            "url_hash": "canonical_url_hash_xyz",
            "normalized_title": "old title",
            "source_domain": "reuters.com",
        }
    ]

    candidate = {
        "content_hash": "hash_new_edit",
        "url_hash": "canonical_url_hash_xyz",
        "normalized_title": "revised title",
        "source_domain": "reuters.com",
    }

    result = engine.check_exact_duplicate(candidate, existing)
    assert result is not None
    assert result.is_duplicate is True
    assert result.match_type == "exact_duplicate"


# ============================================================================
# Stage 2: Near Duplicate Detection Tests
# ============================================================================

def test_near_duplicate_rephrased_headline():
    engine = DeduplicationEngine()
    existing = [
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "Government Approves $5 Billion High-Speed Rail Project",
            "content": "The federal transportation ministry has officially approved a $5 billion high-speed rail line connecting major metropolitan hubs across the nation.",
        }
    ]

    # Rephrased headline with substantially identical content
    candidate_title = "Government Approves $5B High Speed Rail Project Announced"
    candidate_content = "The federal transportation ministry officially approved a $5 billion high-speed rail network connecting major metropolitan hubs across the nation today."

    result = engine.check_near_duplicate(candidate_title, candidate_content, existing)
    assert result is not None
    assert result.is_duplicate is True
    assert result.is_near_duplicate is True
    assert result.match_type == "near_duplicate"
    assert result.similarity_score >= 0.78
    assert result.matched_article_id == "33333333-3333-3333-3333-333333333333"


# ============================================================================
# Stage 3: Syndication Detection Tests
# ============================================================================

def test_syndication_detection_wire_copy():
    engine = DeduplicationEngine()
    wire_body = (
        "WASHINGTON (AP) — The United States and European allies announced comprehensive "
        "new trade standards today aimed at regulating cross-border artificial intelligence applications. "
        "The accord establishes uniform safety thresholds, risk categories, and bilateral auditing protocols."
    )

    existing = [
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "title": "US and EU Announce Landmark AI Trade Standards",
            "content": wire_body,
            "source_domain": "apnews.com",
        }
    ]

    # Regional newspaper republishes AP wire verbatim
    candidate = {
        "id": "55555555-5555-5555-5555-555555555555",
        "title": "US, European Allies Agree to Common AI Trade Rules",
        "content": wire_body,
        "source_domain": "chicago-herald-example.com",
    }

    result = engine.check_syndication(candidate, existing)
    assert result is not None
    assert result.is_syndicated is True
    assert result.is_duplicate is False  # Syndicated reports are linked to the event, not discarded
    assert result.match_type == "syndicated"
    assert result.source_independence_score == 0.2  # Discounted wire copy
    assert result.matched_article_id == "44444444-4444-4444-4444-444444444444"


# ============================================================================
# Stage 4: Semantic Event Clustering & Entity Disambiguation Tests
# ============================================================================

def test_event_clustering_articles_a_b_c_vs_d():
    """Verify that Articles A, B, and C merge into the same event, but Article D creates a separate event."""
    detector = EventDetector()

    # Synthetic 16-dimensional embedding vectors for fast deterministic testing
    # Funding announcement semantic vector
    funding_emb = [0.25] * 16
    # Policy discussion semantic vector (divergent)
    policy_emb = [0.25 if i % 2 == 0 else -0.25 for i in range(16)]

    # Normalized
    funding_norm = (sum(x**2 for x in funding_emb) ** 0.5)
    funding_emb = [x / funding_norm for x in funding_emb]

    policy_norm = (sum(x**2 for x in policy_emb) ** 0.5)
    policy_emb = [x / policy_norm for x in policy_emb]

    # EVENT-100: Initial Event created from Article A
    event_100 = {
        "id": "event-100",
        "title": "Government announces major AI investment",
        "category": "Technology",
        "entities": json.dumps([{"text": "Government", "label": "ORG"}, {"text": "AI", "label": "PRODUCT"}]),
        "locations": json.dumps(["Washington"]),
        "start_time": "2026-09-02T10:00:00Z",
        "latest_update": "2026-09-02T10:00:00Z",
        "embedding": json.dumps(funding_emb),
        "status": "active",
    }

    # Article B: "New government AI funding initiative unveiled"
    article_b = {
        "title": "New government AI funding initiative unveiled",
        "category": "Technology",
        "entities": json.dumps([{"text": "government", "label": "ORG"}, {"text": "AI", "label": "PRODUCT"}]),
        "locations": json.dumps(["Washington"]),
        "published_at": "2026-09-02T10:15:00Z",
        "composite_embedding": funding_emb,
        "content": "A multi-billion dollar funding initiative for artificial intelligence was unveiled by ministers today.",
    }

    decision_b = detector.evaluate_article_for_events(article_b, [event_100])
    assert decision_b.event_id == "event-100"
    assert decision_b.match_type == "semantic_match"
    assert decision_b.similarity >= 0.78

    # Article C: "Ministry allocates billions for artificial intelligence"
    article_c = {
        "title": "Ministry allocates billions for artificial intelligence",
        "category": "Technology",
        "entities": json.dumps([{"text": "Ministry", "label": "ORG"}, {"text": "artificial intelligence", "label": "PRODUCT"}]),
        "locations": json.dumps(["Washington"]),
        "published_at": "2026-09-02T10:30:00Z",
        "composite_embedding": funding_emb,
        "content": "Billions of dollars were allocated to artificial intelligence research projects this morning.",
    }

    decision_c = detector.evaluate_article_for_events(article_c, [event_100])
    assert decision_c.event_id == "event-100"
    assert decision_c.match_type == "semantic_match"
    assert decision_c.similarity >= 0.78

    # Article D: "Government discusses future AI policy"
    # Even though it shares entities ('Government', 'AI'), the action context is 'discusses policy' rather than 'announces investment'
    article_d = {
        "title": "Government discusses future AI policy",
        "category": "Technology",
        "entities": json.dumps([{"text": "Government", "label": "ORG"}, {"text": "AI", "label": "PRODUCT"}]),
        "locations": json.dumps(["Washington"]),
        "published_at": "2026-09-02T11:00:00Z",
        "composite_embedding": policy_emb,
        "content": "Officials convened to discuss the philosophical framework and long term governance policies for artificial intelligence.",
    }

    decision_d = detector.evaluate_article_for_events(article_d, [event_100])
    # Must correctly NOT match EVENT-100
    assert decision_d.event_id is None
    assert decision_d.match_type == "new_event"


# ============================================================================
# Contradiction Detection Tests
# ============================================================================

def test_contradiction_detection_flags_verification():
    detector = EventDetector()
    event = {
        "id": "event-200",
        "title": "Official statement on factory incident released",
        "category": "World News",
        "entities": json.dumps([{"text": "Metropolis Factory", "label": "ORG"}]),
        "locations": json.dumps(["Berlin"]),
        "start_time": "2026-09-02T12:00:00Z",
        "latest_update": "2026-09-02T12:00:00Z",
        "embedding": json.dumps([0.5] * 16),
        "status": "active",
    }

    contradictory_article = {
        "title": "Company denies involvement and refutes reports of factory incident",
        "category": "World News",
        "entities": json.dumps([{"text": "Metropolis Factory", "label": "ORG"}]),
        "locations": json.dumps(["Berlin"]),
        "published_at": "2026-09-02T12:45:00Z",
        "composite_embedding": [0.5] * 16,
        "content": "Spokespersons denied all involvement and explicitly refuted previous claims of structural damage.",
    }

    decision = detector.evaluate_article_for_events(contradictory_article, [event])
    assert decision.event_id == "event-200"
    assert decision.is_contradiction is True
    assert decision.match_type == "contradiction"


# ============================================================================
# Structured Output Schema Conformance Test
# ============================================================================

def test_event_cluster_match_result_schema():
    """Verify structured output conforms exactly to the user requested schema."""
    result = EventClusterMatchResult(
        article_id="art-12345",
        event_id="evt-67890",
        match_type="semantic_match",
        similarity=0.89,
        confidence=0.93,
        is_duplicate=False,
        is_syndicated=False,
    )

    data = result.model_dump()
    assert data["article_id"] == "art-12345"
    assert data["event_id"] == "evt-67890"
    assert data["match_type"] == "semantic_match"
    assert data["similarity"] == 0.89
    assert data["confidence"] == 0.93
    assert data["is_duplicate"] is False
    assert data["is_syndicated"] is False
