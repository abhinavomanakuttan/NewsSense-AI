from fastapi import APIRouter, Depends

from app.core.dependencies import get_user_repo
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(request: RegisterRequest, user_repo: UserRepository = Depends(get_user_repo)):
    service = AuthService(user_repo)
    return await service.register(request)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, user_repo: UserRepository = Depends(get_user_repo)):
    service = AuthService(user_repo)
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: TokenRefreshRequest, user_repo: UserRepository = Depends(get_user_repo)):
    service = AuthService(user_repo)
    return await service.refresh_token(request.refresh_token)
