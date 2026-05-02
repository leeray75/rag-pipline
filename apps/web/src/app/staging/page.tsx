"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StagingBrowser } from "@/features/staging/staging-browser";
import { useListJobsQuery } from "@/store/api/jobs-api";

export default function StagingPage() {
  const { data: jobs, isLoading, error } = useListJobsQuery();

  if (isLoading) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-3xl font-bold mb-8">Staging</h1>
        <p>Loading jobs...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-3xl font-bold mb-8">Staging</h1>
        <p className="text-red-500">Error loading jobs: {(error as any).data?.detail || "Unknown error"}</p>
      </main>
    );
  }

  // Get the most recent job with documents
  const jobWithDocs = jobs?.find((j) => j.total_documents > 0);
  const selectedJobId = jobWithDocs?.id;

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Staging</h1>
      </div>

      {/* Jobs List */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Jobs with Documents</CardTitle>
        </CardHeader>
        <CardContent>
          {(!jobs || jobs.length === 0) ? (
            <div className="text-center py-12 text-gray-500">
              No jobs found. <a href="/ingestion" className="text-blue-600 hover:underline">Create a job</a>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>URL</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Documents</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-mono text-sm">
                      {job.id}
                    </TableCell>
                    <TableCell className="max-w-md truncate">
                      {job.url}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{job.status}</Badge>
                    </TableCell>
                    <TableCell>
                      {job.processed_documents} / {job.total_documents}
                    </TableCell>
                    <TableCell>
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <a href={`/staging?jobId=${job.id}`}>View</a>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Document Browser */}
      {selectedJobId ? (
        <div>
          <h2 className="text-2xl font-semibold mb-4">Document Browser</h2>
          <StagingBrowser jobId={selectedJobId} />
        </div>
      ) : (
        <div className="flex items-center justify-center h-64 border rounded-lg">
          <p className="text-muted-foreground">Select a job to view documents</p>
        </div>
      )}
    </main>
  );
}
