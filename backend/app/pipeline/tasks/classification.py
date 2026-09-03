import asyncio
import logging

from app.ai.classifier import NewsClassifier
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def classify_article(article_data: dict) -> dict:
    async def _run():
        classifier = NewsClassifier()
        await classifier.initialize()
        result = await classifier.process(article_data)
        await classifier.cleanup()
        return result

    return asyncio.run(_run())
