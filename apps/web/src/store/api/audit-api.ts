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
