"""Unit and integration tests for Vector Store & Semantic Memory System.

Validates:
- Multi-document embedding & indexing (Articles, Events, Claims, Evidence, Entities, Topics)
- SHA-256 duplicate control (avoids redundant embedding computation)
- Dense cosine semantic retrieval
- Metadata-filtered HNSW traversal (country, category, verification_status)
- Hybrid search fusing dense similarity and lexical scoring via Reciprocal Rank Fusion (RRF)
- CRUD deletion & collection telemetry
"""

import pytest
from qdrant_client import QdrantClient

from app.schemas.vector_store import (
    VectorMetadata,
    VectorPointInput,
    VectorSearchFilter,
)
from app.services.vector_store_service import (
    PRIMARY_COLLECTION,
    VectorStoreService,
)


@pytest.fixture
def memory_vector_store():
    """Create an isolated, in-memory VectorStoreService for deterministic testing."""
    service = VectorStoreService()
    # Inject pure in-memory client
    service._client = QdrantClient(":memory:")
    service._engine_type = "qdrant_embedded_memory"
    service.ensure_collection()
    return service


# ============================================================================
# Multi-Document Embedding & Indexing Tests
# ============================================================================

def test_multi_document_indexing(memory_vector_store: VectorStoreService):
    """Verify that heterogeneous news items are indexed with appropriate document types."""
    # 1. Index Article
    meta_art = VectorMetadata(
        document_id="art-101",
        document_type="article",
        category="Technology",
        country="US",
        title="OpenAI releases new reasoning model",
        snippet="OpenAI officially launched its next-generation reasoning AI model today.",
    )
    pid_art, recomputed_art = memory_vector_store.upsert_document(
        document_id="art-101",
        document_type="article",
        text="OpenAI releases new reasoning model with advanced code generation.",
        metadata=meta_art,
    )
    assert pid_art == memory_vector_store.make_point_id("article", "art-101")
    assert recomputed_art is True

    # 2. Index Claim
    meta_claim = VectorMetadata(
        document_id="clm-202",
        document_type="claim",
        category="Technology",
        verification_status="WELL_SUPPORTED",
        title="Claim: Model achieves 95% accuracy",
        snippet="The model achieved 95% benchmark accuracy.",
    )
    pid_claim, recomputed_claim = memory_vector_store.upsert_document(
        document_id="clm-202",
        document_type="claim",
        text="The new reasoning model achieves 95% accuracy on standard mathematics benchmarks.",
        metadata=meta_claim,
    )
    assert pid_claim == memory_vector_store.make_point_id("claim", "clm-202")
    assert recomputed_claim is True

    # 3. Index Evidence
    meta_ev = VectorMetadata(
        document_id="evi-303",
        document_type="evidence",
        verification_status="WELL_SUPPORTED",
        title="Evidence from benchmark evaluation",
        snippet="Independent evaluation confirmed 95.2% benchmark score.",
    )
    pid_ev, _ = memory_vector_store.upsert_document(
        document_id="evi-303",
        document_type="evidence",
        text="Independent evaluation by Stanford researchers confirmed 95.2% accuracy.",
        metadata=meta_ev,
    )
    assert pid_ev == memory_vector_store.make_point_id("evidence", "evi-303")


# ============================================================================
# Duplicate Control Tests
# ============================================================================

def test_duplicate_control_via_content_hash(memory_vector_store: VectorStoreService):
    """Verify that re-indexing identical text skips the embedding step."""
    text = "Semiconductor manufacturing facility opens in Gujarat with $10 billion investment."
    meta = VectorMetadata(
        document_id="art-semi-1",
        document_type="article",
        category="Business",
        country="IN",
        title="Gujarat Semiconductor Plant Launch",
    )

    # First indexing: must recompute
    pid1, recomputed1 = memory_vector_store.upsert_document(
        document_id="art-semi-1",
        document_type="article",
        text=text,
        metadata=meta,
    )
    assert recomputed1 is True

    # Second indexing with identical text: must NOT recompute
    pid2, recomputed2 = memory_vector_store.upsert_document(
        document_id="art-semi-1",
        document_type="article",
        text=text,
        metadata=meta,
    )
    assert recomputed2 is False
    assert pid1 == pid2

    # Third indexing with modified text: MUST recompute
    pid3, recomputed3 = memory_vector_store.upsert_document(
        document_id="art-semi-1",
        document_type="article",
        text=text + " Construction is scheduled to finish by 2026.",
        metadata=meta,
    )
    assert recomputed3 is True


# ============================================================================
# Dense Semantic Search Tests
# ============================================================================

