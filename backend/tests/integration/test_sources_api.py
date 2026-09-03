"""Integration tests for Source Management API endpoints and ingestion triggers."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_and_filter_sources(client: AsyncClient, admin_headers: dict):
    """Test GET /api/v1/sources with query filters."""
    response = await client.get("/api/v1/sources?category=technology", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_and_toggle_source(client: AsyncClient, admin_headers: dict):
    """Test POST /api/v1/sources and POST /api/v1/sources/{source_id}/toggle."""
    payload = {
        "name": "Integration Test Feed",
        "url": "https://integrationtestfeed.org",
        "feed_url": "https://integrationtestfeed.org/rss.xml",
        "source_type": "rss",
        "category": "technology",
        "language": "en",
        "country": "us",
        "priority": "normal",
        "active": True,
    }
    create_resp = await client.post("/api/v1/sources", json=payload, headers=admin_headers)
    assert create_resp.status_code == 201, create_resp.text
    source_data = create_resp.json()
    source_id = source_data["id"]

    # Check metrics
    metrics_resp = await client.get(f"/api/v1/sources/{source_id}/metrics", headers=admin_headers)
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["name"] == "Integration Test Feed"
    assert metrics["is_active"] is True

    # Toggle active status dynamically without code changes
    toggle_resp = await client.post(f"/api/v1/sources/{source_id}/toggle", headers=admin_headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_active"] is False

    # Toggle back to active
    toggle_back = await client.post(f"/api/v1/sources/{source_id}/toggle", headers=admin_headers)
    assert toggle_back.status_code == 200
    assert toggle_back.json()["is_active"] is True
