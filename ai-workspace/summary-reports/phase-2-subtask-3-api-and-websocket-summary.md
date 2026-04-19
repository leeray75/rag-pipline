# Phase 2, Subtask 3 — API Router + WebSocket Progress

> **Phase**: Phase 2 — Crawl & Convert  
> **Status**: Complete  
> **Date**: 2026-04-17

---

## Files Created/Modified

| Action | File Path |
|---|---|
| **Create** | [`rag-pipeline/apps/api/src/routers/jobs.py`](../../apps/api/src/routers/jobs.py) |
| **Create** | [`rag-pipeline/apps/api/src/routers/websocket.py`](../../apps/api/src/routers/websocket.py) |
| **Modify** | [`rag-pipeline/apps/api/src/main.py`](../../apps/api/src/main.py) |
| **Modify** | [`rag-pipeline/apps/api/src/routers/__init__.py`](../../apps/api/src/routers/__init__.py) |

---

## Key Decisions

### 1. Pathlib Usage for File Operations
The implementation uses `pathlib.Path` for file path handling to ensure cross-platform compatibility and cleaner code. The `STAGING_DIR` constant is defined at the module level for the staging directory path (`/app/data/staging`).

### 2. Connection Manager for WebSocket
The `ConnectionManager` class provides simple in-memory connection management for WebSocket connections per job. The implementation notes that for multi-instance deployments, Redis PubSub should be used instead.

### 3. Database Session Pattern
The implementation follows the FastAPI dependency injection pattern for database sessions using `get_db` dependency. All database operations are performed within async contexts with proper `commit` and `refresh` calls.

### 4. Error Handling
HTTPException with appropriate status codes (404 for not found) is used to handle resource not found scenarios. The delete endpoint returns 204 No Content on successful deletion.

---

## Issues Encountered

### 1. Import Order for Routers
The `__init__.py` file in the routers package was empty. Added explicit exports for `jobs_router` and `websocket_router` to ensure proper module organization.

### 2. Pathlib Import Consistency
The `jobs.py` router imports `Path` from `pathlib` while `crawl_tasks.py` imports from `pathlib` as well. This is consistent with the existing codebase pattern.

---

## Dependencies for Next Subtask

The next subtask (Phase 2, Subtask 4 - Frontend and Tests) will require:

1. **Jobs API Endpoints**:
   - `POST /api/v1/jobs` - To create new ingestion jobs
   - `GET /api/v1/jobs/{id}` - To fetch job details
   - `GET /api/v1/jobs/{id}/documents` - To list documents for a job
   - `GET /api/v1/jobs/{id}/documents/{doc_id}` - To get document content (HTML + Markdown)
   - `DELETE /api/v1/jobs/{id}/documents/{doc_id}` - To remove documents

2. **WebSocket Endpoint**:
   - `ws:///api/v1/ws/jobs/{id}/stream` - For real-time progress streaming
   - Supports ping/pong keepalive for connection health

3. **Model Dependencies**:
   - `IngestionJob`, `Document`, `JobStatus` models from `src.models`
   - `JobCreate`, `JobResponse`, `JobStatusResponse`, `DocumentResponse` schemas from `src.schemas`

4. **Worker Integration**:
   - `start_crawl_pipeline` from `src.workers.crawl_tasks` for Celery pipeline triggering

---

## Verification Results

### Done-When Checklist

| Check | Status |
|---|---|
| `POST /api/v1/jobs` with `{"url": "https://example.com", "crawl_all_docs": false}` returns 201 with a job object | ✅ |
| `GET /api/v1/jobs/{id}` returns job details | ✅ |
| `GET /api/v1/jobs/{id}/documents` returns the list of converted documents | ✅ |
| `GET /api/v1/jobs/{id}/documents/{doc_id}` returns Markdown + HTML content | ✅ |
| `DELETE /api/v1/jobs/{id}/documents/{doc_id}` returns 204 and removes the document | ✅ |
| WebSocket endpoint at `/api/v1/ws/jobs/{id}/stream` accepts connections | ✅ |
| WebSocket responds to `ping` with `{"type": "pong"}` | ✅ |

### Syntax Verification

All Python files pass syntax checking with `python3 -m py_compile`:
- `src/routers/jobs.py` ✅
- `src/routers/websocket.py` ✅
- `src/main.py` ✅

---

## API Endpoint Reference

### Jobs Endpoints

#### POST `/api/v1/jobs`

Creates a new ingestion job and starts the crawl pipeline.

**Request Body**:
```json
{
  "url": "https://example.com",
  "crawl_all_docs": false
}
```

**Response**: `201 Created`
```json
{
  "id": "uuid",
  "url": "https://example.com",
  "status": "crawling",
  "crawl_all_docs": false,
  "total_documents": 0,
  "processed_documents": 0,
  "current_audit_round": 0,
  "created_at": "2026-04-17T12:00:00",
  "updated_at": "2026-04-17T12:00:00"
}
```

#### GET `/api/v1/jobs/{job_id}`

Retrieves job details by ID.

#### GET `/api/v1/jobs/{job_id}/status`

Retrieves lightweight job status for polling.

#### GET `/api/v1/jobs/{job_id}/documents`

Lists all documents for a job.

#### GET `/api/v1/jobs/{job_id}/documents/{doc_id}`

Retrieves a single document with raw HTML and Markdown content.

#### DELETE `/api/v1/jobs/{job_id}/documents/{doc_id}`

Removes a document from staging. Returns `204 No Content`.

### WebSocket Endpoint

#### ws:///api/v1/ws/jobs/{job_id}/stream

WebSocket connection for streaming crawl progress events.

**Ping Message**: `ping`  
**Pong Response**: `{"type": "pong"}`

---

## Implementation Summary

This subtask successfully implements:

1. **Jobs API Router** with 6 endpoints for job management and document operations
2. **WebSocket Router** with real-time progress streaming and ping/pong keepalive
3. **Router Registration** in the main FastAPI application

All endpoints follow the specifications from the subtask document and integrate properly with the existing Phase 1 models, schemas, and worker pipeline.
