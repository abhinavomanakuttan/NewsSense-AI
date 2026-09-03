"""Run the ingestion pipeline directly without a Celery broker.

Usage:
    python -m scripts.run_pipeline [source_id ...]
    python -m scripts.run_pipeline --all
    python -m scripts.run_pipeline --list
    python -m scripts.run_pipeline <source_id> --enrich

With no args, ingests the first active source that has a feed_url. Pass
--enrich to run AI enrichment (classification, sentiment, NER, credibility,
summarization, embeddings) on newly ingested articles.
"""

import asyncio
import sys
from uuid import UUID

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.source import Source
from app.services.article_ingestion_service import ArticleIngestionService


async def list_sources() -> list[Source]:
    async with async_session_factory() as session:
        result = await session.execute(select(Source).order_by(Source.name))
        sources = list(result.scalars().all())
        session.expunge_all()
        return sources


async def run_single(source_id: str, enrich: bool = False) -> dict:
    async with ArticleIngestionService() as service:
        result = await service.ingest_source(UUID(source_id))
    if enrich:
        from app.services.article_enrichment_service import ArticleEnrichmentService

        for article_id in result.get("new_article_ids", []):
            try:
                async with ArticleEnrichmentService() as service:
                    enriched = await service.enrich_article(article_id)
                print(f"  enriched {article_id}: {enriched['steps']}")
            except Exception as exc:
                print(f"  enrichment failed for {article_id}: {exc}")
    return result


async def main() -> int:
    args = sys.argv[1:]
    if "--list" in args:
        for source in await list_sources():
            active = "active" if source.is_active else "inactive"
            feed = source.feed_url or "-"
            print(f"{source.id}  [{active}]  {source.name}  {feed}")
        return 0

    sources = await list_sources()
    if not sources:
        print("No sources found. Run `python -m scripts.seed` first.")
        return 1

    if "--all" in args:
        targets = [s.id for s in sources if s.is_active and s.feed_url]
    else:
        ids = [a for a in args if not a.startswith("-")]
        if ids:
            targets = []
            for raw in ids:
                try:
                    targets.append(UUID(raw))
                except ValueError:
                    print(f"Ignoring invalid source id: {raw}")
        else:
            targets = [s.id for s in sources if s.is_active and s.feed_url][:1]

    if not targets:
        print("No active sources with a feed_url to ingest.")
        return 1

    for source_id in targets:
        print(f"Ingesting {source_id} ...")
        try:
            result = await run_single(str(source_id), enrich="--enrich" in args)
            print(f"  -> {result}")
        except Exception as exc:
            print(f"  -> FAILED: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
