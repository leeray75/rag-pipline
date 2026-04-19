# Auth & Security Integration Overview — RAG Reference Document

<!-- RAG_METADATA
topic: authentication, security, integration
stack: python-jose + slowapi + fastapi + ssrf-prevention
version: phase-7-subtask-3
tags: jwt, rate-limiting, ssrf, fastapi, security, main.py, open-source
use_case: phase-7-subtask-3-auth-and-security
-->

## Overview

This document covers the integration of all authentication and security components for Phase 7 Subtask 3. **All tools are open-source and free.**

| Component | Library | Version | Purpose |
|---|---|---|---|
| JWT Authentication | `python-jose[cryptography]` | 3.4.0 | Bearer token auth for API endpoints |
| Rate Limiting | `slowapi` | 0.1.9 | IP-based request throttling (429 responses) |
| SSRF Prevention | Python stdlib only | 3.9+ | Block requests to private/internal IPs |

---

## `main.py` Integration Order

```python
# ============================================================
# 1. LOGGING (Subtask 2)
# ============================================================
from src.logging_config import configure_logging
configure_logging()

# ============================================================
# 2. FASTAPI APP CREATION
# ============================================================
from fastapi import FastAPI
app = FastAPI(title="RAG Pipeline API", version="1.0.0")

# ============================================================
# 3. RATE LIMITER — Must be set on app.state before routers
# ============================================================
from slowapi.errors import RateLimitExceeded
from src.rate_limit import limiter, rate_limit_exceeded_handler

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ============================================================
# 4. OPENTELEMETRY (Subtask 2)
# ============================================================
from src.telemetry import configure_telemetry
configure_telemetry(app)

# ============================================================
# 5. PROMETHEUS METRICS (Subtask 2)
# ============================================================
from src.metrics import configure_metrics
configure_metrics(app)

# ============================================================
# 6. ROUTERS
# ============================================================
from src.routers.health import router as health_router
from src.routers.auth import router as auth_router
from src.routers.jobs import router as jobs_router
from src.mcp.http_transport import router as mcp_router

app.include_router(health_router)                    # /health, /health/ready
app.include_router(auth_router, prefix="/api/v1")    # /api/v1/auth/login
app.include_router(jobs_router, prefix="/api/v1")    # /api/v1/jobs/...
app.include_router(mcp_router)                       # POST /mcp
```

---

## File Inventory

| File | Purpose |
|---|---|
| `apps/api/src/auth/__init__.py` | Auth package marker |
| `apps/api/src/auth/jwt.py` | JWT encode/decode, FastAPI dependencies |
| `apps/api/src/routers/auth.py` | `POST /api/v1/auth/login` endpoint |
| `apps/api/src/rate_limit.py` | slowapi Limiter + custom 429 handler |
| `apps/api/src/security/__init__.py` | Security package marker |
| `apps/api/src/security/url_validator.py` | SSRF prevention via IP range blocking |

---

## Authentication Flow

```
Client
  │
  ├── POST /api/v1/auth/login
  │   {"email": "admin@example.com", "password": "changeme"}
  │
  ▼
Auth Router
  │
  ├── Lookup user in USERS dict (or DB)
  ├── Verify password
  ├── create_access_token(subject=email, role="admin")
  │   → jwt.encode({"sub": email, "role": "admin", "exp": ...}, JWT_SECRET, "HS256")
  │
  ▼
Response: {"access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400}

Client
  │
  ├── GET /api/v1/jobs
  │   Authorization: Bearer eyJ...
  │
  ▼
FastAPI HTTPBearer dependency
  │
  ├── Extract token from Authorization header
  ├── jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
  ├── Validate exp, iat claims
  ├── Return TokenPayload(sub=email, role="admin", ...)
  │
  ▼
Route handler receives user: TokenPayload
```

---

## Rate Limiting Flow

