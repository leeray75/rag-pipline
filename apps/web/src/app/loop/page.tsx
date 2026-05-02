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
import { useListJobsQuery } from "@/store/api/jobs-api";
import Link from "next/link";

export default function LoopPage() {
  const { data: jobs, isLoading, error } = useListJobsQuery();

  if (isLoading) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-3xl font-bold mb-8">Audit-Correct Loop</h1>
        <p>Loading jobs...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-3xl font-bold mb-8">Audit-Correct Loop</h1>
        <p className="text-red-500">Error loading jobs: {(error as any).data?.detail || "Unknown error"}</p>
      </main>
    );
  }

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Audit-Correct Loop</h1>
      </div>

      {/* Jobs List */}
      <Card>
        <CardHeader>
          <CardTitle>Jobs with A2A Loop</CardTitle>
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
                        <Link href={`/loop/${job.id}`}>Loop</Link>
                      </Button>
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
