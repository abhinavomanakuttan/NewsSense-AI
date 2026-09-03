import logging

from app.ai.embeddings import EmbeddingGenerator
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def generate_article_embedding(article_data: dict) -> dict:
    import asyncio

    async def _run():
        generator = EmbeddingGenerator()
        await generator.initialize()
        result = await generator.process(article_data)
        await generator.cleanup()
        return result

    return asyncio.run(_run())


@celery_app.task
def generate_batch_embeddings(articles: list[dict]) -> list[dict]:
    import asyncio

    async def _run():
        generator = EmbeddingGenerator()
        await generator.initialize()
        texts = [a.get("title", "") + " " + (a.get("content", "") or "")[:2000] for a in articles]
        embeddings = await generator.process_batch(texts)
        await generator.cleanup()

        return [
            {
                "article_id": a.get("id"),
                "embedding": emb.tolist(),
                "dimension": len(emb),
            }
            for a, emb in zip(articles, embeddings, strict=True)
        ]

    return asyncio.run(_run())
