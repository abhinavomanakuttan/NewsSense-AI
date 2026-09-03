"""DB-backed tests for the notification repository (list, unread, mark read)."""

from app.repositories.notification_repository import NotificationRepository


async def _create(repo, user_id, title="Hello", is_read=False, **overrides):
    return await repo.create(
        user_id=user_id,
        title=title,
        notification_type="article",
        is_read=is_read,
        **overrides,
    )


async def test_get_user_notifications_ordered(db_session, regular_user, article_fixture):
    repo = NotificationRepository(db_session)
    await _create(repo, regular_user["id"], title="First")
    await _create(repo, regular_user["id"], title="Second")
    await db_session.flush()

    items = await repo.get_user_notifications(regular_user["id"])
    assert len(items) == 2
    assert items[0].title == "Second"  # newest first


async def test_get_unread_count(db_session, regular_user, article_fixture):
    repo = NotificationRepository(db_session)
    await _create(repo, regular_user["id"], title="unread 1")
    await _create(repo, regular_user["id"], title="unread 2")
    await _create(repo, regular_user["id"], title="read", is_read=True)
    await db_session.flush()

    assert await repo.get_unread_count(regular_user["id"]) == 2
    assert await repo.get_unread_count(article_fixture["id"]) == 0


async def test_mark_as_read(db_session, regular_user):
    repo = NotificationRepository(db_session)
    note = await _create(repo, regular_user["id"])
    await db_session.flush()

    assert await repo.mark_as_read(note.id, regular_user["id"]) is True
    assert await repo.get_unread_count(regular_user["id"]) == 0


async def test_mark_as_read_wrong_user(db_session, regular_user, article_fixture):
    repo = NotificationRepository(db_session)
    note = await _create(repo, regular_user["id"])
    await db_session.flush()

    other_id = article_fixture["id"]
    assert await repo.mark_as_read(note.id, other_id) is False
    assert await repo.get_unread_count(regular_user["id"]) == 1


async def test_mark_all_as_read(db_session, regular_user):
    repo = NotificationRepository(db_session)
    await _create(repo, regular_user["id"], title="a")
    await _create(repo, regular_user["id"], title="b")
    await _create(repo, regular_user["id"], title="c", is_read=True)
    await db_session.flush()

    updated = await repo.mark_all_as_read(regular_user["id"])
    assert updated == 2
    assert await repo.get_unread_count(regular_user["id"]) == 0


async def test_pagination(db_session, regular_user):
    repo = NotificationRepository(db_session)
    for i in range(5):
        await _create(repo, regular_user["id"], title=f"n{i}")
    await db_session.flush()

    first_page = await repo.get_user_notifications(regular_user["id"], skip=0, limit=2)
    assert len(first_page) == 2
    second_page = await repo.get_user_notifications(regular_user["id"], skip=2, limit=2)
    assert len(second_page) == 2
    assert first_page[0].id != second_page[0].id