def test_dense_semantic_search(memory_vector_store: VectorStoreService):
    """Verify semantic retrieval matches concepts even with different phrasing."""
    articles = [
        ("art-ai", "article", "Artificial intelligence algorithms break records in protein folding simulations.", "Technology"),
        ("art-cricket", "article", "India defeats Australia in thrilling cricket world cup final.", "Sports"),
        ("art-econ", "article", "Central bank raises interest rates to curb rising inflation pressures.", "Business"),
    ]
    for doc_id, doc_type, text, cat in articles:
        meta = VectorMetadata(document_id=doc_id, document_type=doc_type, category=cat, title=text[:40])
        memory_vector_store.upsert_document(doc_id, doc_type, text, meta)

    # Query without exact words
    results = memory_vector_store.search(
        query="latest machine learning breakthroughs in biology",
        top_k=3,
        hybrid=False,
    )
    assert len(results) >= 1
    assert results[0].document_id == "art-ai"
    assert results[0].metadata.category == "Technology"


# ============================================================================
# Metadata Filtering Tests
# ============================================================================

def test_metadata_filtering(memory_vector_store: VectorStoreService):
    """Verify filtering by country, category, and verification status."""
    docs = [
        ("art-in-tech", "article", "Bengaluru tech startups secure funding for generative AI platforms.", "Technology", "IN", None),
        ("art-us-tech", "article", "Silicon Valley tech giants invest in quantum computing infrastructure.", "Technology", "US", None),
        ("clm-disputed", "claim", "Opposition leaders claim voting machines were malfunctioning.", "Politics", "IN", "DISPUTED"),
        ("clm-verified", "claim", "Election commission officially verifies 67% voter turnout rate.", "Politics", "IN", "WELL_SUPPORTED"),
    ]
    for doc_id, doc_type, text, cat, country, verdict in docs:
        meta = VectorMetadata(
            document_id=doc_id,
            document_type=doc_type,
            category=cat,
            country=country,
            verification_status=verdict,
            title=text[:40],
        )
        memory_vector_store.upsert_document(doc_id, doc_type, text, meta)

    # Filter 1: Technology in India only
    res_in_tech = memory_vector_store.search(
        query="technology innovation startups",
        filter_spec=VectorSearchFilter(category="Technology", country="IN"),
    )
    assert len(res_in_tech) == 1
    assert res_in_tech[0].document_id == "art-in-tech"

    # Filter 2: Show opposing / disputed reports only
    res_disputed = memory_vector_store.search(
        query="election voting voting machines turnout",
        filter_spec=VectorSearchFilter(verification_status="DISPUTED"),
    )
    assert len(res_disputed) == 1
    assert res_disputed[0].document_id == "clm-disputed"
    assert res_disputed[0].metadata.verification_status == "DISPUTED"


# ============================================================================
# Hybrid Search with Reciprocal Rank Fusion (RRF) Tests
# ============================================================================

def test_hybrid_search_reciprocal_rank_fusion(memory_vector_store: VectorStoreService):
    """Verify that hybrid search combines semantic similarity with exact keyword matches."""
    memory_vector_store.upsert_document(
        document_id="doc-keyword-heavy",
        document_type="article",
        text="India election updates: parliamentary election phases, polling dates, and candidate lists.",
        metadata=VectorMetadata(
            document_id="doc-keyword-heavy",
            document_type="article",
            title="India Election Updates",
            category="Politics",
            country="IN",
        ),
    )
    memory_vector_store.upsert_document(
        document_id="doc-semantic-heavy",
        document_type="article",
        text="Democratic voting exercise in South Asia where citizens cast ballots for national leadership.",
        metadata=VectorMetadata(
            document_id="doc-semantic-heavy",
            document_type="article",
            title="South Asian Democratic Voting",
            category="Politics",
            country="IN",
        ),
    )

    results = memory_vector_store.search(
        query="India election updates",
        top_k=2,
        hybrid=True,
        alpha=0.50,
    )
    assert len(results) == 2
    # Document with both dense and exact keyword matches ranks #1
    assert results[0].document_id == "doc-keyword-heavy"
    assert results[0].dense_score is not None
    assert results[0].lexical_score is not None
    assert results[0].score > 0.0


# ============================================================================
# Deletion & Stats Tests
# ============================================================================

def test_deletion_and_stats(memory_vector_store: VectorStoreService):
    """Verify document deletion and telemetry accuracy."""
    meta = VectorMetadata(document_id="doc-delete-test", document_type="article", title="Temp Article")
    memory_vector_store.upsert_document("doc-delete-test", "article", "Temporary content to delete", meta)

    stats_before = memory_vector_store.get_stats()
    assert stats_before.document_type_counts["article"] >= 1

    deleted = memory_vector_store.delete_document("article", "doc-delete-test")
    assert deleted is True

    # Search should no longer return it
    search_res = memory_vector_store.search("Temporary content to delete", top_k=5)
    assert not any(r.document_id == "doc-delete-test" for r in search_res)
