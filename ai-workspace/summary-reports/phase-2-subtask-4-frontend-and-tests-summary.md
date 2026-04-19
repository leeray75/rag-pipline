# Phase 2, Subtask 4 — Frontend Staging Browser UI + Tests Summary

## Subtask
Phase 2, Subtask 4 — Frontend Staging Browser UI + Tests

## Status
Complete

## Date
2026-04-17

## Files Created/Modified

| Action | File Path |
|--------|-----------|
| Create | rag-pipeline/apps/web/src/store/api/jobs-api.ts |
| Create | rag-pipeline/apps/web/src/app/ingestion/page.tsx |
| Create | rag-pipeline/apps/web/src/features/staging/staging-browser.tsx |
| Create | rag-pipeline/apps/web/src/hooks/use-job-progress.ts |
| Modify | rag-pipeline/apps/web/src/app/layout.tsx |
| Modify | rag-pipeline/apps/web/src/store/api/api-slice.ts |
| Create | rag-pipeline/apps/api/tests/test_converter.py |
| Create | rag-pipeline/apps/api/tests/test_link_discovery.py |

## Key Decisions
- Used existing shadcn/ui component patterns for consistency
- RTK Query with cache tagging for data fetching and invalidation
- WebSocket auto-reconnect for real-time job progress
- Two-panel layout with document list and tabbed viewer for staging browser

## Issues Encountered
None - all implementations followed the existing project patterns without issues.

## Dependencies for Next Subtask
- Backend API endpoints must be running (Phase 2 Subtasks 1-3)
- WebSocket endpoint at /api/v1/ws/jobs/{id}/stream must be available
- Frontend environment variables: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL

## Verification Results

### Frontend Files Created
- [x] `jobs-api.ts` - 6 RTK Query endpoints (createJob, getJob, getJobStatus, listDocuments, getDocument, deleteDocument)
- [x] `ingestion/page.tsx` - URL input form with crawl toggle
- [x] `staging-browser.tsx` - Two-panel document browser with Markdown preview
- [x] `use-job-progress.ts` - WebSocket hook with auto-reconnect

### Python Tests Created
- [x] `test_converter.py` - 3 tests for HTML to Markdown conversion
- [x] `test_link_discovery.py` - 2 tests for link extraction and deduplication

### UI Dependencies Installed
- [x] @monaco-editor/react@4.7.0
- [x] react-split-pane@3.2.0
- [x] react-markdown@10.1.0
- [x] remark-gfm@4.0.1

### Navigation Added
- [x] Navigation links in layout.tsx (Ingestion, Staging)

### RTK Query TagTypes
- [x] "Jobs" and "Documents" already present in api-slice.ts

## Implementation Notes