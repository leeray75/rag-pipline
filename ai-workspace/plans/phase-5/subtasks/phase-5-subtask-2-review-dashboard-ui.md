# Phase 5, Subtask 2 — Review Dashboard UI

**Phase**: Phase 5 — Human Review Interface & Approval Workflow
**Subtask**: 2 of 3
**Prerequisites**: Phase 4 complete + Phase 5 Subtask 1 complete — review API endpoints operational, `@monaco-editor/react` installed, `review_decisions` and `review_comments` tables exist, Pydantic schemas defined.
**Scope**: Build RTK Query API layer with 8 hooks, the review dashboard list page, and the per-document review page with Monaco editor, diff view, preview, approve/reject/edit buttons, and comment threads.

---

## Files to Create/Modify

| Action | File Path |
|--------|-----------|
| Create | `rag-pipeline/apps/web/src/store/api/review-api.ts` |
| Create | `rag-pipeline/apps/web/src/app/review/[jobId]/page.tsx` |
| Create | `rag-pipeline/apps/web/src/app/review/[jobId]/[docId]/page.tsx` |
| Modify | `rag-pipeline/apps/web/src/app/layout.tsx` (add nav link) |

---

## Relevant Technology Stack

| Package | Version | Notes |
|---------|---------|-------|
| Next.js | 16.2.3 | App Router with `use()` for async params |
| React | 19.2.5 | Bundled with Next.js |
| Redux Toolkit | 2.11.2 | RTK Query for API layer |
| TailwindCSS | 4.2.2 | Utility-first CSS |
| shadcn/ui | latest | Card, Badge, Button, Tabs, Input, Separator components |
| @monaco-editor/react | latest | Monaco editor React wrapper — installed in Subtask 1 |
| diff | latest | Text diff library |
| react-diff-viewer-continued | latest | Side-by-side diff component |

---

## Step-by-Step Implementation

### Step 1: Create RTK Query Endpoints

**Create file**: `rag-pipeline/apps/web/src/store/api/review-api.ts`

This file defines all TypeScript interfaces and 8 RTK Query hooks for the review API.

```typescript
import { apiSlice } from "./api-slice";

export interface ReviewDocument {
  id: string;
  url: string;
  title: string | null;
  word_count: number | null;
  quality_score: number | null;
  review_status: string;
  reviewer_notes: string | null;
}

export interface ReviewDocDetail {
  id: string;
  url: string;
  title: string | null;
  word_count: number | null;
  quality_score: number | null;
  current_markdown: string;
  original_markdown: string;
  has_changes: boolean;
  review_decision: {
    decision: string;
    reviewer_notes: string | null;
    created_at: string;
  } | null;
  comments: ReviewCommentItem[];
}

export interface ReviewCommentItem {
  id: string;
  line_number: number | null;
  content: string;
  author: string;
  resolved: boolean;
  created_at: string;
}

export interface ReviewSummary {
  total_documents: number;
  approved: number;
  rejected: number;
  edited: number;
  pending: number;
  all_reviewed: boolean;
}

export const reviewApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getReviewSummary: builder.query<ReviewSummary, string>({
      query: (jobId) => `/jobs/${jobId}/review/summary`,
      providesTags: ["Documents"],
    }),
    listReviewDocuments: builder.query<ReviewDocument[], { jobId: string; status?: string }>({
      query: ({ jobId, status }) =>
        `/jobs/${jobId}/review/documents${status ? `?status=${status}` : ""}`,
      providesTags: ["Documents"],
    }),
    getReviewDocument: builder.query<ReviewDocDetail, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => `/jobs/${jobId}/review/documents/${docId}`,
    }),
    submitDecision: builder.mutation<
      { status: string },
      { jobId: string; docId: string; decision: string; notes?: string; content?: string }
    >({
      query: ({ jobId, docId, decision, notes, content }) => ({
        url: `/jobs/${jobId}/review/documents/${docId}/decide`,
        method: "POST",
        body: { decision, reviewer_notes: notes, edited_content: content },
      }),
      invalidatesTags: ["Documents"],
    }),
    batchApprove: builder.mutation<
      { approved_count: number },
      { jobId: string; documentIds: string[]; notes?: string }
    >({
      query: ({ jobId, documentIds, notes }) => ({
        url: `/jobs/${jobId}/review/batch-approve`,
        method: "POST",
        body: { document_ids: documentIds, reviewer_notes: notes },
      }),
      invalidatesTags: ["Documents"],
    }),
    finalizeReview: builder.mutation<
      { status: string; total_documents: number; approved: number; rejected: number },
      string
    >({
      query: (jobId) => ({ url: `/jobs/${jobId}/review/finalize`, method: "POST" }),
      invalidatesTags: ["Jobs", "Documents"],
    }),
    addComment: builder.mutation<
      { id: string },
      { jobId: string; docId: string; lineNumber?: number; content: string }
    >({
      query: ({ jobId, docId, lineNumber, content }) => ({
        url: `/jobs/${jobId}/review/documents/${docId}/comments`,
        method: "POST",
        body: { line_number: lineNumber, content },
      }),
    }),
    resolveComment: builder.mutation<void, { jobId: string; commentId: string }>({
      query: ({ jobId, commentId }) => ({
        url: `/jobs/${jobId}/review/comments/${commentId}/resolve`,
        method: "PATCH",
      }),
    }),
  }),
});

export const {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} = reviewApi;
```

