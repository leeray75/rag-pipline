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
import { useListJobsQuery, useDeleteJobMutation } from "@/store/api/jobs-api";
import { useCallback } from "react";

export default function JobsPage() {
  const { data: jobs, isLoading, error } = useListJobsQuery();

  if (isLoading) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-3xl font-bold mb-8">Jobs</h1>
        <p>Loading jobs...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-3xl font-bold mb-8">Jobs</h1>
        <p className="text-red-500">Error loading jobs: {(error as any).data?.detail || "Unknown error"}</p>
      </main>
    );
  }

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Jobs</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Ingestion Jobs</CardTitle>
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
                    <TableCell className="text-right flex gap-2 justify-end">
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                      <DeleteJobButton jobId={job.id} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

function DeleteJobButton({ jobId }: { jobId: string }) {
  const [deleteJob, { isLoading }] = useDeleteJobMutation();

  const handleDelete = useCallback(() => {
    if (confirm(`Are you sure you want to delete this job? This action cannot be undone.`)) {
      deleteJob(jobId);
    }
  }, [deleteJob, jobId]);

  if (isLoading) {
    return (
      <Button variant="ghost" size="sm" disabled className="text-red-500">
        Deleting...
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleDelete}
      className="text-red-500 hover:text-red-700 hover:bg-red-50"
    >
      Delete
    </Button>
  );
}