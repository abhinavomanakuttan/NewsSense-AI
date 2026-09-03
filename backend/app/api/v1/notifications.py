from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_notification_repo
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationListResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
):
    service = NotificationService(notification_repo)
    return await service.get_notifications(current_user.id, skip, limit)


@router.put("/{notification_id}/read", response_model=bool)
async def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
):
    service = NotificationService(notification_repo)
    return await service.mark_as_read(notification_id, current_user.id)


@router.put("/read-all", response_model=int)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
):
    service = NotificationService(notification_repo)
    return await service.mark_all_as_read(current_user.id)
