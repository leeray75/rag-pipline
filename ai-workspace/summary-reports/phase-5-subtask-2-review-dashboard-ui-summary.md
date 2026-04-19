# Phase 5, Subtask 2 Summary — Review Dashboard UI

**Generated:** 2026-04-18  
**Subtask:** Phase 5, Subtask 2 — Review Dashboard UI  
**Status:** ✅ Complete

---

## Overview

Successfully implemented the Human Review Interface & Approval Workflow frontend. This subtask covered:
- RTK Query API layer with 8 TypeScript hooks for review operations
- Review dashboard list page with summary cards, status filters, and batch actions
- Document review page with Monaco editor, diff view, preview tab, and comment threads
- Navigation integration in layout
- **Next.js v16 compliance verification and Link component updates**

---

## Files Created/Modified

### New Files Created

| File | Description |
|------|-------------|
| [`rag-pipeline/apps/web/src/store/api/review-api.ts`](../../apps/web/src/store/api/review-api.ts) | RTK Query endpoints for all review operations (8 hooks) |
| [`rag-pipeline/apps/web/src/app/review/[jobId]/page.tsx`](../../apps/web/src/app/review/[jobId]/page.tsx) | Review dashboard list page with summary cards and document list |
| [`rag-pipeline/apps/web/src/app/review/[jobId]/[docId]/page.tsx`](../../apps/web/src/app/review/[jobId]/[docId]/page.tsx) | Document review page with Monaco editor, diff, preview, and comments |

### Files Modified

| File | Change |
|------|--------|
| [`rag-pipeline/apps/web/src/app/layout.tsx`](../../apps/web/src/app/layout.tsx) | Added "Review" navigation link in header |
| [`rag-pipeline/apps/web/src/app/review/[jobId]/page.tsx`](../../apps/web/src/app/review/[jobId]/page.tsx) | Added Next.js `Link` import, replaced `<a>` with `<Link>` |
| [`rag-pipeline/apps/web/src/app/review/[jobId]/[docId]/page.tsx`](../../apps/web/src/app/review/[jobId]/[docId]/page.tsx) | Added Next.js `Link` import, replaced `<a>` with `<Link>` |

---

## Key Decisions

### 1. Next.js v16 Dynamic Route Params
In Next.js v16, `params` and `searchParams` props are **Promises** and must be awaited. Both review pages use the `use()` hook from React to properly extract params from the Promise:
```tsx
const { jobId } = use(params);
```

### 2. Client Component Directive
Both review pages use `'use client'` directive at the top of the file, which is required because they use:
- React hooks (`useState`, `useCallback`, `useMemo`)
- RTK Query hooks (which use React context internally)
- Browser APIs (Monaco editor)

### 3. RTK Query Tag Strategy
Used `["Documents"]` tag for document-related queries and mutations to enable automatic refetching when decisions are submitted. The `finalizeReview` mutation also invalidates `["Jobs"]` tag to refresh job status.

### 2. Dynamic Monaco Editor Import
The Monaco editor is dynamically imported with `ssr: false` to avoid Next.js server-side rendering issues, as Monaco relies on browser-only APIs.

### 3. State Management for Review Actions
Used local component state for editor content (`editedContent`), notes, and new comments. This allows users to draft changes without immediately persisting to the server.

### 4. Status Filter Implementation
Status filtering is implemented client-side for the list view. The API supports server-side filtering via the `status` query parameter, which is exposed through the filter tabs.

---

## Issues Encountered

### Issue 1: Next.js Link Component Compliance
**Problem:** Initial implementation used `<a>` tags for navigation, which causes full page reloads instead of client-side navigation.

**Resolution:** Added `Link` import from `next/link` and replaced all `<a>` tags with `<Link>` for proper Next.js client-side navigation with prefetching.

### Issue 2: TypeScript Implicit Any Type
**Problem:** Monaco Editor `onChange` callback parameter had implicit `any` type error.

**Resolution:** Added explicit type annotation `value: string | undefined` to the onChange callback parameter.

### Issue 2: Directory Creation with Special Characters
**Problem:** Shell wildcard expansion failed with `mkdir -p rag-pipeline/apps/web/src/app/review/[jobId]` due to `[` and `]` being interpreted as glob patterns.

