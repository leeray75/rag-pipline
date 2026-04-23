# Ingestion Progress Visualization - Implementation Plan

## Overview

This document outlines the plan to add real-time progress visualization to the ingestion page, allowing users to monitor job status and identify issues during the crawling and ingestion process.

## Current State

### What Exists

1. **Job Status API**: [`/api/v1/jobs/{job_id}/status`](rag-pipline/apps/api/src/routers/jobs.py:62-69)
   - Returns lightweight job status for polling
   - Includes: id, status, total_documents, processed_documents, current_audit_round

2. **Document List API**: [`/api/v1/jobs/{job_id}/documents`](rag-pipline/apps/api/src/routers/jobs.py:72-78)
   - Lists all documents for a job
   - Includes: id, url, title, status, word_count, quality_score

3. **Job Details API**: [`/api/v1/jobs/{job_id}`](rag-pipline/apps/api/src/routers/jobs.py:52-59)
   - Full job details including created_at, updated_at

### What's Missing

1. **Real-time Progress Updates**: No WebSocket or SSE for live progress
2. **Per-Document Status**: No detailed view of individual document processing
3. **Error Visualization**: No clear indication of failed documents
4. **Audit Progress**: No visibility into audit round progress
5. **Embedding Progress**: No visibility into vector embedding status

## Proposed Solution

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Ingestion Page (page.tsx)                                    │  │
│  │  - Job creation form                                          │  │
│  │  - Progress visualization (new)                               │  │
│  │  - Real-time updates via WebSocket                            │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              │ WebSocket / SSE                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Polling (fallback)                                           │  │
│  │  - /api/v1/jobs/{job_id}/status                               │  │
│  │  - /api/v1/jobs/{job_id}/documents                            │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP API
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  WebSocket Router                                              │  │
│  │  - /api/v1/ws/jobs/{job_id}                                   │  │
│  │  - Broadcasts progress updates                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              │ Celery Tasks                          │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Progress Tracking                                             │  │
│  │  - Job status updates                                         │  │
│  │  - Document processing status                                 │  │
│  │  - Audit progress                                             │  │
│  │  - Embedding progress                                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Backend - WebSocket Router

**File**: `rag-pipline/apps/api/src/routers/websocket.py` (existing, needs enhancement)

**Changes**:
1. Add job progress broadcast endpoint
2. Create progress message schema
3. Integrate with Celery task callbacks

**New Endpoints**:
- `GET /api/v1/ws/jobs/{job_id}` - WebSocket connection for job progress
- `GET /api/v1/ws/jobs/{job_id}/documents` - Document-level progress

#### Step 2: Backend - Progress Tracking

**File**: `rag-pipline/apps/api/src/workers/crawl_tasks.py`

**Changes**:
1. Add progress callback to Celery tasks
2. Broadcast progress via WebSocket
3. Update database with real-time status

**Progress Events**:
```typescript
interface ProgressEvent {
  job_id: string;
  event_type: 
    | "crawl_started"
    | "crawl_progress"
    | "crawl_complete"
    | "audit_started"
    | "audit_progress"
    | "audit_complete"
    | "embedding_started"
    | "embedding_progress"
    | "embedding_complete"
    | "job_complete"
    | "error";
  message: string;
  data?: {
    current?: number;
    total?: number;
    documents?: DocumentProgress[];
    audit_round?: number;
    error?: string;
  };
}
```

#### Step 3: Backend - Enhanced Status API

**File**: `rag-pipline/apps/api/src/routers/jobs.py`

**Changes**:
1. Add `/status/verbose` endpoint with full progress details
2. Add `/documents/status` endpoint with per-document progress

**New Endpoints**:
- `GET /api/v1/jobs/{job_id}/status/verbose` - Full progress details
- `GET /api/v1/jobs/{job_id}/documents/status` - Document progress

#### Step 4: Frontend - Progress Visualization

**File**: `rag-pipline/apps/web/src/app/ingestion/page.tsx`

**Changes**:
1. Add WebSocket connection for real-time updates
2. Add polling fallback for compatibility
3. Create progress visualization components

**New Components**:
1. **JobProgressBar**: Shows overall job progress
2. **DocumentList**: Lists all documents with status
3. **AuditProgress**: Shows audit round progress
4. **EmbeddingProgress**: Shows vector embedding progress
5. **ErrorLog**: Displays errors with details

#### Step 5: Frontend - Enhanced UI

**File**: `rag-pipline/apps/web/src/app/ingestion/page.tsx`

