import pytest

from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_create_notification_persists_and_dispatches(db_session, regular_user, monkeypatch):
    dispatched: list[tuple[str, dict]] = []

    async def fake_publish(user_id, payload):
        dispatched.append((user_id, payload))

    from app.services.notification_dispatcher import notification_dispatcher

    monkeypatch.setattr(notification_dispatcher, "publish", fake_publish)

    service = NotificationService(NotificationRepository(db_session))
    notification = await service.create_notification(
        user_id=regular_user["id"],
        title="Welcome",
        body="Thanks for joining",
        notification_type="welcome",
    )

    assert notification.title == "Welcome"
    assert len(dispatched) == 1
    user_id, payload = dispatched[0]
    assert user_id == str(regular_user["id"])
    assert payload["title"] == "Welcome"
    assert payload["id"] == str(notification.id)
    assert payload["notification_type"] == "welcome"


@pytest.mark.asyncio
async def test_create_notification_tolerates_dispatcher_failure(
    db_session, regular_user, monkeypatch
):
    async def boom(user_id, payload):
        raise RuntimeError("dispatcher down")

    from app.services.notification_dispatcher import notification_dispatcher

    monkeypatch.setattr(notification_dispatcher, "publish", boom)

    service = NotificationService(NotificationRepository(db_session))
    notification = await service.create_notification(
        user_id=regular_user["id"],
        title="Still saved",
        body="Even if push fails",
        notification_type="test",
    )

    assert notification.id is not None
    listed = await service.get_notifications(regular_user["id"])
    assert len(listed.notifications) >= 1
