"""Auth API — login and token management."""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auth.jwt import TokenResponse, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple user store — replace with database in production
USERS: dict[str, dict] = {
    os.getenv("ADMIN_EMAIL", "admin@example.com"): {
        "password": os.getenv("ADMIN_PASSWORD", "changeme"),
        "role": "admin",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate and return a JWT access token."""
    user = USERS.get(request.email)
    if not user or user["password"] != request.password:
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(
        subject=request.email,
        role=user["role"],
    )
    return TokenResponse(
        access_token=token,
        expires_in=24 * 3600,
    )
