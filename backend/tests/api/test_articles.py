"""API tests for the articles endpoints."""


async def test_list_articles_empty(client):
    resp = await client.get("/api/v1/articles")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_articles(client, article_fixture):
    resp = await client.get("/api/v1/articles")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "AI Breakthrough in Health"
    assert body[0]["source_name"] == "Test News"
    assert body[0]["category_name"] == "Technology"


async def test_get_article_by_slug(client, article_fixture):
    resp = await client.get("/api/v1/articles/ai-breakthrough-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"].startswith("Scientists")
    assert body["source_name"] == "Test News"
    assert body["category_name"] == "Technology"


async def test_get_article_not_found(client):
    resp = await client.get("/api/v1/articles/does-not-exist")
    assert resp.status_code == 404


async def test_get_article_increments_views(client, article_fixture):
    await client.get("/api/v1/articles/ai-breakthrough-health")
    resp = await client.get("/api/v1/articles/ai-breakthrough-health")
    assert resp.status_code == 200
    assert resp.json()["view_count"] == "2"


async def test_get_trending(client, article_fixture):
    resp = await client.get("/api/v1/articles/trending")
    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "AI Breakthrough in Health"
