"""Prometheus instrumentation.

Exposes a `/metrics` endpoint scraped by Prometheus, HTTP request metrics via a
middleware, and small app-level counters (WebSockets, notifications, ingested
articles, enrichment runs). Metrics recording is best-effort and never breaks
the request path.
"""

from __future__ import annotations

import re
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_UUID_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# --- HTTP metrics ---------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_INFLIGHT = Gauge(
    "http_requests_inflight",
    "Number of HTTP requests currently being handled.",
)

# --- App-level metrics ----------------------------------------------------

WS_CONNECTIONS_ACTIVE = Gauge(
    "ws_connections_active",
    "Number of active WebSocket connections.",
)

NOTIFICATIONS_DISPATCHED_TOTAL = Counter(
    "notifications_dispatched_total",
    "Total notifications dispatched to sockets / Redis fan-out.",
)

ARTICLES_INGESTED_TOTAL = Counter(
    "articles_ingested_total",
    "Total articles ingested (new, not duplicates).",
)

ENRICHMENT_RUNS_TOTAL = Counter(
    "enrichment_runs_total",
    "Article enrichment attempts.",
)


def normalize_path(path: str) -> str:
    """Replace UUID path segments with `{id}` to bound label cardinality."""
    return _UUID_RE.sub("/{id}", path)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        HTTP_REQUESTS_INFLIGHT.inc()
        method = request.method
        path = normalize_path(request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status="500").inc()
            raise
        finally:
            HTTP_REQUESTS_INFLIGHT.dec()

        duration = time.perf_counter() - start
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(response.status_code)).inc()
        return response


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
