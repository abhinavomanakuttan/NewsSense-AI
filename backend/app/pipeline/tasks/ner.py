import asyncio
import logging

from app.ai.ner import NERExtractor
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def extract_entities(article_data: dict) -> dict:
    async def _run():
        extractor = NERExtractor()
        await extractor.initialize()
        result = await extractor.process(article_data)
        await extractor.cleanup()
        return result

    return asyncio.run(_run())
