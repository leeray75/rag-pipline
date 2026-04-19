# Phase 6, Subtask 4 — RTK Query + Chunk Browser UI + Embed-to-Qdrant UI

> **Phase**: Phase 6 — JSON Generation, Chunking & Vector Ingestion
> **Prerequisites**: Phase 5 complete + Phase 6 Subtasks 1–3 complete (all backend services, API router, Celery tasks working)
> **Subtask Scope**: Tasks 10–12 from Phase 6 (ingestApi.ts RTK Query slice, ChunkBrowser.tsx, EmbedToQdrant.tsx)

---

## Files to Create / Modify

| Action | File Path |
|--------|-----------|
| Create | `rag-pipeline/apps/web/src/store/ingestApi.ts` |
| Modify | `rag-pipeline/apps/web/src/store/store.ts` |
| Create | `rag-pipeline/apps/web/src/features/ingest/ChunkBrowser.tsx` |
| Create | `rag-pipeline/apps/web/src/features/ingest/EmbedToQdrant.tsx` |

---

## Relevant Technology Stack

| Package | Version | Notes |
|---------|---------|-------|
| Next.js | 16.2.3 | App Router |
| React | 19.2.5 | UI framework |
| Redux Toolkit | 2.11.2 | RTK Query for API |
| TailwindCSS | 4.2.2 | Styling |

---

## Context: Backend API Endpoints

These endpoints were created in Subtask 3 and are consumed here:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ingest/jobs/{jobId}/chunk` | Start chunking task |
| GET | `/api/v1/ingest/jobs/{jobId}/chunks?offset=N&limit=N` | List chunks paginated |
| GET | `/api/v1/ingest/jobs/{jobId}/chunks/{chunkId}` | Get single chunk |
| GET | `/api/v1/ingest/jobs/{jobId}/chunk-stats` | Get chunk statistics |
| POST | `/api/v1/ingest/jobs/{jobId}/embed` | Start embedding task |
| WS | `/api/v1/ingest/jobs/{jobId}/embed/ws?collection=NAME` | Embed progress stream |
| GET | `/api/v1/ingest/collections` | List all collections |
| GET | `/api/v1/ingest/collections/{name}/stats` | Collection stats |
| POST | `/api/v1/ingest/collections/{name}/search?query=TEXT&limit=N` | Similarity search |

---

## Step-by-Step Implementation

### Task 10: Create the RTK Query Ingest API Slice

**Working directory**: `rag-pipeline/apps/web/`

#### 10.1 Create `src/store/ingestApi.ts`

```typescript
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// ---- Types ----

export interface ChunkMetadata {
  source_url: string;
  title: string;
  description: string;
  tags: string[];
  heading_path: string;
  fetched_at: string | null;
  approved_at: string | null;
  audit_rounds: number;
  quality_score: number;
}

export interface ChunkDocument {
  id: string;
  document_id: string;
  job_id: string;
  chunk_index: number;
  total_chunks: number;
  content: string;
  token_count: number;
  metadata: ChunkMetadata;
}

export interface ChunkStats {
  job_id: string;
  total_chunks: number;
  avg_token_count: number;
  min_token_count: number;
  max_token_count: number;
  total_tokens: number;
  token_histogram: number[];
}

export interface EmbedRequest {
  job_id: string;
  collection_name: string;
  model_name?: string;
}

export interface EmbedProgress {
  job_id: string;
  phase: string;
  current: number;
  total: number;
  message: string;
}

