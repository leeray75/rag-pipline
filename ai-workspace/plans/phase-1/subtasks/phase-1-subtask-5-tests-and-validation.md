# Phase 1, Subtask 5 — Initial Tests + Phase Validation

> **Phase**: Phase 1 — Foundation
> **Subtask**: 5 of 5
> **Prerequisites**: Subtasks 1-4 must be complete (mono-repo, FastAPI, Next.js, Docker, Celery, CI/CD all in place)
> **Scope**: 2 test files to create, run full Done-When checklist, run validation.sh

---

## Context

This subtask creates the initial pytest test suite for the FastAPI backend, runs the complete Phase 1 Done-When checklist, and executes the phase validation script. It covers Task 9 (initial tests) from the parent phase and serves as the final gate before Phase 1 is considered complete.

**Project Root**: `rag-pipeline/`
**Working Directory**: `rag-pipeline/apps/api/`

---

## Relevant Technology Stack

| Package | Version | Notes |
|---|---|---|
| pytest | 8.0.0+ | Already in pyproject.toml dev dependencies |
| pytest-asyncio | 0.25.0+ | Already in pyproject.toml dev dependencies |
| httpx | 0.28.0+ | Already in pyproject.toml dev dependencies |
| ruff | 0.11.0+ | Already in pyproject.toml dev dependencies |
| mypy | 1.15.0+ | Already in pyproject.toml dev dependencies |

---

## Step-by-Step Implementation

### Step 1: Create `tests/conftest.py`

Create file `rag-pipeline/apps/api/tests/conftest.py`:

```python
"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### Step 2: Create `tests/test_health.py`

Create file `rag-pipeline/apps/api/tests/test_health.py`:

```python
"""Health endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/v1/health should return 200 with service info."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "rag-pipeline-api"
    assert "version" in data
```

### Step 3: Run the test suite

```bash
cd rag-pipeline/apps/api
pytest tests/ -v
```

Expected output:
```
tests/test_health.py::test_health_endpoint PASSED
```

### Step 4: Run ruff linter

```bash
cd rag-pipeline/apps/api
ruff check src/ tests/
```

Expected: No errors.

### Step 5: Run mypy type checker

```bash
cd rag-pipeline/apps/api
mypy src/
```

Expected: No errors (or only expected warnings from third-party stubs).

### Step 6: Run the Phase 1 validation script

```bash
bash rag-pipeline/ai-workspace/plans/phase-1/validation.sh
```

This script checks:
1. Mono-repo root files (package.json, pnpm-workspace.yaml, turbo.json, .gitignore)
2. FastAPI backend files (pyproject.toml, main.py, config.py, database.py, routers, models)
3. Module stubs (agents, crawlers, converters, embeddings, ingest, mcp)
4. Test files (conftest.py, test_health.py)
5. Next.js frontend files (package.json, layout.tsx, page.tsx, store files)
6. Infrastructure files (docker-compose.yml, docker-compose.dev.yml, ci.yml)
7. Python import checks (all modules importable)
8. Type checking (mypy)
9. TypeScript compilation (tsc --noEmit)
10. Orphaned import check

### Step 7: Run the full Phase 1 Done-When checklist

Verify each item manually or via commands:

| # | Check | Command / Verification |
|---|---|---|
| 1 | `pnpm install` at repo root completes | `cd rag-pipeline && pnpm install` |
| 2 | Docker Compose starts all 7 services | `cd rag-pipeline/infra && docker compose -f docker-compose.yml up --build` |
| 3 | Health endpoint returns 200 | `curl http://localhost/api/v1/health` |
| 4 | Next.js dashboard loads at localhost:3000 | Open browser or `curl http://localhost:3000` |
| 5 | Postgres migrations run cleanly | `cd rag-pipeline/apps/api && alembic upgrade head` |
| 6 | Redis is reachable | `redis-cli ping` → PONG |
| 7 | Qdrant dashboard accessible | `curl http://localhost:6333/dashboard` |
| 8 | Celery worker connects to Redis | Check celery-worker container logs |
| 9 | pytest passes with ≥1 test | `cd rag-pipeline/apps/api && pytest tests/ -v` |
| 10 | CI pipeline YAML committed | `ls rag-pipeline/.github/workflows/ci.yml` |
| 11 | All code passes ruff and mypy | `ruff check src/ tests/ && mypy src/` |

### Step 8: Commit Phase 1

Once all checks pass:

```bash
cd rag-pipeline
git add -A
git commit -m "feat(phase-1): foundation — mono-repo, FastAPI, Next.js, Docker, CI/CD"
```

---

## Files to Create/Modify

| # | File Path | Action |
|---|---|---|
| 1 | `apps/api/tests/conftest.py` | Create |
| 2 | `apps/api/tests/test_health.py` | Create |

All paths relative to `rag-pipeline/`.

---

## Done-When Checklist

This is the **complete Phase 1 Done-When checklist**. All items must pass for Phase 1 to be considered complete.

- [ ] `pnpm install` at repo root completes successfully
- [ ] `docker compose -f infra/docker-compose.yml up --build` starts all 7 services with no errors
- [ ] `GET /api/v1/health` returns `200` with `{"status": "healthy"}`
- [ ] Next.js dashboard loads at `http://localhost:3000` showing 3 placeholder cards
- [ ] Postgres migrations run cleanly via `alembic upgrade head` — 4 tables created
- [ ] Redis is reachable — `redis-cli ping` returns `PONG`
- [ ] Qdrant dashboard is accessible at `http://localhost:6333/dashboard`
- [ ] Celery worker starts and connects to Redis broker
- [ ] `pytest tests/ -v` passes with ≥1 test
- [ ] CI pipeline YAML is committed at `.github/workflows/ci.yml`
- [ ] All code passes `ruff check` and `mypy` without errors
- [ ] `bash rag-pipeline/ai-workspace/plans/phase-1/validation.sh` passes with 0 errors

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-1-subtask-5-tests-and-validation-summary.md`

The summary report must include:
- **Subtask**: Phase 1, Subtask 5 — Initial Tests + Phase Validation
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know (i.e., Phase 2 readiness)
- **Verification Results**: Output of Done-When checklist items
- **Validation Script Output**: Full output of `validation.sh`
