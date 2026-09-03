import asyncio
import logging

from app.ai.sentiment import SentimentAnalyzer
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def analyze_sentiment(article_data: dict) -> dict:
    async def _run():
        analyzer = SentimentAnalyzer()
        await analyzer.initialize()
        result = await analyzer.process(article_data)
        await analyzer.cleanup()
        return result

    return asyncio.run(_run())
