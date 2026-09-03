from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    get_article_repo,
    get_bookmark_repo,
    get_current_user,
    get_reading_history_repo,
    get_user_preference_repo,
)
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_history_repository import ReadingHistoryRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=list[RecommendationResponse])
async def get_recommendations(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    article_repo: ArticleRepository = Depends(get_article_repo),
    preference_repo: UserPreferenceRepository = Depends(get_user_preference_repo),
    reading_history_repo: ReadingHistoryRepository = Depends(get_reading_history_repo),
    bookmark_repo: BookmarkRepository = Depends(get_bookmark_repo),
):
    service = RecommendationService(
        article_repo,
        preference_repo,
        reading_history_repo,
        bookmark_repo=bookmark_repo,
    )
    return await service.get_recommendations(current_user.id, limit)
