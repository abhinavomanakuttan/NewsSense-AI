from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "smartfeed",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "fetch-all-feeds": {
            "task": "app.pipeline.tasks.feed_fetcher.fetch_all_feeds",
            "schedule": 300.0,
        },
        "update-trending": {
            "task": "app.pipeline.tasks.recommendation_updater.update_trending",
            "schedule": 1800.0,
        },
    },
)

# Import task modules so Celery discovers their @task decorators.
import app.pipeline.tasks.enrichment  # noqa: E402, F401
import app.pipeline.tasks.feed_fetcher  # noqa: E402, F401
import app.pipeline.tasks.indexer  # noqa: E402, F401
import app.pipeline.tasks.ner  # noqa: E402, F401
import app.pipeline.tasks.orchestration  # noqa: E402, F401
import app.pipeline.tasks.recommendation_updater  # noqa: E402, F401
import app.pipeline.tasks.sentiment  # noqa: E402, F401
