# Fix Missing SQLAlchemy Models - Summary Report

**Date**: 2026-04-23  
**Branch**: `bugfix/fix-missing-sqlalchemy-models`  
**Issue**: `ERR_CONNECTION_REFUSED` on `/api/v1/jobs` endpoint

## Problem Description

Users reported getting `ERR_CONNECTION_REFUSED` when trying to submit URLs to the ingestion page. The error occurred at `http://localhost:8000/api/v1/jobs`.

## Root Cause Analysis

1. **API container not running**: The `docker ps` output showed the `api` container was missing from the running containers
2. **Missing SQLAlchemy ORM models**: The application was failing to start due to missing model definitions:
   - `src/models/chunk.py` - Missing `ChunkRecord`, `VectorCollection`, `IngestionJob`, `JobStatus`
   - `src/models/document.py` - Missing `Document`
   - `src/models/review.py` - Missing `ReviewComment`, `ReviewDecision`
   - `src/models/audit.py` - Missing `AuditReport`
3. **Missing Base class**: The `Base` class was not exported from `src/database.py`

## Solution Implemented

### Files Created

| File | Description |
|------|-------------|
| `apps/api/src/models/__init__.py` | Module exports for all models |
| `apps/api/src/models/chunk.py` | `ChunkRecord`, `VectorCollection`, `IngestionJob`, `JobStatus` |
| `apps/api/src/models/document.py` | `Document` |
| `apps/api/src/models/review.py` | `ReviewComment`, `ReviewDecision` |
| `apps/api/src/models/audit.py` | `AuditReport` |

### Files Modified

| File | Changes |
|------|---------|
| `apps/api/src/database.py` | Added `Base` class for model inheritance |
| `apps/api/src/models/chunk.py` | Updated relationships to use correct model names |
| `apps/api/src/models/document.py` | Added `review_decisions` and `review_comments` relationships |
| `apps/api/src/models/chunk.py` | Added `audit_reports` relationship to `IngestionJob` |

### Database Schema

The models align with the existing Alembic migrations:
- `edaa014c2adf` - Initial schema (ingestion_jobs, audit_reports, documents, vector_collections)
- `2026_04_18_1441` - Review decisions and comments
- `2026_04_18_1708` - Chunks and updated vector_collections

## Testing

1. Started the API container: `docker compose up -d api`
2. Rebuilt the container with new models
3. Verified the container starts successfully

## Known Issues

The `a2a-sdk` package has changed its API. The import `from a2a.client import A2AClient` is failing. This needs to be addressed in a follow-up fix.

## Files Changed Summary

```
apps/api/src/database.py              | Added Base class
apps/api/src/models/__init__.py       | Created (new file)
apps/api/src/models/chunk.py          | Created (new file)
apps/api/src/models/document.py       | Created (new file)
apps/api/src/models/review.py         | Created (new file)
apps/api/src/models/audit.py          | Created (new file)
CHANGELOG.md                          | Updated with fix details
```

## Deployment Notes

To deploy this fix:

```bash
cd rag-pipline/infra
docker compose build api
docker compose up -d api
```

## Related Documentation

- [`rag-pipline/CHANGELOG.md`](../../CHANGELOG.md)
- [`rag-pipline/apps/api/src/database.py`](../../apps/api/src/database.py)
- [`rag-pipline/apps/api/src/models/`](../../apps/api/src/models/)
