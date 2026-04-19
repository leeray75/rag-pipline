# Phase 1, Subtask 3 — Next.js Frontend Scaffold + Shared Pydantic Schemas

> **Phase**: Phase 1 — Foundation
> **Subtask**: 3 of 5
> **Prerequisites**: Subtask 1 (Mono-Repo Init) and Subtask 2 (FastAPI + Database) must be complete
> **Scope**: ~12 files to create in `apps/web/`, 3 files in `apps/api/src/schemas/`

---

## Context

This subtask scaffolds the Next.js frontend at `apps/web/` with shadcn/ui, Redux Toolkit, and RTK Query, then creates the shared Pydantic schemas in the API backend. It combines Task 4 (Next.js scaffold) and Task 8 (shared Pydantic schemas) from the parent phase.

**Project Root**: `rag-pipeline/`

The mono-repo structure from Subtask 1 places the frontend at `rag-pipeline/apps/web/` within the pnpm workspace.

---

## Relevant Technology Stack

| Package | Version | Install |
|---|---|---|
| Next.js | 16.2.3 | `npx create-next-app@latest` |
| React | 19.2.5 | Bundled with Next.js |
| Redux Toolkit | 2.11.2 | `pnpm add @reduxjs/toolkit react-redux` |
| TailwindCSS | 4.2.2 | Bundled with create-next-app `--tailwind` |
| shadcn/ui | latest | `npx shadcn@latest init` |
| Vitest | 3.x | `pnpm add -D vitest` |
| Node.js | 22.x | Runtime |
| pnpm | 9.15.0 | Package manager |
| Pydantic | 2.13.0 | Already installed in Subtask 2 |

---

## Step-by-Step Implementation — Part A: Next.js Frontend

**Working directory**: `rag-pipeline/apps/`

### Step 1: Create Next.js app

```bash
cd rag-pipeline/apps
npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --use-pnpm
```

### Step 2: Install additional dependencies

```bash
cd rag-pipeline/apps/web
pnpm add @reduxjs/toolkit react-redux
pnpm add -D vitest @testing-library/react @testing-library/jest-dom
```

### Step 3: Initialize shadcn/ui

```bash
cd rag-pipeline/apps/web
npx shadcn@latest init
```

When prompted:
- Style: **New York**
- Base color: **Neutral**
- CSS variables: **Yes**

### Step 4: Add initial shadcn components

```bash
npx shadcn@latest add button card input badge tabs separator
```

### Step 5: Create Redux store — `src/store/store.ts`

Create file `rag-pipeline/apps/web/src/store/store.ts`:

```typescript
import { configureStore } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";
import { apiSlice } from "./api/api-slice";

export const store = configureStore({
  reducer: {
    [apiSlice.reducerPath]: apiSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(apiSlice.middleware),
});

setupListeners(store.dispatch);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
```

### Step 6: Create RTK Query base API — `src/store/api/api-slice.ts`

Create file `rag-pipeline/apps/web/src/store/api/api-slice.ts`:

```typescript
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

export const apiSlice = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  }),
  tagTypes: ["Jobs", "Documents", "AuditReports"],
  endpoints: () => ({}),
});
```

### Step 7: Create Redux hooks — `src/store/hooks.ts`

Create file `rag-pipeline/apps/web/src/store/hooks.ts`:

```typescript
import { useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "./store";

export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
```

### Step 8: Create store provider — `src/store/provider.tsx`

Create file `rag-pipeline/apps/web/src/store/provider.tsx`:

```tsx
"use client";

import { Provider } from "react-redux";
import { store } from "./store";

export function StoreProvider({ children }: { children: React.ReactNode }) {
  return <Provider store={store}>{children}</Provider>;
}
```

### Step 9: Update `src/app/layout.tsx`

Replace the contents of `rag-pipeline/apps/web/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "@/store/provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RAG Pipeline Dashboard",
  description: "AI Knowledge Base RAG Ingestion Pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  );
}
```

### Step 10: Create placeholder home page — `src/app/page.tsx`

