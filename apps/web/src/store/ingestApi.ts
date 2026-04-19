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
  baseQuery: fetchBaseQuery({
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  }),
  tagTypes: ["Chunks", "ChunkStats", "Collections"],
  endpoints: (builder) => ({
    // Chunking
    startChunking: builder.mutation<{ task_id: string }, string>({
      query: (jobId) => ({
        url: `/ingest/jobs/${jobId}/chunk`,
        method: "POST",
      }),
      invalidatesTags: ["Chunks", "ChunkStats"],
    }),

    listChunks: builder.query<
      ChunkDocument[],
      { jobId: string; offset?: number; limit?: number }
    >({
      query: ({ jobId, offset = 0, limit = 50 }) =>
        `/ingest/jobs/${jobId}/chunks?offset=${offset}&limit=${limit}`,
      providesTags: ["Chunks"],
    }),

    getChunk: builder.query<
      ChunkDocument,
      { jobId: string; chunkId: string }
    >({
      query: ({ jobId, chunkId }) => `/ingest/jobs/${jobId}/chunks/${chunkId}`,
    }),

    getChunkStats: builder.query<ChunkStats, string>({
      query: (jobId) => `/ingest/jobs/${jobId}/chunk-stats`,
      providesTags: ["ChunkStats"],
    }),

    // Embedding
    startEmbedding: builder.mutation<
      { task_id: string; collection_name: string },
      EmbedRequest
    >({
      query: (body) => ({
        url: `/ingest/jobs/${body.job_id}/embed`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Collections"],
    }),

    // Collections
    listCollections: builder.query<CollectionInfo[], void>({
      query: () => "/ingest/collections",
      providesTags: ["Collections"],
    }),

    getCollectionStats: builder.query<CollectionStats, string>({
      query: (name) => `/ingest/collections/${name}/stats`,
    }),

    similaritySearch: builder.mutation<
      SearchResult[],
      { name: string; query: string; limit?: number }
    >({
      query: ({ name, query, limit = 5 }) => ({
        url: `/ingest/collections/${name}/search?query=${encodeURIComponent(query)}&limit=${limit}`,
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
