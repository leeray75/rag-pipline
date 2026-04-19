# Phase 3, Subtask 3 — Audit Report Viewer UI + Tests

> **Phase**: Phase 3 — Audit Agent
> **Prerequisites**: Phase 2 complete — crawl pipeline produces Markdown files with frontmatter in staging directories, Next.js frontend with Redux store and RTK Query `apiSlice` configured, shadcn/ui components installed.
> **Prior Phase 3 Subtasks Required**: Subtask 1 (schema validator + audit agent) and Subtask 2 (audit API endpoints) must be complete — `POST /api/v1/jobs/{id}/audit`, `GET /api/v1/jobs/{id}/audit-reports`, and `GET /api/v1/jobs/{id}/audit-reports/{report_id}` endpoints are functional.
> **Estimated Scope**: 4 files to create/modify

---

## Context

This subtask builds the frontend audit report viewer and the backend test suite. The UI uses RTK Query to call the audit API endpoints, displays a list of audit reports for a job, and shows detailed per-document issues when a report is selected. The test suite validates the rule-based schema validator with 7 test cases covering all major validation rules.

### Key Assumptions from Prior Work

- RTK Query `apiSlice` exists at `src/store/api/api-slice.ts` (from Phase 1/2)
- shadcn/ui components are installed: `Card`, `CardContent`, `CardHeader`, `CardTitle`, `Badge`, `Button`, `Separator`
- Next.js App Router is configured with layout at `src/app/layout.tsx`
- The `schema_validator.py` module from Subtask 1 is importable as `src.agents.schema_validator`

---

## Relevant Technology Stack (Pinned Versions)

| Package | Version | Notes |
|---|---|---|
| Next.js | 16.2.3 | App Router |
| React | 19.2.5 | Bundled with Next.js |
| Redux Toolkit | 2.11.2 | RTK Query for API calls |
| TailwindCSS | 4.2.2 | Utility-first CSS |
| shadcn/ui | latest | UI component library |
| Python | 3.13.x | Test runtime |
| pytest | latest | Test framework |

---

## Step-by-Step Implementation Instructions

### Step 1: Create RTK Query Audit Endpoints

**Working directory**: `rag-pipeline/apps/web/`

#### 1.1 Create `src/store/api/audit-api.ts`

```typescript
import { apiSlice } from "./api-slice";

export interface AuditReportSummary {
  id: string;
  round: number;
  total_issues: number;
  summary: string;
  status: string;
  created_at: string;
}

export interface AuditIssue {
  id: string;
  type: string;
  severity: "critical" | "warning" | "info";
  field: string | null;
  message: string;
  line: number | null;
  suggestion: string | null;
}

export interface AuditDocResult {
  doc_id: string;
  issues: AuditIssue[];
  quality_score: number;
  status: string;
}

export interface AuditReportDetail extends AuditReportSummary {
  job_id: string;
  issues_json: { documents: AuditDocResult[] };
  agent_notes: string | null;
}

export const auditApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    triggerAudit: builder.mutation<AuditReportSummary, string>({
      query: (jobId) => ({ url: `/jobs/${jobId}/audit`, method: "POST" }),
      invalidatesTags: ["AuditReports"],
    }),
    listAuditReports: builder.query<AuditReportSummary[], string>({
      query: (jobId) => `/jobs/${jobId}/audit-reports`,
      providesTags: ["AuditReports"],
    }),
    getAuditReport: builder.query<AuditReportDetail, { jobId: string; reportId: string }>({
      query: ({ jobId, reportId }) => `/jobs/${jobId}/audit-reports/${reportId}`,
    }),
  }),
});

export const {
  useTriggerAuditMutation,
  useListAuditReportsQuery,
  useGetAuditReportQuery,
} = auditApi;
```

**Note**: You may need to add `"AuditReports"` to the `tagTypes` array in the base `apiSlice` definition if it doesn't already include it.

---

### Step 2: Create the Audit Report Viewer Page

**Working directory**: `rag-pipeline/apps/web/`

#### 2.1 Create `src/app/audit/[jobId]/page.tsx`

```tsx
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
```

---

### Step 3: Add Navigation Link

**Working directory**: `rag-pipeline/apps/web/`

#### 3.1 Update `src/app/layout.tsx`

