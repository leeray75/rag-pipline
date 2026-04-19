import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

export const apiSlice = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  }),
  tagTypes: ["Jobs", "Documents", "AuditReports", "Chunks", "ChunkStats", "Collections"],
  endpoints: () => ({}),
});
