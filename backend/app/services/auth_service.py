from uuid import UUID

from app.core.exceptions import DuplicateError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, request: RegisterRequest) -> dict:
        existing_email = await self.user_repo.get_by_email(request.email)
        if existing_email:
            raise DuplicateError("Email already registered")

        existing_username = await self.user_repo.get_by_username(request.username)
        if existing_username:
            raise DuplicateError("Username already taken")

        user = await self.user_repo.create(
            email=request.email,
            username=request.username,
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "message": "User registered successfully",
        }

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(request.email)
        if not user or not verify_password(request.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
        refresh_token = create_refresh_token(data={"sub": str(user.id), "role": user.role})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        new_access = create_access_token(data={"sub": str(user.id), "role": user.role})
        new_refresh = create_refresh_token(data={"sub": str(user.id), "role": user.role})

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
        )
