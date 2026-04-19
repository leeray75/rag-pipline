# Phase 7, Subtask 3 — Authentication & Security

> **Phase**: Phase 7 — MCP Server, Observability & Production Hardening
> **Prerequisites**: Phase 6 complete; Phase 7 Subtasks 1-2 complete (dependencies installed, MCP server working via Streamable HTTP at `POST /mcp`, observability configured)
> **Scope**: JWT authentication with python-jose, API key management, login endpoint, SSRF prevention, rate limiting with slowapi, security middleware

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| python-jose | 3.4.0 | `pip install "python-jose[cryptography]"` |
| slowapi | 0.1.9 | `pip install slowapi` |
| FastAPI | 0.135.3 | Already installed |
| Pydantic | 2.13.0 | Already installed |

> All Python packages were added to `pyproject.toml` in Subtask 1.

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Create | `rag-pipeline/apps/api/src/auth/__init__.py` |
| Create | `rag-pipeline/apps/api/src/auth/jwt.py` |
| Create | `rag-pipeline/apps/api/src/routers/auth.py` |
| Create | `rag-pipeline/apps/api/src/rate_limit.py` |
| Create | `rag-pipeline/apps/api/src/security/__init__.py` |
| Create | `rag-pipeline/apps/api/src/security/url_validator.py` |
| Modify | `rag-pipeline/apps/api/src/main.py` (register auth router, rate limiter) |

---

## Step 1: Create JWT Authentication

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Create `src/auth/__init__.py`

```python
"""Authentication package — JWT-based auth for the dashboard and API."""
```

### 1.2 Create `src/auth/jwt.py`

```python
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
```

---

## Step 2: Create Auth Router

### 2.1 Create `src/routers/auth.py`

```python
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
```

### 2.2 Register auth router in `src/main.py`

```python
from src.routers.auth import router as auth_router

app.include_router(auth_router, prefix="/api/v1")
```

### 2.3 Protect sensitive routes

To protect a route, add the dependency:

```python
from src.auth.jwt import get_current_user, require_admin, require_editor
from fastapi import Depends

@router.post("/jobs/{job_id}/embed", dependencies=[Depends(require_editor)])
async def start_embedding(...):
    ...
```

---

## Step 3: Add Rate Limiting

### 3.1 Create `src/rate_limit.py`

```python
"""Rate limiting configuration using slowapi."""

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

# Default: 100 requests per minute per IP
DEFAULT_LIMIT = os.getenv("RATE_LIMIT", "100/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_LIMIT])


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": exc.retry_after,
        },
    )
```

### 3.2 Initialize in `src/main.py`

```python
from slowapi.errors import RateLimitExceeded
from src.rate_limit import limiter, rate_limit_exceeded_handler

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

---

## Step 4: Implement SSRF Prevention

### 4.1 Create `src/security/__init__.py`

```python
"""Security package — URL validation, SSRF prevention."""
```

### 4.2 Create `src/security/url_validator.py`

```python
"""URL validation — prevents SSRF attacks by blocking private IP ranges."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# RFC 1918 and other private ranges
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


class SSRFError(Exception):
    """Raised when a URL resolves to a blocked IP address."""


def validate_url(url: str) -> str:
    """Validate a URL is safe to fetch.

    Checks:
    1. Scheme is http or https.
    2. Hostname is not empty.
    3. Resolved IP is not in a private/internal range.

    Returns the validated URL.
    Raises SSRFError if the URL is unsafe.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme: {parsed.scheme}")

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname")

    # Resolve hostname to IP
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFError(
                    f"URL resolves to blocked IP range: {ip} ({network})"
                )

    logger.debug("URL validated: %s", url)
    return url
```

---

## Step 5: Summary of `src/main.py` Changes for This Subtask

After completing this subtask, `src/main.py` should have these additions:

```python
# Auth router
from src.routers.auth import router as auth_router
app.include_router(auth_router, prefix="/api/v1")

# Rate limiting
from slowapi.errors import RateLimitExceeded
from src.rate_limit import limiter, rate_limit_exceeded_handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | JWT auth protects sensitive endpoints | `curl -X POST /api/v1/ingest/jobs/{id}/embed` without token → 401 |
| 2 | `POST /api/v1/auth/login` returns a JWT | `curl -X POST /api/v1/auth/login -d '{"email":"admin@example.com","password":"changeme"}'` → token |
| 3 | Rate limiting returns 429 when exceeded | Send >100 requests/min → 429 response |
| 4 | SSRF prevention blocks private IPs | `validate_url("http://192.168.1.1/secret")` raises `SSRFError` |
| 5 | SSRF prevention blocks localhost | `validate_url("http://127.0.0.1/admin")` raises `SSRFError` |
| 6 | SSRF prevention blocks non-HTTP schemes | `validate_url("ftp://example.com/file")` raises `SSRFError` |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-7-subtask-3-auth-and-security-summary.md`

The summary report must include:
- **Subtask**: Phase 7, Subtask 3 — Authentication & Security
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items