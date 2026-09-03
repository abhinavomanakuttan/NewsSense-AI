"""API tests for the users & preferences endpoints."""


async def test_get_me_requires_auth(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_get_me(client, auth_headers):
    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"]
    assert body["role"] == "user"
    assert "hashed_password" not in body


async def test_update_profile(client, auth_headers):
    resp = await client.put(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


async def test_get_preferences_defaults(client, auth_headers):
    resp = await client.get("/api/v1/users/me/preferences", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_languages"] == ["en"]
    assert body["notification_enabled"] is True


async def test_update_preferences(client, auth_headers):
    resp = await client.put(
        "/api/v1/users/me/preferences",
        headers=auth_headers,
        json={
            "preferred_categories": ["technology", "science"],
            "dark_mode": True,
            "email_digest_frequency": "weekly",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["preferred_categories"] == ["technology", "science"]
    assert body["dark_mode"] is True
    assert body["email_digest_frequency"] == "weekly"


async def test_get_preferences_persisted(client, auth_headers):
    await client.put(
        "/api/v1/users/me/preferences",
        headers=auth_headers,
        json={"preferred_sources": ["BBC"]},
    )
    resp = await client.get("/api/v1/users/me/preferences", headers=auth_headers)
    assert resp.json()["preferred_sources"] == ["BBC"]


async def test_recommendations_endpoint(client, auth_headers, article_fixture):
    resp = await client.get("/api/v1/recommendations", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert body[0]["title"] == "AI Breakthrough in Health"
    assert body[0]["category_name"] == "Technology"


async def test_recommendations_requires_auth(client):
    resp = await client.get("/api/v1/recommendations")
    assert resp.status_code == 401
