from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.api.v1 as api
import app.api.ws as ws
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import PrometheusMiddleware, metrics_response
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import create_tables

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_sqlite = settings.database_url.startswith("sqlite")
    if is_sqlite:
        await create_tables()
    from app.utils.cache import cache_service

    await cache_service.initialize()

    from app.services.notification_dispatcher import notification_dispatcher

    await notification_dispatcher.start()
    yield
    await notification_dispatcher.stop()
    await cache_service.close()


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PrometheusMiddleware)

app.include_router(api.auth.router, prefix="/api/v1")
app.include_router(api.users.router, prefix="/api/v1")
app.include_router(api.articles.router, prefix="/api/v1")
app.include_router(api.news.router, prefix="/api/v1")
app.include_router(api.sources.router, prefix="/api/v1")
app.include_router(api.categories.router, prefix="/api/v1")
app.include_router(api.tags.router, prefix="/api/v1")
app.include_router(api.bookmarks.router, prefix="/api/v1")
app.include_router(api.notifications.router, prefix="/api/v1")
app.include_router(api.events.router, prefix="/api/v1")
app.include_router(api.summaries.router, prefix="/api/v1")
app.include_router(api.search.router, prefix="/api/v1")
app.include_router(api.reading_history.router, prefix="/api/v1")
app.include_router(api.recommendations.router, prefix="/api/v1")
app.include_router(api.chatbot.router, prefix="/api/v1")
app.include_router(api.analytics.router, prefix="/api/v1")
app.include_router(api.admin.router, prefix="/api/v1")
app.include_router(api.orchestrator.router, prefix="/api/v1")
app.include_router(api.verification.router, prefix="/api/v1")
app.include_router(api.framing.router, prefix="/api/v1")
app.include_router(api.vectors.router, prefix="/api/v1")
app.include_router(ws.router)

# Direct /api aliases for user convenience
for r in [
    api.news.router,
    api.events.router,
    api.categories.router,
    api.sources.router,
    api.search.router,
    api.verification.router,
    api.summaries.router,
    api.recommendations.router,
    api.bookmarks.router,
    api.users.router,
    api.chatbot.router,
]:
    app.include_router(r, prefix="/api")


@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.project_name,
        "version": settings.version,
    }


@app.get("/metrics")
async def metrics():
    return metrics_response()
