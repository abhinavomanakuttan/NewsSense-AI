import asyncio
import logging

from app.ai.credibility import CredibilityAssessor
from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def assess_credibility(article_data: dict, source_data: dict, similar_articles: list[dict]) -> dict:
    async def _run():
        assessor = CredibilityAssessor()
        await assessor.initialize()
        result = await assessor.process(
            {
                "article": article_data,
                "source": source_data,
                "similar_articles": similar_articles,
            }
        )
        await assessor.cleanup()
        return result

    return asyncio.run(_run())
