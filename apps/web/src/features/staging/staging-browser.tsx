"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useListDocumentsQuery,
  useGetDocumentQuery,
  useDeleteDocumentMutation,
  type DocumentItem,
} from "@/store/api/jobs-api";

interface StagingBrowserProps {
  jobId: string;
}

export function StagingBrowser({ jobId }: StagingBrowserProps) {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const { data: documents, isLoading } = useListDocumentsQuery(jobId);
  const { data: docDetail } = useGetDocumentQuery(
    { jobId, docId: selectedDocId! },
    { skip: !selectedDocId }
  );
  const [deleteDoc] = useDeleteDocumentMutation();

  if (isLoading) return <p>Loading documents...</p>;
  if (!documents?.length) return <p>No documents found for this job.</p>;

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Document List Panel */}
      <div className="col-span-4 border rounded-lg p-4 max-h-[80vh] overflow-y-auto">
        <h3 className="font-semibold mb-4">
          Documents ({documents.length})
        </h3>
        {documents.map((doc: DocumentItem) => (
          <div
            key={doc.id}
            className={`p-3 rounded cursor-pointer mb-2 border ${
              selectedDocId === doc.id ? "border-primary bg-accent" : "hover:bg-accent/50"
            }`}
            onClick={() => setSelectedDocId(doc.id)}
          >
            <p className="text-sm font-medium truncate">{doc.title || doc.url}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={doc.status === "converted" ? "default" : "destructive"}>
                {doc.status}
              </Badge>
              {doc.word_count && (
                <span className="text-xs text-muted-foreground">
                  {doc.word_count} words
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Document Viewer Panel */}
      <div className="col-span-8">
        {docDetail ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{docDetail.title || "Untitled"}</CardTitle>
              <p className="text-sm text-muted-foreground">{docDetail.url}</p>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="markdown">
                <TabsList>
                  <TabsTrigger value="markdown">Markdown Preview</TabsTrigger>
                  <TabsTrigger value="raw">Raw Markdown</TabsTrigger>
                  <TabsTrigger value="html">Source HTML</TabsTrigger>
                </TabsList>
                <TabsContent value="markdown" className="prose max-w-none max-h-[60vh] overflow-y-auto">
                  {docDetail.markdown && (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {docDetail.markdown}
                    </ReactMarkdown>
                  )}
                </TabsContent>
                <TabsContent value="raw">
                  <pre className="bg-muted p-4 rounded text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {docDetail.markdown || "No markdown content"}
                  </pre>
                </TabsContent>
                <TabsContent value="html">
                  <pre className="bg-muted p-4 rounded text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {docDetail.raw_html || "No HTML content"}
                  </pre>
                </TabsContent>
              </Tabs>
              <div className="flex gap-2 mt-4">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    deleteDoc({ jobId, docId: docDetail.id });
                    setSelectedDocId(null);
                  }}
                >
                  Remove Document
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="flex items-center justify-center h-64 border rounded-lg">
            <p className="text-muted-foreground">Select a document to view</p>
          </div>
        )}
      </div>
    </div>
  );
}