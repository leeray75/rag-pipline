import { apiSlice } from "./api-slice";

export interface ReviewDocument {
  id: string;
  url: string;
  title: string | null;
  word_count: number | null;
  quality_score: number | null;
  review_status: string;
  reviewer_notes: string | null;
}

export interface ReviewDocDetail {
  id: string;
  url: string;
  title: string | null;
  word_count: number | null;
  quality_score: number | null;
  current_markdown: string;
  original_markdown: string;
  has_changes: boolean;
  review_decision: {
    decision: string;
    reviewer_notes: string | null;
    created_at: string;
  } | null;
  comments: ReviewCommentItem[];
}

export interface ReviewCommentItem {
  id: string;
  line_number: number | null;
  content: string;
  author: string;
  resolved: boolean;
  created_at: string;
}

export interface ReviewSummary {
  total_documents: number;
  approved: number;
  rejected: number;
  edited: number;
  pending: number;
  all_reviewed: boolean;
}

export const reviewApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getReviewSummary: builder.query<ReviewSummary, string>({
      query: (jobId) => `/jobs/${jobId}/review/summary`,
      providesTags: ["Documents"],
    }),
    listReviewDocuments: builder.query<ReviewDocument[], { jobId: string; status?: string }>({
      query: ({ jobId, status }) =>
        `/jobs/${jobId}/review/documents${status ? `?status=${status}` : ""}`,
      providesTags: ["Documents"],
    }),
    getReviewDocument: builder.query<ReviewDocDetail, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => `/jobs/${jobId}/review/documents/${docId}`,
    }),
    submitDecision: builder.mutation<
      { status: string },
      { jobId: string; docId: string; decision: string; notes?: string; content?: string }
    >({
      query: ({ jobId, docId, decision, notes, content }) => ({
        url: `/jobs/${jobId}/review/documents/${docId}/decide`,
        method: "POST",
        body: { decision, reviewer_notes: notes, edited_content: content },
      }),
      invalidatesTags: ["Documents"],
    }),
    batchApprove: builder.mutation<
      { approved_count: number },
      { jobId: string; documentIds: string[]; notes?: string }
    >({
      query: ({ jobId, documentIds, notes }) => ({
        url: `/jobs/${jobId}/review/batch-approve`,
        method: "POST",
        body: { document_ids: documentIds, reviewer_notes: notes },
      }),
      invalidatesTags: ["Documents"],
    }),
    finalizeReview: builder.mutation<
      { status: string; total_documents: number; approved: number; rejected: number },
      string
    >({
      query: (jobId) => ({ url: `/jobs/${jobId}/review/finalize`, method: "POST" }),
      invalidatesTags: ["Jobs", "Documents"],
    }),
    addComment: builder.mutation<
      { id: string },
      { jobId: string; docId: string; lineNumber?: number; content: string }
    >({
      query: ({ jobId, docId, lineNumber, content }) => ({
        url: `/jobs/${jobId}/review/documents/${docId}/comments`,
        method: "POST",
        body: { line_number: lineNumber, content },
      }),
    }),
    resolveComment: builder.mutation<void, { jobId: string; commentId: string }>({
      query: ({ jobId, commentId }) => ({
        url: `/jobs/${jobId}/review/comments/${commentId}/resolve`,
        method: "PATCH",
      }),
    }),
  }),
});

export const {
  useGetReviewSummaryQuery,
  useListReviewDocumentsQuery,
  useGetReviewDocumentQuery,
  useSubmitDecisionMutation,
  useBatchApproveMutation,
  useFinalizeReviewMutation,
  useAddCommentMutation,
  useResolveCommentMutation,
} = reviewApi;
