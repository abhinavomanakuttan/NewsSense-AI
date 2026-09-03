import pytest

from app.core.security import hash_password
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_producer import ArticleNotificationProducer


@pytest.fixture
async def interested_user(db_session) -> dict:
    user = await UserRepository(db_session).create(
        email="fan@test.com",
        username="fan",
        hashed_password=hash_password("Pass123!"),
        full_name="Fan",
    )
    await UserPreferenceRepository(db_session).create(
        user_id=user.id,
        preferred_categories=["Technology"],
        notification_enabled=True,
    )
    await db_session.flush()
    return {"id": user.id, "email": user.email}


@pytest.fixture
async def disabled_user(db_session) -> dict:
    user = await UserRepository(db_session).create(
        email="muted@test.com",
        username="muted",
        hashed_password=hash_password("Pass123!"),
        full_name="Muted",
    )
    await UserPreferenceRepository(db_session).create(
        user_id=user.id,
        preferred_categories=["Technology"],
        notification_enabled=False,
    )
    await db_session.flush()
    return {"id": user.id, "email": user.email}


@pytest.fixture
async def other_category_user(db_session) -> dict:
    user = await UserRepository(db_session).create(
        email="sportsfan@test.com",
        username="sportsfan",
        hashed_password=hash_password("Pass123!"),
        full_name="Sports Fan",
    )
    await UserPreferenceRepository(db_session).create(
        user_id=user.id,
        preferred_categories=["Sports"],
        notification_enabled=True,
    )
    await db_session.flush()
    return {"id": user.id, "email": user.email}


@pytest.mark.asyncio
async def test_producer_notifies_only_matching_enabled_users(
    db_session,
    article_fixture,
    interested_user,
    disabled_user,
    other_category_user,
    monkeypatch,
):
    dispatched: list[str] = []

    async def fake_publish(user_id, payload):
        dispatched.append(user_id)

    from app.services.notification_dispatcher import notification_dispatcher

    monkeypatch.setattr(notification_dispatcher, "publish", fake_publish)

    producer = ArticleNotificationProducer(session=db_session)
    created = await producer.notify_for_article(article_fixture["id"])

    assert created == 1
    assert dispatched == [str(interested_user["id"])]

    repo = NotificationRepository(db_session)
    notifications = await repo.get_user_notifications(interested_user["id"], limit=10)
    assert len(notifications) == 1
    assert notifications[0].title == "New article: AI Breakthrough in Health"
    assert notifications[0].notification_type == "new_article"
    assert notifications[0].reference_type == "article"
    assert notifications[0].reference_id == str(article_fixture["id"])

    assert (await repo.get_user_notifications(disabled_user["id"], limit=10)) == []
    assert (await repo.get_user_notifications(other_category_user["id"], limit=10)) == []


@pytest.mark.asyncio
async def test_producer_skips_missing_or_uncategorized_article(
    db_session, article_fixture, monkeypatch
):
    from app.services.notification_dispatcher import notification_dispatcher

    calls = []

    async def fake_publish(user_id, payload):
        calls.append(user_id)

    monkeypatch.setattr(notification_dispatcher, "publish", fake_publish)

    producer = ArticleNotificationProducer(session=db_session)

    created = await producer.notify_for_article("00000000-0000-0000-0000-000000000000")
    assert created == 0
    assert calls == []

    from sqlalchemy import update

    from app.models.article import Article

    await db_session.execute(
        update(Article).where(Article.id == article_fixture["id"]).values(category_id=None)
    )
    await db_session.flush()

    created = await producer.notify_for_article(article_fixture["id"])
    assert created == 0
