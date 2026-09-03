"""Unit tests for the security core module (hashing + JWT)."""

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("SuperSecret123!")
        assert hashed != "SuperSecret123!"
        assert verify_password("SuperSecret123!", hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("SuperSecret123!")
        assert not verify_password("WrongPassword", hashed)

    def test_hash_is_unique_per_call(self):
        assert hash_password("SamePass") != hash_password("SamePass")


class TestJWT:
    def test_access_token_roundtrip(self):
        token = create_access_token(data={"sub": "user-123", "role": "user"})
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        token = create_refresh_token(data={"sub": "user-123"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            decode_token("not-a-real-token")

    def test_access_and_refresh_are_different(self):
        access = create_access_token(data={"sub": "u1"})
        refresh = create_refresh_token(data={"sub": "u1"})
        assert access != refresh