```
Client → POST /api/v1/auth/login (11th request in 1 minute)
  │
  ▼
slowapi middleware
  │
  ├── key_func(request) → client IP address
  ├── Check counter for this IP in memory/Redis
  ├── Counter > 10/minute limit
  │
  ▼
HTTP 429 Too Many Requests
{"error": "Rate limit exceeded", "detail": "10 per 1 minute", "retry_after": 42}
```

---

## SSRF Prevention Flow

```
Client → POST /api/v1/ingest {"url": "http://192.168.1.1/secret"}
  │
  ▼
validate_url("http://192.168.1.1/secret")
  │
  ├── urlparse → scheme="http", hostname="192.168.1.1"
  ├── socket.getaddrinfo("192.168.1.1", None) → [("192.168.1.1", ...)]
  ├── ipaddress.ip_address("192.168.1.1") in ip_network("192.168.0.0/16") → True
  │
  ▼
SSRFError("URL resolves to blocked IP range: 192.168.1.1 is in 192.168.0.0/16")
  │
  ▼
HTTP 400 Bad Request {"detail": "URL resolves to blocked IP range: ..."}
```

---

## Environment Variables

```env
# JWT Authentication
JWT_SECRET=CHANGE-ME-IN-PRODUCTION   # Generate: python -c "import secrets; print(secrets.token_hex(32))"
JWT_EXPIRY_HOURS=24
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme              # Change in production

# Rate Limiting
RATE_LIMIT=100/minute                # Default limit for all routes
```

---

## Role-Based Access Control

| Role | Permissions |
|---|---|
| `viewer` | Read-only: list jobs, view documents, search |
| `editor` | Read + write: create jobs, trigger embedding |
| `admin` | Full access: all operations including delete |

```python
# Dependency usage
@router.get("/jobs")
async def list_jobs(user: TokenPayload = Depends(get_current_user)):
    # Any authenticated user

@router.post("/jobs/{id}/embed", dependencies=[Depends(require_editor)])
async def embed():
    # editor or admin only

@router.delete("/jobs/{id}", dependencies=[Depends(require_admin)])
async def delete():
    # admin only
```

---

## Security Checklist

| # | Check | Verify |
|---|---|---|
| 1 | JWT auth protects sensitive endpoints | `curl /api/v1/jobs` without token → 401 |
| 2 | Login returns JWT | `POST /api/v1/auth/login` → `{"access_token": "eyJ..."}` |
| 3 | Rate limiting returns 429 | Send >100 requests/min → 429 |
| 4 | SSRF blocks private IPs | `validate_url("http://192.168.1.1")` → `SSRFError` |
| 5 | SSRF blocks localhost | `validate_url("http://127.0.0.1")` → `SSRFError` |
| 6 | SSRF blocks non-HTTP schemes | `validate_url("ftp://example.com")` → `SSRFError` |
| 7 | JWT_SECRET is not default | `JWT_SECRET != "CHANGE-ME-IN-PRODUCTION"` |

---

## Common Integration Pitfalls

1. **`app.state.limiter` before routers** — Set `app.state.limiter = limiter` before including any routers. The limiter middleware reads from `app.state`.
2. **slowapi decorator order** — `@router.get(...)` MUST be above `@limiter.limit(...)`. Wrong order silently fails.
3. **`request: Request` in rate-limited routes** — slowapi requires the `Request` object as an explicit parameter.
4. **`algorithms=["HS256"]` is a list** — `jwt.decode(token, key, algorithms=["HS256"])` — passing a string raises `JWTError`.
5. **`JWT_SECRET` in production** — Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. Never use the default.
6. **SSRF + redirects** — `validate_url()` validates the initial URL. HTTP redirects could still lead to internal IPs. Set `follow_redirects=False` in httpx.

---

## Sources
- https://python-jose.readthedocs.io/en/latest/ (python-jose)
- https://slowapi.readthedocs.io/en/latest/ (slowapi)
- https://fastapi.tiangolo.com/tutorial/security/ (FastAPI security)
- https://owasp.org/www-community/attacks/Server_Side_Request_Forgery (SSRF)
