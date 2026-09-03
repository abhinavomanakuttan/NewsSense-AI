from app.pipeline.celery_app import celery_app


def start_scheduler():
    celery_app.start(argv=["celery", "beat", "-A", "app.pipeline.celery_app", "--loglevel=info"])
