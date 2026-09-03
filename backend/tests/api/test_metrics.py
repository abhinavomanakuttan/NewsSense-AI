"""Tests for the Prometheus /metrics endpoint and path normalization."""

from uuid import uuid4

from app.core.metrics import normalize_path


async def test_metrics_endpoint_returns_prometheus_format(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "# HELP" in body
    assert "# TYPE http_requests_total counter" in body


async def test_metrics_record_http_requests(client):
    await client.get("/metrics")
    resp = await client.get("/metrics")
    assert "http_requests_total" in resp.text
    assert "http_request_duration_seconds" in resp.text


async def test_metrics_normalize_uuid_paths(client):
    missing = uuid4()
    await client.get(f"/api/v1/sources/{missing}")
    resp = await client.get("/metrics")
    body = resp.text
    assert f'path="/api/v1/sources/{missing}"' not in body
    assert 'path="/api/v1/sources/{id}"' in body
    assert 'status="404"' in body


async def test_metrics_health_and_metrics_exempt(client):
    # /health should not be scraped but must still work
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_normalize_path_plain():
    assert normalize_path("/api/v1/articles/trending") == "/api/v1/articles/trending"


def test_normalize_path_with_uuid():
    path = f"/api/v1/sources/{uuid4()}/refresh"
    assert normalize_path(path) == "/api/v1/sources/{id}/refresh"


def test_normalize_path_multiple_uuids():
    path = f"/api/v1/events/{uuid4()}/articles/{uuid4()}"
    assert normalize_path(path) == "/api/v1/events/{id}/articles/{id}"
