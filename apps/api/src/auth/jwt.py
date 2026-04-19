"""JWT authentication utilities."""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

security = HTTPBearer()


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user ID or email
    exp: datetime
    iat: datetime
    role: str = "viewer"  # viewer | editor | admin


class TokenResponse(BaseModel):
    """Response from the login endpoint."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


def create_access_token(
    subject: str,
    role: str = "viewer",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=JWT_EXPIRY_HOURS))

    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """FastAPI dependency — extracts and validates the JWT from the Authorization header."""
    return decode_token(credentials.credentials)


async def require_admin(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """FastAPI dependency — requires admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


async def require_editor(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """FastAPI dependency — requires editor or admin role."""
    if user.role not in ("editor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or admin role required",
        )
    return user