**UI Elements**:
```
┌─────────────────────────────────────────────────────────────────────┐
│  Job ID: abc123...                                                  │
│  Status: CRAWLING                                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   │
│  │  45% Complete                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Documents: 23 / 50 processed                               │   │
│  │  ┌───────────────────────────────────────────────────────┐   │   │
│  │  │  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   │   │
│  │  │  46%                                                     │   │   │
│  │  └───────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Audit Round: 1 / 3                                         │   │
│  │  ┌───────────────────────────────────────────────────────┐   │   │
│  │  │  ████████████████████████████████████████████████░░   │   │   │
│  │  │  80%                                                     │   │   │
│  │  └───────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Embedding: 150 / 500 chunks                                │   │
│  │  ┌───────────────────────────────────────────────────────┐   │   │
│  │  │  ██████████████████████████████████████████████████   │   │   │
│  │  │  100%                                                    │   │   │
│  │  └───────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Document Status                                             │   │
│  │  ┌───────────────────────────────────────────────────────┐   │   │
│  │  │  ✓ doc_0001.md    Approved    1,234 words             │   │   │
│  │  │  ✓ doc_0002.md    Approved    2,345 words             │   │   │
│  │  │  ✗ doc_0003.md    Failed      Connection timeout      │   │   │
│  │  │  ⏳ doc_0004.md    Processing...                       │   │   │
│  │  └───────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Technical Details

### WebSocket Protocol

**Connection**: `ws://localhost:8000/api/v1/ws/jobs/{job_id}`

**Messages**:

**Server → Client**:
```json
{
  "type": "progress",
  "job_id": "abc123",
  "event": "crawl_progress",
  "timestamp": "2026-04-23T22:30:00.000Z",
  "data": {
    "current": 23,
    "total": 50,
    "message": "Processed 23/50 documents"
  }
}
```

**Client → Server**:
```json
{
  "type": "ping"
}
```

### Polling Fallback

If WebSocket is not available, fall back to polling:

```typescript
const pollInterval = setInterval(async () => {
  const status = await fetch(`/api/v1/jobs/${jobId}/status/verbose`);
  updateProgress(status.data);
}, 2000); // Poll every 2 seconds
```

### Database Schema Changes

**File**: `rag-pipline/apps/api/alembic/versions/edaa014c2adf_initial_schema.py`

**New Fields**:
- `documents.processed_at` - Timestamp when document was processed
- `documents.error_message` - Error message if processing failed
- `ingestion_jobs.current_phase` - Current phase (crawling, auditing, embedding)

### Error Handling

**Error Types**:
1. **Network Errors**: Connection timeout, DNS failure
2. **Content Errors**: Invalid HTML, missing content
3. **Processing Errors**: Conversion failure, embedding failure

**Error Display**:
- Red badge on failed documents
- Expandable error details
- Retry button for transient errors

## Implementation Timeline

### Phase 1: Backend (Week 1)
- [ ] Add WebSocket progress broadcast to Celery tasks
- [ ] Create progress message schema
- [ ] Add verbose status endpoint
- [ ] Update database schema for progress tracking

### Phase 2: Frontend (Week 2)
- [ ] Add WebSocket connection to ingestion page
- [ ] Create progress visualization components
- [ ] Implement polling fallback
- [ ] Add error handling and display

### Phase 3: Testing (Week 3)
- [ ] Test WebSocket connection
- [ ] Test progress updates
- [ ] Test error handling
- [ ] Test polling fallback

### Phase 4: Documentation (Week 4)
- [ ] Update API documentation
- [ ] Update user documentation
- [ ] Create troubleshooting guide

## Alternative Approaches

### Option A: Server-Sent Events (SSE)

**Pros**:
- Simpler than WebSocket
- Built into HTTP
- Automatic reconnection

**Cons**:
- One-way communication only
- Less efficient for bidirectional updates

### Option B: Long Polling

**Pros**:
- Works with any HTTP server
- Simple to implement

**Cons**:
- Higher latency
- More server load
- Not real-time

### Option C: GraphQL Subscriptions

**Pros**:
- Type-safe
- Flexible queries
- Good tooling

**Cons**:
- More complex setup
- Additional dependencies

## Recommendations

1. **Use WebSocket** for real-time updates
2. **Implement polling fallback** for compatibility
3. **Add verbose status endpoint** for debugging
4. **Create progress visualization** with clear status indicators
5. **Add error handling** with retry capability

## Success Metrics

1. **Progress Update Latency**: < 1 second from Celery task completion
2. **UI Refresh Rate**: < 2 seconds from backend update
3. **Error Detection Time**: < 5 seconds from failure
4. **Page Load Time**: < 2 seconds with progress data

## References

- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [Next.js WebSocket Example](https://github.com/vercel/next.js/tree/canary/examples/with-websocket)
- [React Query Polling](https://tanstack.com/query/latest/docs/react/guides/polling)
