"""End-to-end and unit verification tests for NewsSense / SmartFeed authentication flow."""

from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import async_session_factory
from app.models.user import User
from app.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_complete_auth_flow_e2e():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        rand_id = uuid4().hex[:8]
        email = f"auth_{rand_id}@example.com"
        username = f"auth_{rand_id}"
        password = "SecurePassword123!"

        # 1. New user registration
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": password,
                "full_name": "Auth Flow Test User",
            },
        )
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert reg_data["email"] == email
        assert reg_data["username"] == username
        assert "password" not in reg_data

        # 2. Duplicate email rejection
        dup_email_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"diff_{rand_id}",
                "password": password,
            },
        )
        assert dup_email_res.status_code == 409
        assert "Email already registered" in dup_email_res.json()["detail"]

        # 3. Duplicate username rejection
        dup_user_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"diff_{rand_id}@example.com",
                "username": username,
                "password": password,
            },
        )
        assert dup_user_res.status_code == 409
        assert "Username already taken" in dup_user_res.json()["detail"]

        # 4. Invalid credentials login
        bad_login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword999!"},
        )
        assert bad_login_res.status_code == 401
        assert "Invalid email or password" in bad_login_res.json()["detail"]

        # 5. Successful login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]

        # 6. Protected route without auth (401)
        unauth_res = await client.get("/api/v1/users/me")
        assert unauth_res.status_code == 401

        # 7. Protected route with auth (200)
        auth_res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert auth_res.status_code == 200
        profile = auth_res.json()
        assert profile["email"] == email
        assert profile["username"] == username
        assert "hashed_password" not in profile

        # 8. Token refresh
        refresh_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_res.status_code == 200
        new_token_data = refresh_res.json()
        assert "access_token" in new_token_data
