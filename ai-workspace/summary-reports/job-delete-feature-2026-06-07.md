# Job Delete Feature Implementation Summary

**Date:** 2026-06-07  
**Implemented by:** Cline (AI Assistant)  
**Project:** rag-pipline  
**Version:** 1.2.2 → 1.2.3 (patch bump)

## Objective

Add the ability to cancel and delete stuck ingestion jobs from the web UI's Jobs page. Previously, the "View" button had no handler and there was no way to remove jobs.

## Problem

The Jobs page (`http://localhost/jobs`) displayed ingestion jobs but had no way to:
1. Cancel jobs that were stuck in `pending` or `crawling` status
2. Delete jobs to clean up the list
3. The "View" button in the Actions column was non-functional

## Solution

### 1. Backend: DELETE `/jobs/{job_id}` Endpoint

**File:** `rag-pipline/apps/api/src/routers/jobs.py`

Added new DELETE endpoint that:
- Validates the job exists (404 if not found)
- Deletes the staging directory and all associated files (HTML, Markdown)
- Removes all associated database records:
  - Documents (and their file references)
  - Chunks
  - Vector collections
  - Review decisions
  - Audit reports
- Deletes the job record itself
- Returns 204 No Content on success
- Logs the deletion event

```python
@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Cancel and delete an ingestion job and all associated data."""
    # ... validation, file cleanup, cascade delete, commit
```

### 2. Frontend: RTK Query Mutation

**File:** `rag-pipline/apps/web/src/store/api/jobs-api.ts`

Added `deleteJob` mutation:
```typescript
deleteJob: builder.mutation<void, string>({
  query: (id) => ({
    url: `/jobs/${id}`,
    method: "DELETE",
  }),
  invalidatesTags: ["Jobs"],
}),
```

The mutation invalidates the `["Jobs"]` tag on success, automatically refreshing the jobs list.

### 3. Frontend: Delete Button Component

**File:** `rag-pipline/apps/web/src/app/jobs/page.tsx`

Created `DeleteJobButton` component:
- Uses `useDeleteJobMutation` hook from RTK Query
- Shows confirmation dialog via `confirm()` before deleting
- Displays "Deleting..." button state during API call
- Styled with red color to indicate destructive action

```tsx
function DeleteJobButton({ jobId }: { jobId: string }) {
  const [deleteJob, { isLoading }] = useDeleteJobMutation();

  const handleDelete = useCallback(() => {
    if (confirm(`Are you sure you want to delete this job? This action cannot be undone.`)) {
      deleteJob(jobId);
    }
  }, [deleteJob, jobId]);

  // ... loading state and button UI
}
```

## Files Modified

| File | Change |
|------|--------|
| `apps/api/src/routers/jobs.py` | Added `DELETE /jobs/{job_id}` endpoint with cascade delete |
| `apps/web/src/store/api/jobs-api.ts` | Added `deleteJob` RTK Query mutation |
| `apps/web/src/app/jobs/page.tsx` | Added `DeleteJobButton` component with confirmation |

## Files Created

| File | Description |
|------|-------------|
| `ai-workspace/summary-reports/job-delete-feature-2026-06-07.md` | This summary report |

## API Changes

### New Endpoint

```
DELETE /api/v1/jobs/{job_id}
```

**Response:** 204 No Content on success  
**Error Responses:**
- 404 Not Found - Job does not exist

**Behavior:**
- Deletes all staging files (HTML, Markdown)
- Deletes all associated database records (documents, chunks, collections, reviews, audits)
- Deletes the job record itself
- Logs deletion event

## UI Changes

### Jobs Page Actions Column

Before:
```
[View]
```

After:
```
[View] [Delete]
```

- "View" button still present (non-functional in current version)
- "Delete" button in red, with confirmation dialog
- Shows "Deleting..." state during API call

## Testing

- ✅ Docker build successful for both `api` and `web` containers
- ✅ API container restarted successfully
- ✅ Web container restarted successfully

## Known Limitations

1. **View button not functional** - The "View" button in the Actions column has no onClick handler. This is a pre-existing issue, not addressed in this PR.
2. **No soft delete** - Jobs are permanently deleted, not just marked as cancelled. This means there's no way to recover deleted jobs.
3. **No bulk delete** - Jobs must be deleted one at a time.
4. **Simple confirmation** - Uses browser `confirm()` dialog instead of a styled modal.

## Recommendations for Future Work

1. Implement the "View" button to show job details
2. Add bulk delete selection with checkboxes
3. Add a "Cancel" endpoint that sets status to `FAILED` without deleting (for jobs with running Celery tasks)
4. Add a styled confirmation modal instead of `confirm()`
5. Add toast notifications for delete success/error feedback

## Git

- **Branch:** `feature/job-delete-feature-2026-06-07`
- **Version bump:** 1.2.2 → 1.2.3