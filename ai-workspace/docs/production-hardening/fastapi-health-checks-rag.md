# FastAPI Health Check Endpoints — RAG Reference Document

<!-- RAG_METADATA
topic: fastapi, health-checks, liveness, readiness, production
library: fastapi, starlette
version: fastapi 0.135.3
python_min: 3.9
tags: health-check, liveness, readiness, docker, kubernetes, fastapi, sqlalchemy, redis, qdrant
use_case: phase-7-subtask-4-production-hardening
-->

## Overview

Health check endpoints are required for:
- **Docker Compose** `healthcheck` directives
- **Kubernetes** liveness and readiness probes
- **Load balancers** to route traffic only to healthy instances

Two standard endpoints:
- `GET /health` — **Liveness**: Is the process running? Always returns 200 if the app is alive.
- `GET /health/ready` — **Readiness**: Are all dependencies reachable? Returns 200 (ready) or 503 (degraded).

---

## Implementation

```python
"""Health check endpoints for Docker and load balancer probing."""

import logging
from starlette.responses import JSONResponse
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness check — always returns 200 if the process is running.
    
    Used by Docker healthcheck and load balancers to determine if the
    container should receive traffic. Does NOT check dependencies.
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness check — verifies all dependencies are reachable.
    
    Returns:
        200 {"status": "ready", "checks": {...}} — all dependencies OK
        503 {"status": "degraded", "checks": {...}} — one or more failed
    """
    checks: dict[str, str] = {}

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        logger.warning("postgres health check failed: %s", e)
        checks["postgres"] = f"error: {e}"

    # Check Redis (via Celery)
    try:
        from src.workers.celery_app import celery_app
        celery_app.control.ping(timeout=2)
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning("redis health check failed: %s", e)
        checks["redis"] = f"error: {e}"

    # Check Qdrant
    try:
        import os
        from qdrant_client import QdrantClient
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        logger.warning("qdrant health check failed: %s", e)
        checks["qdrant"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "degraded",
            "checks": checks,
        },
    )
```

---

## Register in `main.py`

```python
from src.routers.health import router as health_router

app.include_router(health_router)
# No prefix — endpoints are at /health and /health/ready
```

**Important**: Register the health router BEFORE other routers and BEFORE adding the Prometheus `/metrics` exclusion. The health endpoint must be excluded from Prometheus instrumentation:

```python
instrumentator = Instrumentator(
    excluded_handlers=["/health", "/health/ready", "/metrics", "/mcp"],
)
```

---

## Response Schemas

### Liveness (`GET /health`)

```json
{"status": "ok"}
```
HTTP 200 always (if process is alive).

### Readiness (`GET /health/ready`)

**All healthy** (HTTP 200):
```json
{
  "status": "ready",
  "checks": {
    "postgres": "ok",
    "redis": "ok",
    "qdrant": "ok"
  }
}
```

**Degraded** (HTTP 503):
```json
{
  "status": "degraded",
  "checks": {
    "postgres": "ok",
    "redis": "error: Connection refused",
    "qdrant": "ok"
  }
}
```

---

## Docker Compose Healthcheck Integration

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s   # Allow time for FastAPI startup
```

Use `/health` (liveness) for Docker healthcheck — NOT `/health/ready`. The readiness check may fail during startup if dependencies aren't ready yet, causing the container to be marked unhealthy before it's had a chance to initialize.

---

## Kubernetes Probe Configuration

```yaml
# Kubernetes deployment spec
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

---

## Extended Health Check with Metrics

For more detailed health reporting, include version and uptime:

```python
import os
import time
from datetime import datetime, timezone

START_TIME = time.time()

@router.get("/health/info")
async def health_info():
    """Extended health info — version, uptime, environment."""
    return {
        "status": "ok",
        "version": os.getenv("RELEASE_VERSION", "1.0.0"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

## Excluding Health Endpoints from OpenTelemetry

Health check endpoints generate noise in traces. Exclude them:

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="health,health/ready,metrics",
)
```

---

## Testing Health Endpoints

```python
import pytest
from httpx import AsyncClient
from src.main import app

@pytest.mark.asyncio
async def test_health_liveness():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_health_readiness_structure():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health/ready")
    # Status is 200 or 503 depending on dependencies
    assert response.status_code in (200, 503)
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert "postgres" in body["checks"]
```

---

## Common Pitfalls

1. **Liveness vs Readiness confusion** — Docker `healthcheck` should use `/health` (liveness). Using `/health/ready` for Docker healthcheck causes containers to restart when dependencies are temporarily unavailable.
2. **`start_period`** — Without this, Docker marks the container unhealthy during the startup grace period. Set to at least the time it takes for FastAPI to fully initialize.
3. **`starlette.responses.JSONResponse`** — Required to return a custom HTTP status code (503). `return {"status": "degraded"}` always returns 200.
4. **Celery ping timeout** — `celery_app.control.ping(timeout=2)` blocks for up to 2 seconds. Keep timeouts short in health checks.
5. **Excluding from metrics** — Health endpoints generate high-frequency, low-value metrics. Always exclude from Prometheus instrumentation.

---

## Sources
- https://fastapi.tiangolo.com/advanced/response-directly/
- https://docs.docker.com/compose/compose-file/05-services/#healthcheck
- https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
