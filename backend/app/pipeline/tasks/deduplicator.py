import hashlib
import logging

from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def deduplicate_articles(articles: list[dict]) -> dict:
    seen_hashes = set()
    unique_articles = []
    duplicates = []

    for article in articles:
        content_hash = article.get("content_hash")
        if not content_hash:
            content = (article.get("title", "") + article.get("content", "")).encode()
            content_hash = hashlib.sha256(content).hexdigest()
            article["content_hash"] = content_hash

        if content_hash in seen_hashes:
            duplicates.append(article)
        else:
            seen_hashes.add(content_hash)
            unique_articles.append(article)

    return {
        "unique_articles": unique_articles,
        "duplicates": duplicates,
        "total_input": len(articles),
        "unique_count": len(unique_articles),
        "duplicate_count": len(duplicates),
    }
