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
