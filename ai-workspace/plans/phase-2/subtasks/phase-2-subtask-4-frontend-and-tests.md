# Phase 2, Subtask 4 — Frontend Staging Browser UI + Tests

> **Phase**: Phase 2 — Crawl & Convert
> **Prerequisites**: Phase 1 complete + Phase 2 Subtasks 1–3 complete (all backend services, Celery tasks, API router, and WebSocket endpoint created)
> **Scope**: 6 files to create, 2 files to modify

---

## Relevant Technology Stack

| Package | Pinned Version | Purpose |
|---|---|---|
| Next.js | 16.2.3 | React framework |
| React | 19.2.5 | UI library |
| Redux Toolkit | 2.11.2 | State management + RTK Query |
| TailwindCSS | 4.2.2 | Utility CSS |
| shadcn/ui | latest | UI component library |
| react-markdown | (latest) | Markdown preview rendering |
| remark-gfm | (latest) | GitHub Flavored Markdown support |
| @monaco-editor/react | (latest) | Code editor for raw content |
| react-split-pane | (latest) | Split panel layout |
| Vitest | 3.x | Frontend test runner |
| pytest | (latest) | Python test runner |

---

## Step 1: Install Additional UI Dependencies

**Working directory**: `rag-pipeline/apps/web/`

```bash
pnpm add @monaco-editor/react react-split-pane react-markdown remark-gfm
```

---

## Step 2: Create RTK Query Endpoints

**Working directory**: `rag-pipeline/apps/web/`

### 2.1 Create `src/store/api/jobs-api.ts`

This file extends the existing RTK Query `apiSlice` (created in Phase 1) with job and document endpoints.

```typescript
import { apiSlice } from "./api-slice";

export interface Job {
  id: string;
  url: string;
  status: string;
  crawl_all_docs: boolean;
  total_documents: number;
  processed_documents: number;
  current_audit_round: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  job_id: string;
  url: string;
  title: string | null;
  status: string;
  word_count: number | null;
  quality_score: number | null;
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  raw_html: string | null;
  markdown: string | null;
}

export const jobsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    createJob: builder.mutation<Job, { url: string; crawl_all_docs: boolean }>({
      query: (body) => ({ url: "/jobs", method: "POST", body }),
      invalidatesTags: ["Jobs"],
    }),
    getJob: builder.query<Job, string>({
      query: (id) => `/jobs/${id}`,
      providesTags: (result, error, id) => [{ type: "Jobs", id }],
    }),
    getJobStatus: builder.query<Job, string>({
      query: (id) => `/jobs/${id}/status`,
    }),
    listDocuments: builder.query<DocumentItem[], string>({
      query: (jobId) => `/jobs/${jobId}/documents`,
      providesTags: ["Documents"],
    }),
    getDocument: builder.query<DocumentDetail, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => `/jobs/${jobId}/documents/${docId}`,
    }),
    deleteDocument: builder.mutation<void, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => ({
        url: `/jobs/${jobId}/documents/${docId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Documents"],
    }),
  }),
});

export const {
  useCreateJobMutation,
  useGetJobQuery,
  useGetJobStatusQuery,
  useListDocumentsQuery,
  useGetDocumentQuery,
  useDeleteDocumentMutation,
} = jobsApi;
```

**Note**: The `apiSlice` from `./api-slice` must already have `"Jobs"` and `"Documents"` in its `tagTypes` array. If not, add them to the existing `apiSlice` definition.

---

## Step 3: Create the Ingestion Page

**Working directory**: `rag-pipeline/apps/web/`

### 3.1 Create `src/app/ingestion/page.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useCreateJobMutation } from "@/store/api/jobs-api";

