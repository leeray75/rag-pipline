import { apiSlice } from "./api-slice";

export interface LoopRound {
  round: number;
  audit_task_id: string;
  audit_task_state: string;
  audit_issues: number;
  audit_status: string;
  report_id: string;
  correction_applied: boolean;
  correction_task_id?: string;
  correction_task_state?: string;
  docs_corrected: number;
  false_positives: number;
}

export interface LoopResult {
  status: string;
  final_round: number;
  total_rounds: number;
  rounds: LoopRound[];
  reason?: string;
}

export interface LoopStatus {
  job_id: string;
  status: string;
  current_round: number;
}

export const loopApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    startLoop: builder.mutation<
      LoopResult,
      { jobId: string; maxRounds?: number }
    >({
      query: ({ jobId, maxRounds }) => ({
        url: `/jobs/${jobId}/start-loop${maxRounds ? `?max_rounds=${maxRounds}` : ""}`,
        method: "POST",
      }),
    }),
    stopLoop: builder.mutation<{ status: string; message: string }, string>({
      query: (jobId) => ({
        url: `/jobs/${jobId}/stop-loop`,
        method: "POST",
      }),
    }),
    getLoopStatus: builder.query<LoopStatus, string>({
      query: (jobId) => `/jobs/${jobId}/loop-status`,
    }),
  }),
});

export const {
  useStartLoopMutation,
  useStopLoopMutation,
  useGetLoopStatusQuery,
} = loopApi;
