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
