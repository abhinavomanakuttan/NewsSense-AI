import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.main import app
from app.repositories.article_repository import ArticleRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.user_repository import UserRepository

TEST_DATABASE_URL = settings.database_url + "_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> dict:
    repo = UserRepository(db_session)
    user = await repo.create(
        email="admin@test.com",
        username="admin",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Test Admin",
        role="admin",
        is_verified=True,
    )
    await db_session.commit()
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "password": "AdminPass123!",
    }


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> dict:
    repo = UserRepository(db_session)
    user = await repo.create(
        email="user@test.com",
        username="regular",
        hashed_password=hash_password("UserPass123!"),
        full_name="Test User",
    )
    await db_session.commit()
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "password": "UserPass123!",
    }


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, regular_user: dict) -> dict:
    """Register+login a fresh user and return their Authorization header."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"auth-{uuid4().hex[:8]}@test.com",
            "username": f"user-{uuid4().hex[:8]}",
            "password": "AuthPass123!",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": regular_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, admin_user: dict) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user["email"], "password": admin_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def source_fixture(db_session: AsyncSession) -> dict:
    repo = SourceRepository(db_session)
    source = await repo.create(
        name="Test News",
        url="https://testnews.com",
        feed_url="https://testnews.com/rss",
        source_type="rss",
        language="en",
        country="us",
        reputation_score=0.8,
    )
    await db_session.commit()
    return {"id": source.id, "name": source.name}


@pytest_asyncio.fixture
async def category_fixture(db_session: AsyncSession) -> dict:
    repo = CategoryRepository(db_session)
    category = await repo.create(
        name="Technology",
        slug="technology",
        description="Tech news",
    )
    await db_session.commit()
    return {"id": category.id, "name": category.name, "slug": category.slug}


@pytest_asyncio.fixture
async def article_fixture(
    db_session: AsyncSession, source_fixture: dict, category_fixture: dict
) -> dict:
    repo = ArticleRepository(db_session)
    article = await repo.create(
        title="AI Breakthrough in Health",
        slug="ai-breakthrough-health",
        url="https://testnews.com/ai-health",
        content="Scientists announced a breakthrough in AI-assisted diagnostics.",
        summary="AI helps doctors diagnose faster.",
        content_hash="test-hash-1",
        source_id=source_fixture["id"],
        category_id=category_fixture["id"],
        published_at="2026-07-30T10:00:00",
    )
    await db_session.commit()
    return {"id": article.id, "slug": article.slug, "title": article.title}
