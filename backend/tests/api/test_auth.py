"""API tests for the authentication endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@user.com",
            "username": "newuser",
            "password": "NewPass123!",
            "full_name": "New User",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@user.com"
    assert body["username"] == "newuser"
    assert "password" not in body


@pytest.mark.asyncio
async def test_register_duplicate_email(client, regular_user):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": regular_user["email"],
            "username": "anotheruser",
            "password": "NewPass123!",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_username(client, regular_user):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "different@user.com",
            "username": regular_user["username"],
            "password": "NewPass123!",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "username": "u1", "password": "x"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, regular_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": regular_user["password"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, regular_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": "WrongPass!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@user.com", "password": "Whatever1!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_flow(client, regular_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": regular_user["password"]},
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(client, regular_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": regular_user["password"]},
    )
    access_token = login.json()["access_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401
