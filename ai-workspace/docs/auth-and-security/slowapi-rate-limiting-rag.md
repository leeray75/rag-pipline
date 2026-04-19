# slowapi Rate Limiting — RAG Reference Document

<!-- RAG_METADATA
topic: rate-limiting, security, fastapi
library: slowapi
version: 0.1.9
python_min: 3.9
tags: rate-limiting, slowapi, fastapi, starlette, 429, ip-based, per-route
use_case: phase-7-subtask-3-auth-and-security
-->

## Overview

**slowapi** is an open-source rate limiting library for FastAPI and Starlette, adapted from flask-limiter. It uses the `limits` library under the hood and supports in-memory, Redis, and Memcached backends.

**Install**: `pip install slowapi`

**License**: MIT

---

## Quick Setup

```python
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create limiter — key_func determines how to identify clients
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

---

## Custom Rate Limit Exceeded Handler

```python
"""Rate limiting configuration using slowapi."""

import os
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

DEFAULT_LIMIT = os.getenv("RATE_LIMIT", "100/minute")

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_LIMIT])


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom handler — returns structured JSON for 429 responses."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": exc.retry_after,
        },
    )
```

---

## Initialize in `main.py`

```python
from slowapi.errors import RateLimitExceeded
from src.rate_limit import limiter, rate_limit_exceeded_handler

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

---

## Per-Route Rate Limiting

```python
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# CRITICAL: Route decorator MUST be above @limiter.limit decorator
@app.get("/api/v1/jobs")
@limiter.limit("100/minute")
async def list_jobs(request: Request):   # request: Request is REQUIRED
    return {"jobs": []}

@app.post("/api/v1/auth/login")
@limiter.limit("10/minute")             # Stricter limit for auth endpoints
async def login(request: Request, body: LoginRequest):
    ...

@app.post("/mcp")
@limiter.limit("200/minute")            # Higher limit for MCP endpoint
async def mcp_endpoint(request: Request):
    ...
```

**Critical rules**:
1. `@app.get(...)` / `@router.get(...)` MUST be above `@limiter.limit(...)` — wrong order silently fails
2. `request: Request` MUST be an explicit parameter in the function signature
3. If returning a dict (not a `Response` object), also add `response: Response` to get rate limit headers

---

## Rate Limit String Format

```
"<count>/<period>"
```

| Example | Meaning |
|---|---|
| `"100/minute"` | 100 requests per minute |
| `"1000/hour"` | 1000 requests per hour |
| `"10000/day"` | 10000 requests per day |
| `"5/second"` | 5 requests per second |
| `"10/minute;100/hour"` | 10/min AND 100/hour (multiple limits) |

---

## Default vs Per-Route Limits

```python
# Global default — applies to ALL routes unless overridden
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
)

# Per-route override — overrides the default for this route
@app.post("/api/v1/auth/login")
@limiter.limit("10/minute")   # Stricter than default
async def login(request: Request, ...):
    ...

# Exempt a route from rate limiting
@app.get("/health")
@limiter.exempt
async def health(request: Request):
    return {"status": "ok"}
```

---

## Key Functions

| Function | Identifies client by | Use case |
|---|---|---|
| `get_remote_address` | IP address | Default, IP-based limiting |
| Custom function | User ID, API key | Authenticated per-user limits |

### Custom key function (per-user limiting)

```python
from starlette.requests import Request

def get_user_id(request: Request) -> str:
    """Rate limit by authenticated user ID instead of IP."""
    # Extract from JWT token if available
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from src.auth.jwt import decode_token
            payload = decode_token(auth[7:])
            return payload.sub  # Use email/user ID as key
        except Exception:
            pass
    # Fall back to IP
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_id)
```

---

## Backends

| Backend | Config | Use case |
|---|---|---|
| Memory (default) | No config needed | Development, single-process |
| Redis | `storage_uri="redis://localhost:6379"` | Production, multi-process |
| Memcached | `storage_uri="memcached://localhost:11211"` | Production alternative |

```python
# Redis backend (recommended for production with multiple workers)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="redis://redis:6379",
)
```

---

## Response Headers

When `headers_enabled=True`, slowapi adds rate limit info to response headers:

```python
limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,   # Add X-RateLimit-* headers
)
```

Headers added:
- `X-RateLimit-Limit: 100`
- `X-RateLimit-Remaining: 87`
- `X-RateLimit-Reset: 1234567890`
- `Retry-After: 42` (on 429 responses)

---

## 429 Response

When rate limit is exceeded, slowapi returns HTTP 429:

```json
{
  "error": "Rate limit exceeded",
  "detail": "100 per 1 minute",
  "retry_after": 42
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT` | `"100/minute"` | Default rate limit string |

---

## Common Pitfalls

1. **Decorator order** — `@router.get(...)` MUST be above `@limiter.limit(...)`. Reversed order silently fails to apply the limit.
2. **`request: Request` required** — slowapi needs the `Request` object to extract the client key. If missing, it raises a `ValueError`.
3. **Memory backend in multi-worker** — The default memory backend is per-process. With `uvicorn --workers 4`, each worker has its own counter. Use Redis for accurate multi-worker limiting.
4. **`app.state.limiter`** — Must set `app.state.limiter = limiter` before adding the exception handler. The middleware reads from `app.state`.
5. **`_rate_limit_exceeded_handler` vs custom** — The built-in `_rate_limit_exceeded_handler` returns plain text. Use a custom handler for JSON responses.
6. **WebSocket not supported** — slowapi does not support WebSocket endpoints.

---

## Sources
- https://slowapi.readthedocs.io/en/latest/ (slowapi official docs)
- https://github.com/laurentS/slowapi (GitHub)
- https://pypi.org/project/slowapi/ (v0.1.9)
