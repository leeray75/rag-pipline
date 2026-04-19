import { apiSlice } from "./api-slice";

export interface Job {
  id: string;
  url: string;
  status: string;
  crawl_all_docs: boolean;
  total_documents: number;
  processed_documents: number;
  current_audit_round: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  job_id: string;
  url: string;
  title: string | null;
  status: string;
  word_count: number | null;
  quality_score: number | null;
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  raw_html: string | null;
  markdown: string | null;
}

export const jobsApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    createJob: builder.mutation<Job, { url: string; crawl_all_docs: boolean }>({
      query: (body) => ({ url: "/jobs", method: "POST", body }),
      invalidatesTags: ["Jobs"],
    }),
    getJob: builder.query<Job, string>({
      query: (id) => `/jobs/${id}`,
      providesTags: (result, error, id) => [{ type: "Jobs", id }],
    }),
    getJobStatus: builder.query<Job, string>({
      query: (id) => `/jobs/${id}/status`,
    }),
    listDocuments: builder.query<DocumentItem[], string>({
      query: (jobId) => `/jobs/${jobId}/documents`,
      providesTags: ["Documents"],
    }),
    getDocument: builder.query<DocumentDetail, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => `/jobs/${jobId}/documents/${docId}`,
    }),
    deleteDocument: builder.mutation<void, { jobId: string; docId: string }>({
      query: ({ jobId, docId }) => ({
        url: `/jobs/${jobId}/documents/${docId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Documents"],
    }),
  }),
});

export const {
  useCreateJobMutation,
  useGetJobQuery,
  useGetJobStatusQuery,
  useListDocumentsQuery,
  useGetDocumentQuery,
  useDeleteDocumentMutation,
} = jobsApi;