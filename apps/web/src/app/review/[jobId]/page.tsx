"use client";

import { use, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
  type ReviewDocument,
} from "@/store/api/review-api";

export default function ReviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data: summary } = useGetReviewSummaryQuery(jobId);
  const { data: documents } = useListReviewDocumentsQuery({ jobId, status: statusFilter });
  const [batchApprove, { isLoading: isBatching }] = useBatchApproveMutation();
  const [finalize, { isLoading: isFinalizing }] = useFinalizeReviewMutation();

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!documents) return;
    const pendingIds = documents.filter((d) => d.review_status === "pending").map((d) => d.id);
    setSelectedIds(new Set(pendingIds));
  };

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Human Review</h1>
        <div className="flex gap-2">
          <Button
            variant="default"
            onClick={() => batchApprove({ jobId, documentIds: Array.from(selectedIds) })}
            disabled={selectedIds.size === 0 || isBatching}
          >
            Batch Approve ({selectedIds.size})
          </Button>
          <Button
            variant="default"
            onClick={() => finalize(jobId)}
            disabled={!summary?.all_reviewed || isFinalizing}
          >
            Finalize Review
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-5 gap-4 mb-8">
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold">{summary.total_documents}</p>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-green-600">{summary.approved}</p>
              <p className="text-xs text-muted-foreground">Approved</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{summary.edited}</p>
              <p className="text-xs text-muted-foreground">Edited</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-red-600">{summary.rejected}</p>
              <p className="text-xs text-muted-foreground">Rejected</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-yellow-600">{summary.pending}</p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-4">
        {[undefined, "pending", "approved", "edited", "rejected"].map((filter) => (
          <Button
            key={filter || "all"}
            variant={statusFilter === filter ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(filter)}
          >
            {filter || "All"}
          </Button>
        ))}
        <Button variant="outline" size="sm" onClick={selectAll}>
          Select All Pending
        </Button>
      </div>

      {/* Document List */}
      <div className="space-y-2">
        {documents?.map((doc: ReviewDocument) => (
          <div
            key={doc.id}
            className="flex items-center gap-4 p-4 border rounded-lg hover:bg-accent/50"
          >
            <input
              type="checkbox"
              checked={selectedIds.has(doc.id)}
              onChange={() => toggleSelect(doc.id)}
              className="h-4 w-4"
            />
            <div className="flex-1">
              <p className="font-medium">{doc.title || doc.url}</p>
              <p className="text-xs text-muted-foreground">{doc.url}</p>
            </div>
            <Badge variant={doc.quality_score && doc.quality_score > 70 ? "default" : "secondary"}>
              Score: {doc.quality_score || "N/A"}
            </Badge>
            <Badge
              variant={
                doc.review_status === "approved"
                  ? "default"
                  : doc.review_status === "rejected"
                  ? "destructive"
                  : "secondary"
              }
            >
              {doc.review_status}
            </Badge>
            <Link href={`/review/${jobId}/${doc.id}`}>
              <Button variant="outline" size="sm">Review</Button>
            </Link>
          </div>
        ))}
      </div>
    </main>
  );
}