export interface CollectionInfo {
  id: string;
  job_id: string;
  collection_name: string;
  embedding_model: string;
  vector_dimensions: number;
  vector_count: number;
  document_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CollectionStats {
  collection_name: string;
  vector_count: number;
  indexed_vectors: number;
  points_count: number;
  segments_count: number;
  disk_data_size_bytes: number;
  ram_data_size_bytes: number;
  status: string;
}

export interface SearchResult {
  id: string;
  score: number;
  content_preview: string;
  heading_path: string;
  source_url: string;
}

// ---- API Slice ----

export const ingestApi = createApi({
  reducerPath: "ingestApi",
  baseQuery: fetchBaseQuery({ baseUrl: "/api/v1/ingest" }),
  tagTypes: ["Chunks", "ChunkStats", "Collections"],
  endpoints: (builder) => ({
    // Chunking
    startChunking: builder.mutation<{ task_id: string }, string>({
      query: (jobId) => ({
        url: `/jobs/${jobId}/chunk`,
        method: "POST",
      }),
      invalidatesTags: ["Chunks", "ChunkStats"],
    }),

    listChunks: builder.query<
      ChunkDocument[],
      { jobId: string; offset?: number; limit?: number }
    >({
      query: ({ jobId, offset = 0, limit = 50 }) =>
        `/jobs/${jobId}/chunks?offset=${offset}&limit=${limit}`,
      providesTags: ["Chunks"],
    }),

    getChunk: builder.query<
      ChunkDocument,
      { jobId: string; chunkId: string }
    >({
      query: ({ jobId, chunkId }) => `/jobs/${jobId}/chunks/${chunkId}`,
    }),

    getChunkStats: builder.query<ChunkStats, string>({
      query: (jobId) => `/jobs/${jobId}/chunk-stats`,
      providesTags: ["ChunkStats"],
    }),

    // Embedding
    startEmbedding: builder.mutation<
      { task_id: string; collection_name: string },
      EmbedRequest
    >({
      query: (body) => ({
        url: `/jobs/${body.job_id}/embed`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Collections"],
    }),

    // Collections
    listCollections: builder.query<CollectionInfo[], void>({
      query: () => "/collections",
      providesTags: ["Collections"],
    }),

    getCollectionStats: builder.query<CollectionStats, string>({
      query: (name) => `/collections/${name}/stats`,
    }),

    similaritySearch: builder.mutation<
      SearchResult[],
      { name: string; query: string; limit?: number }
    >({
      query: ({ name, query, limit = 5 }) => ({
        url: `/collections/${name}/search?query=${encodeURIComponent(query)}&limit=${limit}`,
        method: "POST",
      }),
    }),
  }),
});

export const {
  useStartChunkingMutation,
  useListChunksQuery,
  useGetChunkQuery,
  useGetChunkStatsQuery,
  useStartEmbeddingMutation,
  useListCollectionsQuery,
  useGetCollectionStatsQuery,
  useSimilaritySearchMutation,
} = ingestApi;
```

#### 10.2 Register in the Redux store

In `src/store/store.ts`, add:

```typescript
import { ingestApi } from "./ingestApi";

export const store = configureStore({
  reducer: {
    // ... existing reducers ...
    [ingestApi.reducerPath]: ingestApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      // ... existing middleware ...
      .concat(ingestApi.middleware),
});
```

---

### Task 11: Build the Chunk Browser UI

**Working directory**: `rag-pipeline/apps/web/`

#### 11.1 Create `src/features/ingest/ChunkBrowser.tsx`

```tsx
"use client";

import { useState } from "react";
import {
  useListChunksQuery,
  useGetChunkStatsQuery,
  type ChunkDocument,
} from "@/store/ingestApi";

interface ChunkBrowserProps {
  jobId: string;
}

export function ChunkBrowser({ jobId }: ChunkBrowserProps) {
  const [page, setPage] = useState(0);
  const pageSize = 25;

  const { data: chunks = [], isLoading } = useListChunksQuery({
    jobId,
    offset: page * pageSize,
    limit: pageSize,
  });

  const { data: stats } = useGetChunkStatsQuery(jobId);

  const [selectedChunk, setSelectedChunk] = useState<ChunkDocument | null>(
    null
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Stats summary */}
      {stats && <ChunkStatsCards stats={stats} />}

      {/* Chunk table */}
      <div className="lg:col-span-2">
        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold">
              Chunks ({stats?.total_chunks ?? 0})
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">Heading Path</th>
                  <th className="px-4 py-2 text-left">Content Preview</th>
                  <th className="px-4 py-2 text-right">Tokens</th>
                  <th className="px-4 py-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {chunks.map((chunk) => (
                  <tr
                    key={chunk.id}
                    className="border-t border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800 cursor-pointer"
                    onClick={() => setSelectedChunk(chunk)}
                  >
                    <td className="px-4 py-2 font-mono text-xs">
                      {chunk.chunk_index}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500 max-w-[200px] truncate">
                      {chunk.metadata.heading_path || "—"}
                    </td>
                    <td className="px-4 py-2 max-w-[300px] truncate">
                      {chunk.content.slice(0, 120)}...
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {chunk.token_count}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <TokenBadge count={chunk.token_count} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="flex justify-between items-center px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 rounded bg-gray-200 dark:bg-gray-700 disabled:opacity-50"
            >
              ← Prev
            </button>
            <span className="text-sm text-gray-500">Page {page + 1}</span>
            <button
              disabled={chunks.length < pageSize}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 rounded bg-gray-200 dark:bg-gray-700 disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Chunk inspector sidebar */}
      <div className="lg:col-span-1">
        {selectedChunk ? (
          <ChunkInspector chunk={selectedChunk} />
        ) : (
          <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 text-center text-gray-400">
            Click a chunk to inspect
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Sub-components ----

function ChunkStatsCards({ stats }: { stats: import("@/store/ingestApi").ChunkStats }) {
  const bucketLabels = [
    "0-128",
    "128-256",
    "256-384",
    "384-512",
    "512-768",
    "768-1024",
    "1024+",
  ];

  return (
    <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="Total Chunks" value={stats.total_chunks} />
      <StatCard
        label="Avg Tokens"
        value={Math.round(stats.avg_token_count)}
      />
      <StatCard label="Min Tokens" value={stats.min_token_count} />
      <StatCard label="Max Tokens" value={stats.max_token_count} />

      {/* Histogram */}
      <div className="col-span-2 md:col-span-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h4 className="text-sm font-medium mb-3">Token Distribution</h4>
        <div className="flex items-end gap-2 h-24">
          {stats.token_histogram.map((count, i) => {
            const max = Math.max(...stats.token_histogram, 1);
            const height = (count / max) * 100;
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-xs text-gray-500">{count}</span>
                <div
                  className="w-full bg-blue-500 rounded-t"
                  style={{ height: `${height}%`, minHeight: count > 0 ? 4 : 0 }}
                />
                <span className="text-[10px] text-gray-400">
                  {bucketLabels[i]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value.toLocaleString()}</p>
    </div>
  );
}

function TokenBadge({ count }: { count: number }) {
  const color =
    count <= 512
      ? "bg-green-100 text-green-700"
      : count <= 1024
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-100 text-red-700";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {count <= 512 ? "OK" : count <= 1024 ? "Long" : "Over"}
    </span>
  );
}

function ChunkInspector({ chunk }: { chunk: ChunkDocument }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
        <h3 className="text-sm font-semibold">
          Chunk #{chunk.chunk_index} of {chunk.total_chunks}
        </h3>
        <p className="text-xs text-gray-500 mt-1 font-mono">{chunk.id}</p>
      </div>

      {/* Metadata */}
      <div className="p-4 space-y-3 text-sm">
        <MetaRow label="Heading" value={chunk.metadata.heading_path} />
        <MetaRow label="Source" value={chunk.metadata.source_url} />
        <MetaRow label="Title" value={chunk.metadata.title} />
        <MetaRow
          label="Tags"
          value={chunk.metadata.tags.join(", ") || "—"}
        />
        <MetaRow label="Tokens" value={String(chunk.token_count)} />
        <MetaRow
          label="Quality"
          value={`${chunk.metadata.quality_score}%`}
        />
        <MetaRow
          label="Audit Rounds"
          value={String(chunk.metadata.audit_rounds)}
        />
      </div>

      {/* Content */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <h4 className="text-xs font-medium text-gray-500 mb-2">Content</h4>
        <pre className="text-xs whitespace-pre-wrap bg-gray-50 dark:bg-gray-800 p-3 rounded max-h-80 overflow-y-auto">
          {chunk.content}
        </pre>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-500 min-w-[80px]">{label}:</span>
      <span className="text-gray-900 dark:text-gray-100 break-all">
        {value || "—"}
      </span>
    </div>
  );
}
```

---

### Task 12: Build the Embed-to-Qdrant UI

**Working directory**: `rag-pipeline/apps/web/`

#### 12.1 Create `src/features/ingest/EmbedToQdrant.tsx`

```tsx
"use client";

import { useState, useEffect, useRef } from "react";
import {
  useStartEmbeddingMutation,
  useListCollectionsQuery,
  useGetCollectionStatsQuery,
  useSimilaritySearchMutation,
  type EmbedProgress,
  type SearchResult,
} from "@/store/ingestApi";

interface EmbedToQdrantProps {
  jobId: string;
}

export function EmbedToQdrant({ jobId }: EmbedToQdrantProps) {
  const [collectionName, setCollectionName] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [progress, setProgress] = useState<EmbedProgress | null>(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const [startEmbedding] = useStartEmbeddingMutation();
  const { data: collections = [], refetch: refetchCollections } =
    useListCollectionsQuery();

  const collectionNameValid = /^[a-z][a-z0-9_-]{2,62}$/.test(collectionName);

  async function handleEmbed() {
    if (!collectionNameValid) return;
    setShowConfirm(false);
    setIsIngesting(true);

    // Start the Celery task
    await startEmbedding({
      job_id: jobId,
      collection_name: collectionName,
      model_name: "BAAI/bge-small-en-v1.5",
    });

    // Connect WebSocket for progress
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/ingest/jobs/${jobId}/embed/ws?collection=${collectionName}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data: EmbedProgress = JSON.parse(event.data);
      setProgress(data);
      if (data.phase === "complete" || data.phase === "error") {
        setIsIngesting(false);
        refetchCollections();
        ws.close();
      }
    };

    ws.onerror = () => {
      setIsIngesting(false);
      setProgress({
        job_id: jobId,
        phase: "error",
        current: 0,
        total: 0,
        message: "WebSocket connection failed",
      });
    };
  }

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Embed form */}
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold mb-4">Embed to Qdrant</h3>
        <p className="text-sm text-gray-500 mb-4">
          Embeds all chunks using{" "}
          <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">
            BAAI/bge-small-en-v1.5
          </code>{" "}
          via FastEmbed (384 dimensions, cosine similarity). Runs locally — no
          API key required.
        </p>

        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">
              Collection Name
            </label>
            <input
              type="text"
              value={collectionName}
              onChange={(e) => setCollectionName(e.target.value.toLowerCase())}
              placeholder="my-docs-collection"
              className={`w-full px-3 py-2 border rounded-lg text-sm ${
                collectionName && !collectionNameValid
                  ? "border-red-500"
                  : "border-gray-300 dark:border-gray-600"
              }`}
            />
            {collectionName && !collectionNameValid && (
              <p className="text-xs text-red-500 mt-1">
                Must be 3-63 chars, start with letter, only lowercase/numbers/hyphens/underscores
              </p>
            )}
          </div>
          <button
            disabled={!collectionNameValid || isIngesting}
            onClick={() => setShowConfirm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isIngesting ? "Ingesting..." : "Embed to Qdrant"}
          </button>
        </div>
      </div>

      {/* Confirm modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-900 rounded-lg p-6 max-w-md w-full mx-4">
            <h4 className="text-lg font-semibold mb-2">Confirm Ingestion</h4>
            <div className="text-sm space-y-2 mb-4">
              <p>
                Collection:{" "}
                <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">
                  {collectionName}
                </code>
              </p>
              <p>Model: BAAI/bge-small-en-v1.5 (384 dims)</p>
              <p>Distance: Cosine</p>
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 border rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleEmbed}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                Confirm & Start
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress */}
      {progress && <EmbedProgressBar progress={progress} />}

      {/* Collections list */}
      <CollectionsList collections={collections} />
    </div>
  );
}

// ---- Sub-components ----

function EmbedProgressBar({ progress }: { progress: EmbedProgress }) {
  const pct =
    progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : 0;
  const color =
    progress.phase === "error"
      ? "bg-red-500"
      : progress.phase === "complete"
        ? "bg-green-500"
        : "bg-blue-500";

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium capitalize">{progress.phase}</span>
        <span className="text-sm text-gray-500">
          {progress.current} / {progress.total}
        </span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-2">{progress.message}</p>
    </div>
  );
}

function CollectionsList({
  collections,
}: {
  collections: import("@/store/ingestApi").CollectionInfo[];
}) {
  const [searchCollection, setSearchCollection] = useState<string | null>(null);

  if (collections.length === 0) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-lg font-semibold">Collections</h3>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-800">
        {collections.map((col) => (
          <div key={col.id} className="px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{col.collection_name}</p>
                <p className="text-xs text-gray-500">
                  {col.embedding_model} · {col.vector_dimensions}d ·{" "}
                  {col.vector_count} vectors · {col.document_count} docs
                </p>
              </div>
              <div className="flex gap-2">
                <StatusBadge status={col.status} />
                <button
                  onClick={() => setSearchCollection(col.collection_name)}
                  className="px-3 py-1 text-xs bg-gray-100 dark:bg-gray-800 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                >
                  Test Search
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Search test panel */}
      {searchCollection && (
        <SearchTestPanel
          collectionName={searchCollection}
          onClose={() => setSearchCollection(null)}
        />
      )}
    </div>
  );
}

function SearchTestPanel({
  collectionName,
  onClose,
}: {
  collectionName: string;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [search, { data: results, isLoading }] = useSimilaritySearchMutation();

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium">
          Search: {collectionName}
        </h4>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          ✕
        </button>
      </div>
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter search query..."
          className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) {
              search({ name: collectionName, query, limit: 5 });
            }
          }}
        />
        <button
          disabled={!query.trim() || isLoading}
          onClick={() => search({ name: collectionName, query, limit: 5 })}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50"
        >
         {isLoading ? "..." : "Search"}
       </button>
     </div>

     {results && (
       <div className="space-y-2">
         {results.map((r: SearchResult) => (
           <div
             key={r.id}
             className="p-3 bg-gray-50 dark:bg-gray-800 rounded text-sm"
           >
             <div className="flex justify-between mb-1">
               <span className="text-xs text-gray-500">{r.heading_path}</span>
               <span className="text-xs font-mono text-blue-600">
                 {r.score.toFixed(4)}
               </span>
             </div>
             <p className="text-xs">{r.content_preview}</p>
           </div>
         ))}
       </div>
     )}
   </div>
 );
}

function StatusBadge({ status }: { status: string }) {
 const colors: Record<string, string> = {
   ready: "bg-green-100 text-green-700",
   creating: "bg-yellow-100 text-yellow-700",
   error: "bg-red-100 text-red-700",
 };

 return (
   <span
     className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-700"}`}
   >
     {status}
   </span>
 );
}
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | All RTK Query hooks importable from `@/store/ingestApi` | TypeScript compiles without errors |
| 2 | `ingestApi` reducer registered in Redux store | Store includes `ingestApi` reducer path |
| 3 | `ChunkBrowser` renders paginated table with stats cards | Navigate to ingest page, verify table renders |
| 4 | `ChunkBrowser` shows token histogram in stats section | Histogram bars visible with bucket labels |
| 5 | `ChunkInspector` sidebar shows full chunk details on click | Click a row, verify metadata + content display |
| 6 | `TokenBadge` shows OK/Long/Over based on token count | Green for ≤512, yellow for ≤1024, red for >1024 |
| 7 | `EmbedToQdrant` validates collection name with regex | Invalid names show red border + error message |
| 8 | Confirm modal shows before embedding starts | Click "Embed to Qdrant" → modal appears |
| 9 | Progress bar updates via WebSocket during embedding | Progress bar fills during embed process |
| 10 | Collections list shows after successful ingestion | Collection appears with status badge |
| 11 | Search test panel returns similarity results | Enter query → results with scores displayed |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-6-subtask-4-rtk-chunk-browser-embed-ui-summary.md`

The summary report must include:
- **Subtask**: Phase 6, Subtask 4 — RTK Query + Chunk Browser UI + Embed-to-Qdrant UI
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items