from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_user_preference_repo, get_user_repo
from app.models.user import User
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserPreferencesResponse,
    UserPreferencesUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
    preference_repo: UserPreferenceRepository = Depends(get_user_preference_repo),
):
    service = UserService(user_repo, preference_repo)
    return await service.get_profile(current_user.id)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
    preference_repo: UserPreferenceRepository = Depends(get_user_preference_repo),
):
    service = UserService(user_repo, preference_repo)
    return await service.update_profile(current_user.id, request.model_dump(exclude_none=True))


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
    preference_repo: UserPreferenceRepository = Depends(get_user_preference_repo),
):
    service = UserService(user_repo, preference_repo)
    return await service.get_preferences(current_user.id)


@router.put("/me/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    request: UserPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
    preference_repo: UserPreferenceRepository = Depends(get_user_preference_repo),
):
    service = UserService(user_repo, preference_repo)
    return await service.update_preferences(current_user.id, request.model_dump(exclude_none=True))