### Step 2: Create Review Dashboard Page

**Create file**: `rag-pipeline/apps/web/src/app/review/[jobId]/page.tsx`

This page shows summary cards, status filter tabs, batch approve, finalize button, and the document list.

```tsx
"use client";

import { use, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
  type ReviewDocument,
} from "@/store/api/review-api";

export default function ReviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: summary } = useGetReviewSummaryQuery(jobId);
  const { data: documents } = useListReviewDocumentsQuery({ jobId, status: statusFilter });
  const [batchApprove, { isLoading: isBatching }] = useBatchApproveMutation();
  const [finalize, { isLoading: isFinalizing }] = useFinalizeReviewMutation();

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!documents) return;
    const pendingIds = documents.filter((d) => d.review_status === "pending").map((d) => d.id);
    setSelectedIds(new Set(pendingIds));
  };

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Human Review</h1>
        <div className="flex gap-2">
          <Button
            variant="default"
            onClick={() => batchApprove({ jobId, documentIds: Array.from(selectedIds) })}
            disabled={selectedIds.size === 0 || isBatching}
          >
            Batch Approve ({selectedIds.size})
          </Button>
          <Button
            variant="default"
            onClick={() => finalize(jobId)}
            disabled={!summary?.all_reviewed || isFinalizing}
          >
            Finalize Review
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-5 gap-4 mb-8">
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold">{summary.total_documents}</p>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-green-600">{summary.approved}</p>
              <p className="text-xs text-muted-foreground">Approved</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{summary.edited}</p>
              <p className="text-xs text-muted-foreground">Edited</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-red-600">{summary.rejected}</p>
              <p className="text-xs text-muted-foreground">Rejected</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-yellow-600">{summary.pending}</p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-4">
        {[undefined, "pending", "approved", "edited", "rejected"].map((filter) => (
          <Button
            key={filter || "all"}
            variant={statusFilter === filter ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(filter)}
          >
            {filter || "All"}
          </Button>
        ))}
        <Button variant="outline" size="sm" onClick={selectAll}>
          Select All Pending
        </Button>
      </div>

      {/* Document List */}
      <div className="space-y-2">
        {documents?.map((doc: ReviewDocument) => (
          <div
            key={doc.id}
            className="flex items-center gap-4 p-4 border rounded-lg hover:bg-accent/50"
          >
            <input
              type="checkbox"
              checked={selectedIds.has(doc.id)}
              onChange={() => toggleSelect(doc.id)}
              className="h-4 w-4"
            />
            <div className="flex-1">
              <p className="font-medium">{doc.title || doc.url}</p>
              <p className="text-xs text-muted-foreground">{doc.url}</p>
            </div>
            <Badge variant={doc.quality_score && doc.quality_score > 70 ? "default" : "secondary"}>
              Score: {doc.quality_score || "N/A"}
            </Badge>
            <Badge
              variant={
                doc.review_status === "approved"
                  ? "default"
                  : doc.review_status === "rejected"
                  ? "destructive"
                  : "secondary"
              }
            >
              {doc.review_status}
            </Badge>
            <a href={`/review/${jobId}/${doc.id}`}>
              <Button variant="outline" size="sm">Review</Button>
            </a>
          </div>
        ))}
      </div>
    </main>
  );
}
```

### Step 3: Create Document Review Page with Monaco Editor

**Create file**: `rag-pipeline/apps/web/src/app/review/[jobId]/[docId]/page.tsx`

This page provides the Monaco editor for inline editing, a diff view tab, a preview tab, approve/reject/edit buttons, and comment threads.

