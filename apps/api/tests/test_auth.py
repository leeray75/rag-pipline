"""Tests for JWT authentication."""

import pytest
from datetime import timedelta

from src.auth.jwt import create_access_token, decode_token, TokenPayload


def test_create_and_decode_token():
    """Token can be created and decoded."""
    token = create_access_token(subject="test@example.com", role="admin")
    payload = decode_token(token)
    assert payload.sub == "test@example.com"
    assert payload.role == "admin"


def test_expired_token():
    """Expired token raises HTTPException."""
    from fastapi import HTTPException

    token = create_access_token(
        subject="test@example.com",
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401


def test_invalid_token():
    """Garbage token raises HTTPException."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        decode_token("not.a.valid.token")
    assert exc_info.value.status_code == 401