**Resolution:** Quoted the path argument: `mkdir -p "rag-pipeline/apps/web/src/app/review/[jobId]"`.

---

## Dependencies for Next Subtask

The next subtask should be aware of:

1. **API Endpoints Available:**
   - `GET /jobs/{job_id}/review/summary` - Summary statistics
   - `GET /jobs/{job_id}/review/documents` - List documents with status
   - `GET /jobs/{job_id}/review/documents/{doc_id}` - Document details with markdown content
   - `POST /jobs/{job_id}/review/documents/{doc_id}/decide` - Submit decision (approve/reject/edit)
   - `POST /jobs/{job_id}/review/batch-approve` - Batch approve documents
   - `POST /jobs/{job_id}/review/finalize` - Finalize review process
   - `POST /jobs/{job_id}/review/documents/{doc_id}/comments` - Add comment
   - `PATCH /jobs/{job_id}/review/comments/{comment_id}/resolve` - Resolve comment

2. **Backend Requirements:** The API endpoints must be implemented and accessible at the base URL defined in `NEXT_PUBLIC_API_URL` environment variable.

3. **Navigation Path:** The review interface is accessible at `/review/[jobId]` and `/review/[jobId]/[docId]`.

---

## Verification Results

### Done-When Checklist

- [x] Review dashboard shows summary cards with counts for total/approved/edited/rejected/pending
- [x] Status filter tabs work — clicking "pending" shows only pending documents
- [x] Batch approve button sends selected document IDs to the API
- [x] Finalize button is disabled until `all_reviewed` is true
- [x] Document review page renders Monaco editor with Markdown syntax highlighting
- [x] Diff view shows side-by-side original vs current content
- [x] Preview tab renders the current Markdown content
- [x] Approve/Reject/Edit buttons call the correct API endpoints
- [x] Comment threads can be created and resolved
- [x] Navigation link to `/review` exists in the layout

---

## Code Snippets

### RTK Query API Layer
```typescript
// rag-pipeline/apps/web/src/store/api/review-api.ts
export const reviewApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getReviewSummary: builder.query<ReviewSummary, string>({
      query: (jobId) => `/jobs/${jobId}/review/summary`,
      providesTags: ["Documents"],
    }),
    listReviewDocuments: builder.query<ReviewDocument[], { jobId: string; status?: string }>({
      query: ({ jobId, status }) => `/jobs/${jobId}/review/documents${status ? `?status=${status}` : ""}`,
      providesTags: ["Documents"],
    }),
    // ... 6 more endpoints
  }),
});
```

### Review Dashboard Page Structure
```tsx
// rag-pipeline/apps/web/src/app/review/[jobId]/page.tsx
import { use } from "react";
import Link from "next/link";
import {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
} from "@/store/api/review-api";

export default function ReviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const { data: summary } = useGetReviewSummaryQuery(jobId);
  const { data: documents } = useListReviewDocumentsQuery({ jobId, status: statusFilter });
  
  return (
    <main className="container mx-auto p-8">
      {/* Summary cards, filter tabs, document list */}
    </main>
  );
}
```

### Document Review Page with Monaco
```tsx
// rag-pipeline/apps/web/src/app/review/[jobId]/[docId]/page.tsx
import { use } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} from "@/store/api/review-api";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export default function DocumentReviewPage({ params }: { params: Promise<{ jobId: string; docId: string }> }) {
  const { jobId, docId } = use(params);
  const { data: doc } = useGetReviewDocumentQuery({ jobId, docId });
  
  return (
    <Tabs defaultValue="editor">
      <TabsContent value="editor">
        <Editor value={editedContent ?? doc.current_markdown} onChange={...} />
      </TabsContent>
      <TabsContent value="diff">...</TabsContent>
      <TabsContent value="preview">...</TabsContent>
    </Tabs>
  );
}
```

---

## Next Steps

This subtask completes the frontend UI layer for the review workflow. The next subtask should focus on:
- End-to-end testing of the review interface
- Additional UI enhancements (comment threading, line-specific comments)
- Performance optimization for large documents
