"""FastAPI Endpoints for Vector Store, Semantic Memory, and Hybrid Search."""

import time
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.article import Article
from app.models.claim import Claim, ClaimEvidence
from app.models.event import Event
from app.models.vector_document import DocumentEmbedding
from app.schemas.vector_store import (
    ReindexRequest,
    ReindexResponse,
    VectorMetadata,
    VectorPointInput,
    VectorSearchFilter,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
    VectorStoreStatsResponse,
)
from app.services.vector_store_service import VectorStoreService, get_vector_store

router = APIRouter(prefix="/vectors", tags=["Vector Store & Semantic Memory"])


@router.post("/search", response_model=VectorSearchResponse)
async def search_semantic_memory(
    request: VectorSearchRequest,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Execute dense or hybrid semantic search across news memory with metadata filters."""
    results = vector_store.search(
        query=request.query,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
        filter_spec=request.filter,
        hybrid=request.hybrid,
        alpha=request.alpha,
    )
    return VectorSearchResponse(
        query=request.query,
        total_hits=len(results),
        hybrid=request.hybrid,
        results=results,
    )


@router.post("/upsert")
async def upsert_vector_point(
    payload: VectorPointInput,
    db: AsyncSession = Depends(get_db),
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Upsert a single document into semantic memory with SHA-256 duplicate control."""
    point_id, was_recomputed = vector_store.upsert_document(
        document_id=payload.document_id,
        document_type=payload.document_type,
        text=payload.text,
        metadata=payload.metadata,
    )

    # Synchronize relational tracking table
    content_hash = vector_store.compute_content_hash(payload.text)
    stmt = select(DocumentEmbedding).where(DocumentEmbedding.point_id == point_id)
    res = await db.execute(stmt)
    tracking = res.scalars().first()

    if not tracking:
        tracking = DocumentEmbedding(
            id=uuid.uuid4(),
            document_id=payload.document_id,
            document_type=payload.document_type,
            point_id=point_id,
            content_hash=content_hash,
            category=payload.metadata.category,
            country=payload.metadata.country,
            language=payload.metadata.language,
            published_at=payload.metadata.published_at,
            verification_status=payload.metadata.verification_status,
            event_id=payload.metadata.event_id,
            article_id=payload.metadata.article_id,
            source_id=payload.metadata.source_id,
        )
        db.add(tracking)
    else:
        tracking.content_hash = content_hash
        tracking.document_version += 1
        tracking.category = payload.metadata.category
        tracking.country = payload.metadata.country
        tracking.verification_status = payload.metadata.verification_status

    await db.commit()
    return {
        "status": "success",
        "point_id": point_id,
        "was_recomputed": was_recomputed,
        "content_hash": content_hash,
    }


@router.get("/stats", response_model=VectorStoreStatsResponse)
async def get_vector_store_statistics(
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Retrieve operational metrics, vector counts, and storage engine telemetry."""
    return vector_store.get_stats()


@router.delete("/{document_type}/{document_id}")
async def delete_vector_point(
    document_type: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Delete a point from semantic memory and clean relational audit record."""
    deleted = vector_store.delete_document(document_type, document_id)
    point_id = vector_store.make_point_id(document_type, document_id)

    stmt = select(DocumentEmbedding).where(DocumentEmbedding.point_id == point_id)
    res = await db.execute(stmt)
    tracking = res.scalars().first()
    if tracking:
        await db.delete(tracking)
        await db.commit()

    return {"status": "deleted" if deleted else "not_found", "point_id": point_id}


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_documents(
    request: ReindexRequest = ReindexRequest(),
    db: AsyncSession = Depends(get_db),
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Re-index documents from SQLite/Postgres tables into vector memory."""
    start_time = time.time()
    indexed = 0
    skipped = 0
    types = request.document_types or ["article", "event_summary", "claim", "evidence"]

    # 1. Reindex Articles
    if "article" in types:
        stmt_art = select(Article).limit(200)
        articles = (await db.execute(stmt_art)).scalars().all()
        for art in articles:
            text = f"{art.title}. {art.summary or art.content or ''}"
            meta = VectorMetadata(
                document_id=str(art.id),
                document_type="article",
                article_id=str(art.id),
                source_id=str(art.source_id) if art.source_id else None,
                category=art.category_name,
                country=art.country,
                language=art.language or "en",
                published_at=art.published_at,
                title=art.title,
                snippet=(art.summary or art.content or "")[:300],
            )
            _, recomputed = vector_store.upsert_document(
                document_id=str(art.id),
                document_type="article",
                text=text,
                metadata=meta,
                force_reembed=request.force_all,
            )
            if recomputed:
                indexed += 1
            else:
                skipped += 1

    # 2. Reindex Events
    if "event_summary" in types:
        stmt_evt = select(Event).limit(200)
        events = (await db.execute(stmt_evt)).scalars().all()
        for evt in events:
            text = f"{evt.title}. {evt.summary or evt.description or ''}"
            meta = VectorMetadata(
                document_id=str(evt.id),
                document_type="event_summary",
                event_id=str(evt.id),
                category=evt.category,
                title=evt.title,
                snippet=(evt.summary or evt.description or "")[:300],
            )
            _, recomputed = vector_store.upsert_document(
                document_id=str(evt.id),
                document_type="event_summary",
                text=text,
                metadata=meta,
                force_reembed=request.force_all,
            )
            if recomputed:
                indexed += 1
            else:
                skipped += 1

    # 3. Reindex Claims
    if "claim" in types:
        stmt_claims = select(Claim).limit(200)
        claims = (await db.execute(stmt_claims)).scalars().all()
        for clm in claims:
            meta = VectorMetadata(
                document_id=str(clm.id),
                document_type="claim",
                event_id=str(clm.event_id) if clm.event_id else None,
                article_id=str(clm.article_id) if clm.article_id else None,
                verification_status=clm.verdict,
                title=f"Claim: {clm.claim_text[:60]}",
                snippet=clm.claim_text,
            )
            _, recomputed = vector_store.upsert_document(
                document_id=str(clm.id),
                document_type="claim",
                text=clm.claim_text,
                metadata=meta,
                force_reembed=request.force_all,
            )
            if recomputed:
                indexed += 1
            else:
                skipped += 1

    duration = round(time.time() - start_time, 2)
    return ReindexResponse(
        status="completed",
        indexed_count=indexed,
        skipped_count=skipped,
        duration_seconds=duration,
    )
