import asyncio
import logging

from app.ai.summarizer import NewsSummarizer
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def summarize_article(article_data: dict) -> dict:
    async def _run():
        summarizer = NewsSummarizer()
        await summarizer.initialize()
        result = await summarizer.process(article_data)
        await summarizer.cleanup()
        return result

    return asyncio.run(_run())