export default function IngestionPage() {
  const [url, setUrl] = useState("");
  const [crawlAll, setCrawlAll] = useState(false);
  const [createJob, { isLoading, data: job }] = useCreateJobMutation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    await createJob({ url: url.trim(), crawl_all_docs: crawlAll });
  };

  return (
    <main className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">URL Ingestion</h1>

      {/* URL Input Form */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Submit Documentation URL</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              type="url"
              placeholder="https://docs.example.com/getting-started"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="crawlAll"
                checked={crawlAll}
                onChange={(e) => setCrawlAll(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="crawlAll" className="text-sm">
                Crawl All Documentation Pages
              </label>
            </div>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Submitting..." : "Start Ingestion"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Job Status */}
      {job && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Job Created <Badge variant="secondary">{job.status}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Job ID: {job.id}</p>
            <p className="text-sm">URL: {job.url}</p>
            <p className="text-sm">
              Progress: {job.processed_documents} / {job.total_documents} documents
            </p>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
```

---

## Step 4: Create the Staging Browser Component

**Working directory**: `rag-pipeline/apps/web/`

### 4.1 Create `src/features/staging/staging-browser.tsx`

```tsx
"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useListDocumentsQuery,
  useGetDocumentQuery,
  useDeleteDocumentMutation,
  type DocumentItem,
} from "@/store/api/jobs-api";

interface StagingBrowserProps {
  jobId: string;
}

export function StagingBrowser({ jobId }: StagingBrowserProps) {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const { data: documents, isLoading } = useListDocumentsQuery(jobId);
  const { data: docDetail } = useGetDocumentQuery(
    { jobId, docId: selectedDocId! },
    { skip: !selectedDocId }
  );
  const [deleteDoc] = useDeleteDocumentMutation();

  if (isLoading) return <p>Loading documents...</p>;
  if (!documents?.length) return <p>No documents found for this job.</p>;

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Document List Panel */}
      <div className="col-span-4 border rounded-lg p-4 max-h-[80vh] overflow-y-auto">
        <h3 className="font-semibold mb-4">
          Documents ({documents.length})
        </h3>
        {documents.map((doc: DocumentItem) => (
          <div
            key={doc.id}
            className={`p-3 rounded cursor-pointer mb-2 border ${
              selectedDocId === doc.id ? "border-primary bg-accent" : "hover:bg-accent/50"
            }`}
            onClick={() => setSelectedDocId(doc.id)}
          >
            <p className="text-sm font-medium truncate">{doc.title || doc.url}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={doc.status === "converted" ? "default" : "destructive"}>
                {doc.status}
              </Badge>
              {doc.word_count && (
                <span className="text-xs text-muted-foreground">
                  {doc.word_count} words
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Document Viewer Panel */}
      <div className="col-span-8">
        {docDetail ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{docDetail.title || "Untitled"}</CardTitle>
              <p className="text-sm text-muted-foreground">{docDetail.url}</p>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="markdown">
                <TabsList>
                  <TabsTrigger value="markdown">Markdown Preview</TabsTrigger>
                  <TabsTrigger value="raw">Raw Markdown</TabsTrigger>
                  <TabsTrigger value="html">Source HTML</TabsTrigger>
                </TabsList>
                <TabsContent value="markdown" className="prose max-w-none max-h-[60vh] overflow-y-auto">
                  {docDetail.markdown && (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {docDetail.markdown}
                    </ReactMarkdown>
                  )}
                </TabsContent>
                <TabsContent value="raw">
                  <pre className="bg-muted p-4 rounded text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {docDetail.markdown || "No markdown content"}
                  </pre>
                </TabsContent>
                <TabsContent value="html">
                  <pre className="bg-muted p-4 rounded text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {docDetail.raw_html || "No HTML content"}
                  </pre>
                </TabsContent>
              </Tabs>
              <div className="flex gap-2 mt-4">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    deleteDoc({ jobId, docId: docDetail.id });
                    setSelectedDocId(null);
                  }}
                >
                  Remove Document
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="flex items-center justify-center h-64 border rounded-lg">
            <p className="text-muted-foreground">Select a document to view</p>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

## Step 5: Create the WebSocket Progress Hook

**Working directory**: `rag-pipeline/apps/web/`

### 5.1 Create `src/hooks/use-job-progress.ts`

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface ProgressEvent {
  type: string;
  job_id: string;
  total?: number;
  completed?: number;
  current_url?: string;
  message?: string;
}

export function useJobProgress(jobId: string | null) {
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!jobId) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/api/v1/ws/jobs/${jobId}/stream`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => {
      setIsConnected(false);
      // Reconnect after 3 seconds
      setTimeout(() => connect(), 3000);
    };
    ws.onmessage = (event) => {
      try {
        const data: ProgressEvent = JSON.parse(event.data);
        setProgress(data);
      } catch {
        // ignore non-JSON messages
      }
    };

    wsRef.current = ws;
  }, [jobId]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { progress, isConnected };
}
```

---

## Step 6: Add Navigation Link in Layout

**Working directory**: `rag-pipeline/apps/web/`

Update `src/app/layout.tsx` to include navigation links. Add inside `<body>` before `{children}`:

```tsx
<nav className="border-b">
  <div className="container mx-auto flex items-center gap-6 p-4">
    <a href="/" className="font-bold text-lg">RAG Pipeline</a>
    <a href="/ingestion" className="text-sm hover:underline">Ingestion</a>
    <a href="/staging" className="text-sm hover:underline">Staging</a>
  </div>
</nav>
```

---

## Step 7: Write Phase 2 Python Tests

**Working directory**: `rag-pipeline/apps/api/`

### 7.1 Create `tests/test_converter.py`

```python
"""Tests for the Markdown converter."""

from src.converters.markdown_converter import convert_html_to_markdown


def test_basic_html_conversion():
    """Simple HTML converts to Markdown with frontmatter."""
    html = "<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>World</p></body></html>"
    result = convert_html_to_markdown(html, "https://example.com/test")
    assert result.error is None
    assert "---" in result.markdown  # frontmatter present
    assert "title:" in result.markdown
    assert "source_url:" in result.markdown
    assert result.word_count > 0


def test_sanitization_removes_scripts():
    """Script tags should be removed before conversion."""
    html = '<html><body><h1>Hi</h1><script>alert("xss")</script><p>Content</p></body></html>'
    result = convert_html_to_markdown(html, "https://example.com")
    assert "alert" not in result.markdown
    assert "script" not in result.markdown.lower()


def test_empty_html_returns_error():
    """Empty HTML should still return a result without crashing."""
    result = convert_html_to_markdown("", "https://example.com")
    # Should not raise, may have error or minimal content
    assert result is not None
```

### 7.2 Create `tests/test_link_discovery.py`

```python
"""Tests for link discovery."""

from src.crawlers.link_discovery import extract_links_with_selectors


def test_extracts_nav_links():
    """Should extract links from nav elements."""
    html = """
    <html><body>
    <nav>
        <a href="/docs/intro">Introduction</a>
        <a href="/docs/guide">Guide</a>
        <a href="https://external.com">External</a>
    </nav>
    </body></html>
    """
    links = extract_links_with_selectors(html, "https://example.com")
    hrefs = [l.href for l in links]
    assert "https://example.com/docs/intro" in hrefs
    assert "https://example.com/docs/guide" in hrefs
    # External link should be excluded
    assert not any("external.com" in h for h in hrefs)


def test_deduplicates_links():
    """Duplicate links should be removed."""
    html = """
    <html><body>
    <nav>
        <a href="/docs/intro">Intro</a>
        <a href="/docs/intro">Introduction</a>
    </nav>
    </body></html>
    """
    links = extract_links_with_selectors(html, "https://example.com")
    hrefs = [l.href for l in links]
    assert hrefs.count("https://example.com/docs/intro") == 1
```

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| **Create** | `rag-pipeline/apps/web/src/store/api/jobs-api.ts` |
| **Create** | `rag-pipeline/apps/web/src/app/ingestion/page.tsx` |
| **Create** | `rag-pipeline/apps/web/src/features/staging/staging-browser.tsx` |
| **Create** | `rag-pipeline/apps/web/src/hooks/use-job-progress.ts` |
| **Modify** | `rag-pipeline/apps/web/src/app/layout.tsx` (add nav links) |
| **Modify** | `rag-pipeline/apps/web/src/store/api/api-slice.ts` (add `"Jobs"`, `"Documents"` to tagTypes if missing) |
| **Create** | `rag-pipeline/apps/api/tests/test_converter.py` |
| **Create** | `rag-pipeline/apps/api/tests/test_link_discovery.py` |

---

## Done-When Checklist

- [ ] Next.js `/ingestion` page renders with URL input form and crawl toggle
- [ ] Staging browser component renders document list and preview panels
- [ ] `useJobProgress` hook connects to WebSocket and receives progress events
- [ ] Navigation bar shows links to Ingestion and Staging pages
- [ ] `pytest tests/ -v` passes all tests including converter and link discovery
- [ ] `test_basic_html_conversion` passes — Markdown output contains frontmatter
- [ ] `test_sanitization_removes_scripts` passes — no script content in output
- [ ] `test_extracts_nav_links` passes — same-origin nav links extracted, external excluded
- [ ] `test_deduplicates_links` passes — duplicate URLs collapsed to one entry

---

## Phase 2 Final Done-When Checklist

After all 4 subtasks are complete, verify the full Phase 2 checklist:

- [ ] `POST /api/v1/jobs` with `{"url": "https://example.com", "crawl_all_docs": false}` returns 201
- [ ] Submitting `https://modelcontextprotocol.io/introduction` fetches and converts that page to Markdown
- [ ] With `crawl_all_docs: true`, the link discovery service finds related documentation pages
- [ ] Celery task chain executes: fetch → discover → fan-out convert → finalize
- [ ] Staging directory contains `html/` and `markdown/` files after a crawl
- [ ] `GET /api/v1/jobs/{id}/documents` returns the list of converted documents
- [ ] `GET /api/v1/jobs/{id}/documents/{doc_id}` returns Markdown + HTML content
- [ ] WebSocket endpoint at `/api/v1/ws/jobs/{id}/stream` accepts connections
- [ ] Next.js `/ingestion` page renders with URL input form and crawl toggle
- [ ] Staging browser component renders document list and preview panels
- [ ] All Markdown files have valid YAML frontmatter with `title`, `source_url`, `fetched_at`
- [ ] `pytest tests/ -v` passes all tests including converter and link discovery

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-2-subtask-4-frontend-and-tests-summary.md`

The summary report must include:
- **Subtask**: Phase 2, Subtask 4 — Frontend Staging Browser UI + Tests
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