```tsx
"use client";

import { use, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} from "@/store/api/review-api";

// Dynamic import for Monaco to avoid SSR issues
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export default function DocumentReviewPage({
  params,
}: {
  params: Promise<{ jobId: string; docId: string }>;
}) {
  const { jobId, docId } = use(params);
  const { data: doc, refetch } = useGetReviewDocumentQuery({ jobId, docId });
  const [submitDecision] = useSubmitDecisionMutation();
  const [addComment] = useAddCommentMutation();
  const [resolveComment] = useResolveCommentMutation();

  const [editedContent, setEditedContent] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [newComment, setNewComment] = useState("");

  const handleApprove = useCallback(async () => {
    await submitDecision({ jobId, docId, decision: "approved", notes });
    refetch();
  }, [jobId, docId, notes, submitDecision, refetch]);

  const handleReject = useCallback(async () => {
    await submitDecision({ jobId, docId, decision: "rejected", notes });
    refetch();
  }, [jobId, docId, notes, submitDecision, refetch]);

  const handleSaveEdits = useCallback(async () => {
    if (editedContent) {
      await submitDecision({
        jobId,
        docId,
        decision: "edited",
        notes,
        content: editedContent,
      });
      refetch();
    }
  }, [jobId, docId, editedContent, notes, submitDecision, refetch]);

  const handleAddComment = useCallback(async () => {
    if (newComment.trim()) {
      await addComment({ jobId, docId, content: newComment });
      setNewComment("");
      refetch();
    }
  }, [jobId, docId, newComment, addComment, refetch]);

  if (!doc) return <p className="p-8">Loading...</p>;

  return (
    <main className="container mx-auto p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{doc.title || "Untitled Document"}</h1>
          <p className="text-sm text-muted-foreground">{doc.url}</p>
        </div>
        <div className="flex items-center gap-2">
          {doc.review_decision && (
            <Badge variant={doc.review_decision.decision === "approved" ? "default" : "destructive"}>
              {doc.review_decision.decision}
            </Badge>
          )}
          <Badge variant="secondary">Score: {doc.quality_score || "N/A"}</Badge>
          {doc.has_changes && <Badge variant="default">Modified by Agent</Badge>}
        </div>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="editor">
        <TabsList>
          <TabsTrigger value="editor">Editor</TabsTrigger>
          <TabsTrigger value="diff">Diff View</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="editor" className="border rounded-lg">
          <Editor
            height="500px"
            defaultLanguage="markdown"
            value={editedContent ?? doc.current_markdown}
            onChange={(value) => setEditedContent(value || "")}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              wordWrap: "on",
              lineNumbers: "on",
              fontSize: 14,
            }}
          />
        </TabsContent>

        <TabsContent value="diff">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold mb-2 text-sm">Original</h3>
              <pre className="bg-muted p-4 rounded text-xs max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                {doc.original_markdown}
              </pre>
            </div>
            <div>
              <h3 className="font-semibold mb-2 text-sm">Current - Agent-Corrected</h3>
              <pre className="bg-muted p-4 rounded text-xs max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                {doc.current_markdown}
              </pre>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="preview" className="prose max-w-none p-4 max-h-[500px] overflow-y-auto">
          {/* Use dangerouslySetInnerHTML or react-markdown for preview */}
          <pre className="whitespace-pre-wrap">{doc.current_markdown}</pre>
        </TabsContent>
      </Tabs>

      {/* Review Actions */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Review Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <Input
              placeholder="Reviewer notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="flex gap-2">
              <Button variant="default" onClick={handleApprove}>
                ✓ Approve
              </Button>
              <Button variant="destructive" onClick={handleReject}>
                ✗ Reject
              </Button>
              <Button
                variant="secondary"
                onClick={handleSaveEdits}
                disabled={!editedContent}
              >
                💾 Save Edits & Approve
              </Button>
              <a href={`/review/${jobId}`}>
                <Button variant="outline">← Back to List</Button>
              </a>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comments */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Comments ({doc.comments.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 mb-4">
            {doc.comments.map((comment) => (
              <div
                key={comment.id}
                className={`p-3 border rounded ${comment.resolved ? "opacity-50" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{comment.author}</span>
                    {comment.line_number && (
                      <Badge variant="secondary" className="text-xs">
                        Line {comment.line_number}
                      </Badge>
                    )}
                  </div>
                  {!comment.resolved && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => resolveComment({ jobId, commentId: comment.id })}
                    >
                      Resolve
                    </Button>
                  )}
                </div>
                <p className="text-sm mt-1">{comment.content}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Add a comment..."
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddComment()}
            />
            <Button onClick={handleAddComment} disabled={!newComment.trim()}>
              Comment
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
```

### Step 4: Add Navigation Link

**Modify file**: `rag-pipeline/apps/web/src/app/layout.tsx`

Add a "Review" link to the existing navigation bar:

```tsx
<a href="/review" className="text-sm hover:underline">Review</a>
```

Place this alongside the existing nav links in the layout header/nav component.

---

## Done-When Checklist

- [ ] Review dashboard shows summary cards with counts for total/approved/edited/rejected/pending
- [ ] Status filter tabs work — clicking "pending" shows only pending documents
- [ ] Batch approve button sends selected document IDs to the API
- [ ] Finalize button is disabled until `all_reviewed` is true
- [ ] Document review page renders Monaco editor with Markdown syntax highlighting
- [ ] Diff view shows side-by-side original vs current content
- [ ] Preview tab renders the current Markdown content
- [ ] Approve/Reject/Edit buttons call the correct API endpoints
- [ ] Comment threads can be created and resolved
- [ ] Navigation link to `/review` exists in the layout

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-5-subtask-2-review-dashboard-ui-summary.md`

The summary report must include:
- **Subtask**: Phase 5, Subtask 2 — Review Dashboard UI
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
