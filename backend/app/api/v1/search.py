from fastapi import APIRouter, Depends

from app.core.dependencies import get_article_repo, get_optional_user, get_search_history_repo
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.search_history_repository import SearchHistoryRepository
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    article_repo: ArticleRepository = Depends(get_article_repo),
    search_history_repo: SearchHistoryRepository = Depends(get_search_history_repo),
    user: User | None = Depends(get_optional_user),
):
    service = SearchService(article_repo, search_history_repo)
    return await service.search(request, str(user.id) if user else None)
