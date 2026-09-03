"""API tests for bookmarks and reading history."""


async def test_bookmarks_require_auth(client):
    resp = await client.get("/api/v1/bookmarks")
    assert resp.status_code == 401


async def test_add_bookmark(client, auth_headers, article_fixture):
    resp = await client.post(
        "/api/v1/bookmarks",
        headers=auth_headers,
        json={"article_id": str(article_fixture["id"])},
    )
    assert resp.status_code == 201
    assert resp.json()["article_id"] == str(article_fixture["id"])


async def test_add_bookmark_duplicate(client, auth_headers, article_fixture):
    payload = {"article_id": str(article_fixture["id"])}
    await client.post("/api/v1/bookmarks", headers=auth_headers, json=payload)
    resp = await client.post("/api/v1/bookmarks", headers=auth_headers, json=payload)
    assert resp.status_code == 409


async def test_add_bookmark_missing_article(client, auth_headers):
    resp = await client.post(
        "/api/v1/bookmarks",
        headers=auth_headers,
        json={"article_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


async def test_list_bookmarks(client, auth_headers, article_fixture):
    await client.post(
        "/api/v1/bookmarks",
        headers=auth_headers,
        json={"article_id": str(article_fixture["id"])},
    )
    resp = await client.get("/api/v1/bookmarks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "AI Breakthrough in Health"
    assert body[0]["slug"] == article_fixture["slug"]


async def test_remove_bookmark(client, auth_headers, article_fixture):
    await client.post(
        "/api/v1/bookmarks",
        headers=auth_headers,
        json={"article_id": str(article_fixture["id"])},
    )
    resp = await client.delete(f"/api/v1/bookmarks/{article_fixture['id']}", headers=auth_headers)
    assert resp.status_code == 204


async def test_reading_history_requires_auth(client):
    resp = await client.get("/api/v1/reading-history")
    assert resp.status_code == 401


async def test_record_reading(client, auth_headers, article_fixture):
    resp = await client.post(
        "/api/v1/reading-history",
        headers=auth_headers,
        json={
            "article_id": str(article_fixture["id"]),
            "read_duration_seconds": 30,
            "scroll_depth": 50,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["read_duration_seconds"] == 30
    assert body["title"] == "AI Breakthrough in Health"


async def test_record_reading_accumulates(client, auth_headers, article_fixture):
    payload = {
        "article_id": str(article_fixture["id"]),
        "read_duration_seconds": 30,
        "scroll_depth": 50,
    }
    await client.post("/api/v1/reading-history", headers=auth_headers, json=payload)
    resp = await client.post(
        "/api/v1/reading-history",
        headers=auth_headers,
        json={**payload, "scroll_depth": 20},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["read_duration_seconds"] == 60
    assert body["scroll_depth"] == 50


async def test_record_reading_missing_article(client, auth_headers):
    resp = await client.post(
        "/api/v1/reading-history",
        headers=auth_headers,
        json={
            "article_id": "00000000-0000-0000-0000-000000000000",
            "read_duration_seconds": 5,
        },
    )
    assert resp.status_code == 404


async def test_list_reading_history(client, auth_headers, article_fixture):
    await client.post(
        "/api/v1/reading-history",
        headers=auth_headers,
        json={"article_id": str(article_fixture["id"]), "read_duration_seconds": 15},
    )
    resp = await client.get("/api/v1/reading-history", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["source_name"] == "Test News"


async def test_clear_reading_history(client, auth_headers, article_fixture):
    await client.post(
        "/api/v1/reading-history",
        headers=auth_headers,
        json={"article_id": str(article_fixture["id"]), "read_duration_seconds": 15},
    )
    resp = await client.delete("/api/v1/reading-history", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/reading-history", headers=auth_headers)
    assert resp.json()["total"] == 0


async def test_remove_single_history_record(client, auth_headers, article_fixture):
    resp = await client.post(
        "/api/v1/reading-history",
        headers=auth_headers,
        json={"article_id": str(article_fixture["id"]), "read_duration_seconds": 15},
    )
    history_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/reading-history/{history_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/reading-history", headers=auth_headers)
    assert resp.json()["total"] == 0


async def test_remove_single_history_record_missing(client, auth_headers):
    resp = await client.delete(
        "/api/v1/reading-history/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
