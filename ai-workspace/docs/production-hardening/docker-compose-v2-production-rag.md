# Docker Compose V2 — Production Hardening RAG Reference Document

<!-- RAG_METADATA
topic: docker-compose, production, deployment, containers
library: docker-compose
version: V2 (Compose spec 3.x)
tags: docker-compose, healthcheck, deploy.resources, restart-policy, production, resource-limits
use_case: phase-7-subtask-4-production-hardening
-->

## Overview

**Docker Compose V2** (`docker compose` — note: no hyphen) is the current standard. Compose V1 (`docker-compose`) is deprecated. The production overlay pattern uses a base `docker-compose.yml` merged with `docker-compose.prod.yml` for environment-specific overrides.

**Usage**:
```bash
# Development
docker compose up -d

# Production (merge base + prod overlay)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Validate merged config
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

---

## Production Overlay Pattern

The `docker-compose.prod.yml` file only contains **overrides** — it does not repeat the full service definition. Docker Compose deep-merges the two files.

```yaml
# docker-compose.prod.yml — Production overrides only
services:
  api:
    restart: always
    environment:
      - ENVIRONMENT=production
      - LOG_FORMAT=json
      - OTEL_ENABLED=true
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## `restart` Policy

| Value | Behavior |
|---|---|
| `no` | Never restart (default) |
| `always` | Always restart on exit |
| `on-failure` | Restart only on non-zero exit code |
| `unless-stopped` | Restart unless explicitly stopped |

**Production**: Use `restart: always` for all services.

---

## `deploy.resources` — Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: "2.0"      # Max CPU cores (float string)
      memory: 2G       # Max memory (B, K, M, G)
    reservations:
      cpus: "0.5"      # Guaranteed CPU
      memory: 512M     # Guaranteed memory
```

**Important**: `deploy.resources` is only respected by Docker Swarm by default. For standalone `docker compose`, you must use `--compatibility` flag OR the resources are applied directly as container constraints in Compose V2.

In Compose V2 (standalone), `deploy.resources.limits` maps to `--cpus` and `--memory` Docker flags automatically.

---

## `healthcheck` Configuration

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  # OR: test: ["CMD-SHELL", "pg_isready -U postgres"]
  # OR: test: ["CMD", "redis-cli", "ping"]
  interval: 30s        # Time between checks
  timeout: 10s         # Max time for a single check
  retries: 3           # Failures before marking unhealthy
  start_period: 40s    # Grace period before counting failures
  disable: false       # Set true to disable inherited healthcheck
```

**`test` formats**:
- `["CMD", "executable", "arg1"]` — exec form, no shell
- `["CMD-SHELL", "shell command"]` — shell form, supports pipes/env vars
- `["NONE"]` — disable healthcheck

**Health states**: `starting` → `healthy` / `unhealthy`

---

## Service-Specific Healthchecks

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s   # FastAPI startup time

  celery-worker:
    healthcheck:
      test: ["CMD", "celery", "-A", "src.workers", "inspect", "ping"]
      interval: 60s
      timeout: 10s
      retries: 3

  postgres:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## `depends_on` with Health Conditions

```yaml
services:
  api:
    depends_on:
      postgres:
        condition: service_healthy    # Wait for postgres healthcheck to pass
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started    # Just wait for container to start
```

**Conditions**:
- `service_started` — Container is running (default)
- `service_healthy` — Container healthcheck passes
- `service_completed_successfully` — Container exited with code 0

---

## Named Volumes for Persistence

```yaml
services:
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
    driver: local
  qdrant_data:
    driver: local
  tempo_data:
    driver: local
  prometheus_data:
    driver: local
  loki_data:
    driver: local
  grafana_data:
    driver: local
```

---

## Environment Variable Substitution

```yaml
services:
  grafana:
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      # ${VAR:-default} — use default if VAR is unset or empty
      # ${VAR-default}  — use default only if VAR is unset
      # ${VAR:?error}   — fail with error if VAR is unset or empty
      # ${VAR?error}    — fail with error only if VAR is unset
```

---

## Networking

```yaml
networks:
  app:
    driver: bridge
  observability:
    driver: bridge

services:
  api:
    networks:
      - app
      - observability   # Can reach both app services and observability stack
  
  prometheus:
    networks:
      - observability   # Only on observability network
```

Services on the same network can reach each other by **service name** as hostname (e.g., `http://postgres:5432`, `http://tempo:4317`).

---

## Production Compose File — Full Example

```yaml
# docker-compose.prod.yml
services:
  api:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    environment:
      - ENVIRONMENT=production
      - LOG_FORMAT=json
      - OTEL_ENABLED=true
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  web:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 3G
        reservations:
          cpus: "0.5"
          memory: 1G
    environment:
      - CELERY_CONCURRENCY=8
      - ENVIRONMENT=production
      - LOG_FORMAT=json
    healthcheck:
      test: ["CMD", "celery", "-A", "src.workers", "inspect", "ping"]
      interval: 60s
      timeout: 10s
      retries: 3

  postgres:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
    command: >
      postgres
      -c max_connections=100
      -c shared_buffers=256MB
      -c effective_cache_size=768MB
      -c work_mem=4MB
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
        reservations:
          cpus: "0.5"
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Common Pitfalls

1. **`docker-compose` vs `docker compose`** — V2 uses `docker compose` (space, not hyphen). The old `docker-compose` binary is deprecated.
2. **`deploy.resources` in standalone mode** — In Compose V2 standalone (not Swarm), resource limits ARE applied. In Compose V1, they were ignored without `--compatibility`.
3. **`start_period`** — Critical for services with slow startup (FastAPI with model loading). Without it, healthcheck failures during startup count toward `retries`.
4. **`CMD` vs `CMD-SHELL`** — Use `CMD-SHELL` when you need shell features (pipes, env vars, `&&`). Use `CMD` for simple executables.
5. **Volume mount order** — Config files mounted as `:ro` (read-only) prevent accidental modification inside containers.
6. **`${VAR:-default}` in env files** — The `.env` file is auto-loaded from the same directory as `docker-compose.yml`. Use `--env-file` to specify a different path.

---

## Sources
- https://docs.docker.com/compose/compose-file/ (Compose spec)
- https://docs.docker.com/compose/compose-file/deploy/ (deploy key)
- https://docs.docker.com/compose/compose-file/05-services/#healthcheck
- https://docs.docker.com/compose/multiple-compose-files/merge/