Replace the contents of `rag-pipeline/apps/web/src/app/page.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">RAG Pipeline Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Ingestion Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">No jobs yet. Submit a URL to get started.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Documents will appear after crawling.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Vector Collections</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Collections will appear after ingestion.</p>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
```

### Step 11: Create `.env.local`

Create file `rag-pipeline/apps/web/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Step-by-Step Implementation — Part B: Shared Pydantic Schemas

**Working directory**: `rag-pipeline/apps/api/`

### Step 12: Create `src/schemas/job.py`

Create file `rag-pipeline/apps/api/src/schemas/job.py`:

```python
"""Pydantic schemas for ingestion jobs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class JobCreate(BaseModel):
    """Schema for creating a new ingestion job."""

    url: HttpUrl
    crawl_all_docs: bool = False


class JobResponse(BaseModel):
    """Schema for job API responses."""

    id: uuid.UUID
    url: str
    status: str
    crawl_all_docs: bool
    total_documents: int
    processed_documents: int
    current_audit_round: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    """Lightweight job status for polling."""

    id: uuid.UUID
    status: str
    total_documents: int
    processed_documents: int
    current_audit_round: int
```

### Step 13: Create `src/schemas/document.py`

Create file `rag-pipeline/apps/api/src/schemas/document.py`:

```python
"""Pydantic schemas for documents."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Schema for document API responses."""

    id: uuid.UUID
    job_id: uuid.UUID
    url: str
    title: str | None
    status: str
    word_count: int | None
    quality_score: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Step 14: Update `src/schemas/__init__.py`

Replace the empty `rag-pipeline/apps/api/src/schemas/__init__.py` with:

```python
"""Pydantic schemas package."""

from src.schemas.document import DocumentResponse
from src.schemas.job import JobCreate, JobResponse, JobStatusResponse

__all__ = [
    "DocumentResponse",
    "JobCreate",
    "JobResponse",
    "JobStatusResponse",
]
```

---

## Files to Create/Modify

| # | File Path | Action |
|---|---|---|
| 1 | `apps/web/` (entire scaffold) | Create via create-next-app |
| 2 | `apps/web/src/store/store.ts` | Create |
| 3 | `apps/web/src/store/hooks.ts` | Create |
| 4 | `apps/web/src/store/provider.tsx` | Create |
| 5 | `apps/web/src/store/api/api-slice.ts` | Create |
| 6 | `apps/web/src/app/layout.tsx` | Modify (replace) |
| 7 | `apps/web/src/app/page.tsx` | Modify (replace) |
| 8 | `apps/web/.env.local` | Create |
| 9 | `apps/web/src/components/ui/*.tsx` | Create (via shadcn add) |
| 10 | `apps/api/src/schemas/job.py` | Create |
| 11 | `apps/api/src/schemas/document.py` | Create |
| 12 | `apps/api/src/schemas/__init__.py` | Modify (replace empty) |

All paths relative to `rag-pipeline/`.

---

## Done-When Checklist

- [ ] `apps/web/package.json` exists with Next.js, Redux Toolkit, and Vitest dependencies
- [ ] `pnpm dev` starts Next.js at `http://localhost:3000` (from `apps/web/`)
- [ ] Dashboard displays 3 placeholder cards (Ingestion Jobs, Documents, Vector Collections)
- [ ] shadcn/ui components are installed (button, card, input, badge, tabs, separator)
- [ ] Redux store is configured with RTK Query base API slice
- [ ] `StoreProvider` wraps the app in `layout.tsx`
- [ ] `.env.local` sets `NEXT_PUBLIC_API_URL`
- [ ] `python -c "from src.schemas import JobCreate, JobResponse, JobStatusResponse, DocumentResponse"` succeeds (from `apps/api/`)
- [ ] All schema exports are present in `src/schemas/__init__.py`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-1-subtask-3-nextjs-and-schemas-summary.md`

The summary report must include:
- **Subtask**: Phase 1, Subtask 3 — Next.js Frontend Scaffold + Shared Pydantic Schemas
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
