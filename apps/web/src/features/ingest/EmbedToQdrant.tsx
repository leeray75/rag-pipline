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
