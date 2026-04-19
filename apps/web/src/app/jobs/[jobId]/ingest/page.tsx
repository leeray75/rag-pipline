import { ChunkBrowser } from "@/features/ingest/ChunkBrowser";
import { EmbedToQdrant } from "@/features/ingest/EmbedToQdrant";

interface IngestPageProps {
  params: Promise<{ jobId: string }>;
}

export default async function IngestPage({ params }: IngestPageProps) {
  const { jobId } = await params;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Vector Ingestion</h1>
        <p className="text-sm text-gray-500 mt-1">
          Job: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">{jobId}</code>
        </p>
      </div>

      {/* Step 1: Browse generated chunks */}
      <section>
        <h2 className="text-lg font-semibold mb-4">1. Review Chunks</h2>
        <ChunkBrowser jobId={jobId} />
      </section>

      {/* Step 2: Embed and ingest */}
      <section>
        <h2 className="text-lg font-semibold mb-4">2. Embed & Ingest</h2>
        <EmbedToQdrant jobId={jobId} />
      </section>
    </div>
  );
}
