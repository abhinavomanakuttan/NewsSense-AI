from uuid import UUID

from app.core.exceptions import NotFoundError
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserPreferencesResponse, UserResponse
from app.services.recommendation_service import invalidate_user_recommendations


class UserService:
    def __init__(self, user_repo: UserRepository, preference_repo: UserPreferenceRepository):
        self.user_repo = user_repo
        self.preference_repo = preference_repo

    async def get_profile(self, user_id: UUID) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return UserResponse.model_validate(user)

    async def update_profile(self, user_id: UUID, data: dict) -> UserResponse:
        user = await self.user_repo.update(user_id, **data)
        if not user:
            raise NotFoundError("User not found")
        return UserResponse.model_validate(user)

    async def get_preferences(self, user_id: UUID) -> UserPreferencesResponse:
        prefs = await self.preference_repo.get_or_create(user_id)
        return UserPreferencesResponse.model_validate(prefs)

    async def update_preferences(self, user_id: UUID, data: dict) -> UserPreferencesResponse:
        prefs = await self.preference_repo.get_or_create(user_id)
        for key, value in data.items():
            if hasattr(prefs, key) and value is not None:
                setattr(prefs, key, value)
        await self.preference_repo.db.flush()
        await self.preference_repo.db.refresh(prefs)
        await invalidate_user_recommendations(user_id)
        return UserPreferencesResponse.model_validate(prefs)
