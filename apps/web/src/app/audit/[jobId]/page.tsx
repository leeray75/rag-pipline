"use client";

import { use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  useListAuditReportsQuery,
  useGetAuditReportQuery,
  useTriggerAuditMutation,
  type AuditIssue,
} from "@/store/api/audit-api";
import { useState } from "react";

function severityColor(severity: string): "default" | "destructive" | "secondary" {
  switch (severity) {
    case "critical": return "destructive";
    case "warning": return "default";
    default: return "secondary";
  }
}

export default function AuditPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const { data: reports } = useListAuditReportsQuery(jobId);
  const { data: reportDetail } = useGetAuditReportQuery(
    { jobId, reportId: selectedReportId! },
    { skip: !selectedReportId }
  );
  const [triggerAudit, { isLoading: isAuditing }] = useTriggerAuditMutation();

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Audit Reports</h1>
        <Button onClick={() => triggerAudit(jobId)} disabled={isAuditing}>
          {isAuditing ? "Running Audit..." : "Run Audit"}
        </Button>
      </div>

      {/* Report List */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-4 space-y-3">
          {reports?.map((report) => (
            <Card
              key={report.id}
              className={`cursor-pointer ${selectedReportId === report.id ? "border-primary" : ""}`}
              onClick={() => setSelectedReportId(report.id)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  Round {report.round}
                  <Badge variant={report.status === "approved" ? "default" : "destructive"}>
                    {report.status === "approved" ? "Clean" : `${report.total_issues} issues`}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{report.summary}</p>
              </CardContent>
            </Card>
          ))}
          {!reports?.length && (
            <p className="text-muted-foreground text-sm">No audit reports yet. Click Run Audit above.</p>
          )}
        </div>

        {/* Report Detail */}
        <div className="col-span-8">
          {reportDetail ? (
            <Card>
              <CardHeader>
                <CardTitle>Round {reportDetail.round} Report</CardTitle>
                <p className="text-sm text-muted-foreground">{reportDetail.summary}</p>
              </CardHeader>
              <CardContent className="space-y-6">
                {reportDetail.issues_json?.documents?.map((doc) => (
                  <div key={doc.doc_id}>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-sm">{doc.doc_id}</h4>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">Score: {doc.quality_score}</Badge>
                        <Badge variant={doc.issues.length === 0 ? "default" : "destructive"}>
                          {doc.issues.length} issues
                        </Badge>
                      </div>
                    </div>
                    {doc.issues.map((issue: AuditIssue) => (
                      <div key={issue.id} className="ml-4 p-3 border rounded mb-2">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={severityColor(issue.severity)}>{issue.severity}</Badge>
                          <span className="text-xs font-mono">{issue.type}</span>
                          {issue.field && (
                            <span className="text-xs text-muted-foreground">field: {issue.field}</span>
                          )}
                        </div>
                        <p className="text-sm">{issue.message}</p>
                        {issue.suggestion && (
                          <p className="text-xs text-muted-foreground mt-1">
                            💡 {issue.suggestion}
                          </p>
                        )}
                      </div>
                    ))}
                    <Separator className="mt-4" />
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-64 border rounded-lg">
              <p className="text-muted-foreground">Select an audit report to view details</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
