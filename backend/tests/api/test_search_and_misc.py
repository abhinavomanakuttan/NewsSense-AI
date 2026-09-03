"""API tests for search, categories, sources, and admin."""


async def test_search_anonymous(client, article_fixture):
    resp = await client.post("/api/v1/search", json={"query": "AI"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "AI Breakthrough in Health"


async def test_search_no_results(client):
    resp = await client.post("/api/v1/search", json={"query": "nonexistentxyz"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_search_authenticated_tracks_history(
    client, auth_headers, article_fixture, db_session
):
    resp = await client.post("/api/v1/search", headers=auth_headers, json={"query": "AI"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    from sqlalchemy import func, select

    from app.models.search_history import SearchHistory

    count = (await db_session.execute(select(func.count()).select_from(SearchHistory))).scalar()
    assert count >= 1


async def test_search_filter_by_category(client, article_fixture, category_fixture):
    resp = await client.post("/api/v1/search", json={"query": "AI", "category": "Technology"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["category_name"] == "Technology"

    resp = await client.post("/api/v1/search", json={"query": "AI", "category": "Sports"})
    assert resp.json()["total"] == 0


async def test_search_filter_by_source(client, article_fixture, source_fixture):
    resp = await client.post("/api/v1/search", json={"query": "AI", "source": "Test News"})
    assert resp.json()["total"] == 1

    resp = await client.post("/api/v1/search", json={"query": "AI", "source": "Nope News"})
    assert resp.json()["total"] == 0


async def test_search_pagination_and_total(client, article_fixture):
    resp = await client.post("/api/v1/search", json={"query": "AI", "page": 1, "page_size": 5})
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 1
    assert len(body["results"]) == 1


async def test_search_sort_by_date(client, article_fixture, db_session):
    from app.repositories.article_repository import ArticleRepository

    await ArticleRepository(db_session).create(
        title="AI in Space",
        slug="ai-space",
        url="https://testnews.com/ai-space",
        content="AI powers space rovers.",
        content_hash="test-hash-space",
        published_at="2026-07-31T10:00:00",
    )
    await db_session.commit()

    resp = await client.post("/api/v1/search", json={"query": "AI", "sort_by": "date"})
    assert resp.json()["total"] == 2
    assert resp.json()["results"][0]["title"] == "AI in Space"


async def test_list_categories(client, category_fixture):
    resp = await client.get("/api/v1/categories")
    assert resp.status_code == 200
    assert resp.json()[0]["slug"] == "technology"


async def test_get_category(client, category_fixture):
    resp = await client.get("/api/v1/categories/technology")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Technology"


async def test_create_category(client):
    resp = await client.post(
        "/api/v1/categories",
        json={"name": "Health", "slug": "health", "description": "Health news"},
    )
    assert resp.status_code == 201
    assert resp.json()["slug"] == "health"


async def test_create_duplicate_category(client, category_fixture):
    resp = await client.post(
        "/api/v1/categories",
        json={"name": "Tech Again", "slug": "technology"},
    )
    assert resp.status_code == 409


async def test_list_sources(client, source_fixture):
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Test News"


async def test_get_source(client, source_fixture):
    resp = await client.get(f"/api/v1/sources/{source_fixture['id']}")
    assert resp.status_code == 200
    assert resp.json()["reputation_score"] == 0.8


async def test_admin_analytics_denied_for_user(client, auth_headers):
    resp = await client.get("/api/v1/analytics/overview", headers=auth_headers)
    assert resp.status_code == 403


async def test_admin_analytics_overview(client, admin_headers, article_fixture):
    resp = await client.get("/api/v1/analytics/overview", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] >= 1
    assert body["total_articles"] >= 1
    assert body["total_sources"] >= 1
    assert "active_users_today" in body
    assert "total_searches" in body
    assert "total_events" in body
