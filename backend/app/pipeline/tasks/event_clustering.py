import asyncio
import logging

from app.ai.event_clusterer import EventClusterer
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def cluster_articles(articles: list[dict], embeddings: list[list[float]]) -> dict:
    async def _run():
        clusterer = EventClusterer()
        await clusterer.initialize()
        result = await clusterer.process({"articles": articles, "embeddings": embeddings})
        await clusterer.cleanup()
        return result

    return asyncio.run(_run())
