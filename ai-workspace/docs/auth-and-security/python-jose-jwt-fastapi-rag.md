# python-jose + FastAPI JWT Authentication — RAG Reference Document

<!-- RAG_METADATA
topic: authentication, jwt, security
library: python-jose, fastapi
version: python-jose 3.4.0, fastapi 0.135.3
python_min: 3.9
tags: jwt, authentication, bearer-token, python-jose, fastapi, httpbearer, role-based-access
use_case: phase-7-subtask-3-auth-and-security
-->

## Overview

**python-jose** is an open-source JOSE (JSON Object Signing and Encryption) implementation for Python. It provides JWT encode/decode with support for HS256, RS256, and other algorithms.

**Install**: `pip install "python-jose[cryptography]"`

The `[cryptography]` extra installs the `cryptography` backend (recommended over `pycryptodome`).

---

## JWT Reserved Claims

| Claim | Name | Format | Usage |
|---|---|---|---|
| `exp` | Expiration | int (Unix timestamp) | Token is invalid after this time |
| `nbf` | Not Before | int (Unix timestamp) | Token is invalid before this time |
| `iss` | Issuer | str | Principal that issued the JWT |
| `aud` | Audience | str or list[str] | Intended recipient |
| `iat` | Issued At | int (Unix timestamp) | Time the JWT was issued |
| `sub` | Subject | str | User identifier (email, user ID) |

---

## Core API

### `jwt.encode(claims, key, algorithm)`

```python
from jose import jwt

token = jwt.encode(
    {"sub": "user@example.com", "exp": 1234567890},
    "secret-key",
    algorithm="HS256",
)
# Returns: str (the JWT token)
```

### `jwt.decode(token, key, algorithms)`

```python
from jose import jwt, JWTError

try:
    payload = jwt.decode(
        token,
        "secret-key",
        algorithms=["HS256"],
    )
    # payload is a dict: {"sub": "user@example.com", "exp": 1234567890, ...}
except JWTError as e:
    # Token is invalid, expired, or tampered
    raise HTTPException(status_code=401, detail=str(e))
```

**Important**: `algorithms` is a **list** — always pass `["HS256"]`, not `"HS256"`.

---

## Complete JWT Implementation for FastAPI

```python
"""JWT authentication utilities."""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# Configuration — read from environment
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

# HTTPBearer extracts the token from "Authorization: Bearer <token>" header
security = HTTPBearer()


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str          # user ID or email
    exp: datetime
    iat: datetime
    role: str = "viewer"   # viewer | editor | admin


class TokenResponse(BaseModel):
    """Response from the login endpoint."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds


def create_access_token(
    subject: str,
    role: str = "viewer",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
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
    """Decode and validate a JWT token.
    
    Raises HTTPException 401 if token is invalid or expired.
    """
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
    """FastAPI dependency — extracts and validates JWT from Authorization header."""
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
```

---

## Login Endpoint

```python
"""Auth router — login and token management."""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.auth.jwt import TokenResponse, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple user store — replace with database lookup in production
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

    token = create_access_token(subject=request.email, role=user["role"])
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRY_HOURS * 3600,
    )
```

---

## Protecting Routes

```python
from fastapi import Depends
from src.auth.jwt import get_current_user, require_admin, require_editor

# Require any authenticated user
@router.get("/jobs", dependencies=[Depends(get_current_user)])
async def list_jobs():
    ...

# Require editor or admin
@router.post("/jobs/{job_id}/embed", dependencies=[Depends(require_editor)])
async def start_embedding(job_id: str):
    ...

# Require admin
@router.delete("/jobs/{job_id}", dependencies=[Depends(require_admin)])
async def delete_job(job_id: str):
    ...

# Access user info in handler
@router.get("/me")
async def get_me(user: TokenPayload = Depends(get_current_user)):
    return {"email": user.sub, "role": user.role}
```

---

## Register in `main.py`

```python
from src.routers.auth import router as auth_router

app.include_router(auth_router, prefix="/api/v1")
# Creates: POST /api/v1/auth/login
```

---

## Testing JWT Auth

```bash
# Get a token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme"}'
# → {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400}

# Use the token
curl http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer eyJ..."

# Without token → 401
curl http://localhost:8000/api/v1/jobs
# → {"detail": "Not authenticated"}
```

---

## Algorithms

| Algorithm | Type | Key | Use Case |
|---|---|---|---|
| `HS256` | HMAC-SHA256 | Shared secret string | Single-service, simple setup |
| `RS256` | RSA-SHA256 | RSA private/public key pair | Multi-service, key rotation |
| `ES256` | ECDSA-SHA256 | EC private/public key pair | Multi-service, smaller tokens |

**For this project**: `HS256` with a strong random secret is sufficient. Use `RS256` if multiple services need to verify tokens independently.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `"CHANGE-ME-IN-PRODUCTION"` | HMAC signing secret — must be changed in production |
| `JWT_EXPIRY_HOURS` | `24` | Token lifetime in hours |
| `ADMIN_EMAIL` | `"admin@example.com"` | Admin user email |
| `ADMIN_PASSWORD` | `"changeme"` | Admin user password — must be changed |

**Production secret generation**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
# → e.g. "a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"
```

---

## Common Pitfalls

1. **`algorithms` must be a list** — `jwt.decode(token, key, algorithms=["HS256"])` not `algorithms="HS256"`. Passing a string causes a `JWTError`.
2. **`JWT_SECRET` in production** — Never use the default `"CHANGE-ME-IN-PRODUCTION"`. Generate a strong random secret.
3. **`datetime` vs `int` for `exp`** — python-jose accepts both `datetime` objects and Unix timestamps for `exp`. Using `datetime.now(timezone.utc)` is cleaner.
4. **`HTTPBearer` returns 403 not 401** — When no `Authorization` header is present, `HTTPBearer` raises HTTP 403 by default. To get 401, set `auto_error=False` and handle manually.
5. **Token in `Authorization` header** — Format is `Authorization: Bearer <token>`. The `HTTPBearer` dependency extracts the token automatically.
6. **`JWTError` catches all jose errors** — Expired tokens, invalid signatures, and malformed tokens all raise `JWTError`.

---

## Sources
- https://python-jose.readthedocs.io/en/latest/ (python-jose docs)
- https://python-jose.readthedocs.io/en/latest/jwt/index.html (JWT claims)
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ (FastAPI JWT guide)
- https://pypi.org/project/python-jose/ (v3.4.0)
