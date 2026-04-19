"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} from "@/store/api/review-api";

// Dynamic import for Monaco to avoid SSR issues
const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export default function DocumentReviewPage({
  params,
}: {
  params: Promise<{ jobId: string; docId: string }>;
}) {
  const { jobId, docId } = use(params);
  const { data: doc, refetch } = useGetReviewDocumentQuery({ jobId, docId });
  const [submitDecision] = useSubmitDecisionMutation();
  const [addComment] = useAddCommentMutation();
  const [resolveComment] = useResolveCommentMutation();

  const [editedContent, setEditedContent] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [newComment, setNewComment] = useState("");

  const handleApprove = useCallback(async () => {
    await submitDecision({ jobId, docId, decision: "approved", notes });
    refetch();
  }, [jobId, docId, notes, submitDecision, refetch]);

  const handleReject = useCallback(async () => {
    await submitDecision({ jobId, docId, decision: "rejected", notes });
    refetch();
  }, [jobId, docId, notes, submitDecision, refetch]);

  const handleSaveEdits = useCallback(async () => {
    if (editedContent) {
      await submitDecision({
        jobId,
        docId,
        decision: "edited",
        notes,
        content: editedContent,
      });
      refetch();
    }
  }, [jobId, docId, editedContent, notes, submitDecision, refetch]);

  const handleAddComment = useCallback(async () => {
    if (newComment.trim()) {
      await addComment({ jobId, docId, content: newComment });
      setNewComment("");
      refetch();
    }
  }, [jobId, docId, newComment, addComment, refetch]);

  if (!doc) return <p className="p-8">Loading...</p>;

  return (
    <main className="container mx-auto p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{doc.title || "Untitled Document"}</h1>
          <p className="text-sm text-muted-foreground">{doc.url}</p>
        </div>
        <div className="flex items-center gap-2">
          {doc.review_decision && (
            <Badge variant={doc.review_decision.decision === "approved" ? "default" : "destructive"}>
              {doc.review_decision.decision}
            </Badge>
          )}
          <Badge variant="secondary">Score: {doc.quality_score || "N/A"}</Badge>
          {doc.has_changes && <Badge variant="default">Modified by Agent</Badge>}
        </div>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="editor">
        <TabsList>
          <TabsTrigger value="editor">Editor</TabsTrigger>
          <TabsTrigger value="diff">Diff View</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="editor" className="border rounded-lg">
          <Editor
            height="500px"
            defaultLanguage="markdown"
            value={editedContent ?? doc.current_markdown}
            onChange={(value: string | undefined) => setEditedContent(value || "")}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              wordWrap: "on",
              lineNumbers: "on",
              fontSize: 14,
            }}
          />
        </TabsContent>

        <TabsContent value="diff">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold mb-2 text-sm">Original</h3>
              <pre className="bg-muted p-4 rounded text-xs max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                {doc.original_markdown}
              </pre>
            </div>
            <div>
              <h3 className="font-semibold mb-2 text-sm">Current - Agent-Corrected</h3>
              <pre className="bg-muted p-4 rounded text-xs max-h-[500px] overflow-y-auto whitespace-pre-wrap">
                {doc.current_markdown}
              </pre>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="preview" className="prose max-w-none p-4 max-h-[500px] overflow-y-auto">
          {/* Use dangerouslySetInnerHTML or react-markdown for preview */}
          <pre className="whitespace-pre-wrap">{doc.current_markdown}</pre>
        </TabsContent>
      </Tabs>

      {/* Review Actions */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Review Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <Input
              placeholder="Reviewer notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="flex gap-2">
              <Button variant="default" onClick={handleApprove}>
                ✓ Approve
              </Button>
              <Button variant="destructive" onClick={handleReject}>
                ✗ Reject
              </Button>
              <Button
                variant="secondary"
                onClick={handleSaveEdits}
                disabled={!editedContent}
              >
                💾 Save Edits & Approve
              </Button>
              <Link href={`/review/${jobId}`}>
                <Button variant="outline">← Back to List</Button>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comments */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Comments ({doc.comments.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 mb-4">
            {doc.comments.map((comment) => (
              <div
                key={comment.id}
                className={`p-3 border rounded ${comment.resolved ? "opacity-50" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{comment.author}</span>
                    {comment.line_number && (
                      <Badge variant="secondary" className="text-xs">
                        Line {comment.line_number}
                      </Badge>
                    )}
                  </div>
                  {!comment.resolved && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => resolveComment({ jobId, commentId: comment.id })}
                    >
                      Resolve
                    </Button>
                  )}
                </div>
                <p className="text-sm mt-1">{comment.content}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Add a comment..."
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddComment()}
            />
            <Button onClick={handleAddComment} disabled={!newComment.trim()}>
              Comment
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