Add an Audit link to the navigation bar alongside existing links:

```tsx
<a href="/audit" className="text-sm hover:underline">Audit</a>
```

Place this in the same `<nav>` section where other links (e.g., Jobs, Documents) are defined.

---

### Step 4: Write Schema Validator Tests

**Working directory**: `rag-pipeline/apps/api/`

#### 4.1 Create `tests/test_schema_validator.py`

```python
"""Tests for the rule-based schema validator."""

from src.agents.schema_validator import validate_document


def test_valid_document_passes():
    """A well-formed document should have zero critical issues."""
    content = """---
title: "Getting Started with MCP"
description: "A comprehensive guide to the Model Context Protocol for beginners and intermediate developers"
source_url: "https://modelcontextprotocol.io/docs/getting-started"
fetched_at: "2026-01-01T00:00:00Z"
tags: ["mcp", "protocol"]
---

# Getting Started with MCP

This is a comprehensive guide to understanding the Model Context Protocol.

""" + "Content paragraph. " * 50  # Ensure > 200 words

    result = validate_document(content, "test.md")
    critical_issues = [i for i in result.issues if i.severity == "critical"]
    assert len(critical_issues) == 0
    assert result.is_valid is True


def test_missing_frontmatter_is_critical():
    """Document without frontmatter should have a critical issue."""
    content = "# No Frontmatter\n\nJust body content here."
    result = validate_document(content, "test.md")
    assert result.is_valid is False
    assert any(i.issue_type == "missing_frontmatter" for i in result.issues)


def test_missing_title_is_critical():
    """Missing title in frontmatter should be critical."""
    content = """---
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Heading

Content here.
"""
    result = validate_document(content, "test.md")
    assert any(
        i.issue_type == "missing_frontmatter" and i.field == "title"
        for i in result.issues
    )


def test_multiple_h1_detected():
    """Multiple H1 headings should generate a warning."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# First H1

Some content.

# Second H1

More content.
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "multiple_h1" for i in result.issues)


def test_skipped_heading_level():
    """H1 -> H3 skip should be detected."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Main Title

### Skipped to H3

Content.
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "skipped_heading_level" for i in result.issues)


def test_unlabeled_code_block():
    """Code blocks without language identifiers should be flagged."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Title

```
some code without language
```
""" + "Word " * 200
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "unlabeled_code_block" for i in result.issues)


def test_short_content_warning():
    """Documents under 200 words should get a warning."""
    content = """---
title: "Test"
description: "A valid description that is at least fifty characters long for testing"
source_url: "https://example.com"
fetched_at: "2026-01-01T00:00:00Z"
---

# Title

Short content.
"""
    result = validate_document(content, "test.md")
    assert any(i.issue_type == "content_too_short" for i in result.issues)
```

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Create | `rag-pipeline/apps/web/src/store/api/audit-api.ts` |
| Create | `rag-pipeline/apps/web/src/app/audit/[jobId]/page.tsx` |
| Modify | `rag-pipeline/apps/web/src/app/layout.tsx` |
| Create | `rag-pipeline/apps/api/tests/test_schema_validator.py` |

---

## Done-When Checklist

- [ ] RTK Query `audit-api.ts` exports `useTriggerAuditMutation`, `useListAuditReportsQuery`, `useGetAuditReportQuery`
- [ ] `"AuditReports"` tag is registered in the base `apiSlice` tagTypes
- [ ] Audit Report viewer page at `/audit/[jobId]` renders report list in left panel
- [ ] Selecting a report shows per-document issues grouped by severity in right panel
- [ ] "Run Audit" button triggers `POST /api/v1/jobs/{id}/audit` and refreshes the report list
- [ ] Navigation link to `/audit` is present in the app layout
- [ ] `pytest tests/test_schema_validator.py -v` passes all 7 tests:
  - `test_valid_document_passes`
  - `test_missing_frontmatter_is_critical`
  - `test_missing_title_is_critical`
  - `test_multiple_h1_detected`
  - `test_skipped_heading_level`
  - `test_unlabeled_code_block`
  - `test_short_content_warning`

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-3-subtask-3-audit-ui-and-tests-summary.md`

The summary report must include:
- **Subtask**: Phase 3, Subtask 3 — Audit Report Viewer UI + Tests
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items
