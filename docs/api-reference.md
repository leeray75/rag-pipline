# API Reference

Complete API documentation for the RAG Pipeline.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Ingestion Jobs](#ingestion-jobs)
- [Audit](#audit)
- [A2A Loop](#a2a-loop)
- [Ingestion](#ingestion)
- [MCP](#mcp)
- [Health](#health)

---

## Overview

### Base URL

```
http://localhost/api/v1
```

Note: Traefik routes traffic to the API service on port 8000.

### Response Format

All responses are JSON unless otherwise specified.

**Success Response (200/201/202)**

```json
{
  "id": "uuid",
  "status": "pending",
  "created_at": "2026-04-19T01:00:00Z"
}
```

**Error Response (4xx/5xx)**

```json
{
  "detail": "Error message"
}
```

---

## Authentication

### Login

Authenticate and receive a JWT token.

**Endpoint**

```
POST /api/v1/auth/login
```

**Request**

```json
{
  "email": "admin@example.com",
  "password": "changeme"
}
```

**Response (200 OK)**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Error Response (401 Unauthorized)**

```json
{
  "detail": "Invalid credentials"
}
```

### Using the Token

Include the JWT in the `Authorization` header:

```bash
curl http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Ingestion Jobs

### Create Job

Create a new ingestion job from a URL.

**Endpoint**

```
POST /api/v1/jobs
```

**Request**

```json
{
  "url": "https://example.com/docs",
  "crawl_all_docs": true
}
```

**Response (201 Created)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://example.com/docs",
  "status": "pending",
  "crawl_all_docs": true,
  "total_documents": 0,
  "processed_documents": 0,
  "current_audit_round": 0,
  "created_at": "2026-04-19T01:00:00Z",
  "updated_at": "2026-04-19T01:00:00Z"
}
```

### Get Job Details

Retrieve job details including status and progress.

**Endpoint**

```
GET /api/v1/jobs/{id}
```

**Response (200 OK)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://example.com/docs",
  "status": "crawling",
  "crawl_all_docs": true,
  "total_documents": 0,
  "processed_documents": 0,
  "current_audit_round": 0,
  "created_at": "2026-04-19T01:00:00Z",
  "updated_at": "2026-04-19T01:00:00Z"
}
```

### Get Job Status (Lightweight)

Get job status without full details (optimized for polling).

**Endpoint**

```
GET /api/v1/jobs/{id}/status
```

**Response (200 OK)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "crawling",
  "total_documents": 5,
  "processed_documents": 3,
  "current_audit_round": 0
}
```

### List Documents

List all documents for a job.

**Endpoint**

```
GET /api/v1/jobs/{id}/documents
```

**Response (200 OK)**

```json
{
  "documents": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "url": "https://example.com/docs/page1",
      "title": "Page 1",
      "status": "pending",
      "word_count": 1500,
      "quality_score": 85,
      "created_at": "2026-04-19T01:00:00Z"
    }
  ]
}
```

### Get Document Content

Get the full content of a specific document.

**Endpoint**

```
GET /api/v1/jobs/{id}/documents/{doc_id}
```

**Response (200 OK)**

```json
{
  "id": "uuid",
  "job_id": "uuid",
  "url": "https://example.com/docs/page1",
  "title": "Page 1",
  "raw_html_path": "/app/data/staging/page1.html",
  "markdown_path": "/app/data/staging/page1.md",
  "status": "pending",
  "word_count": 1500,
  "quality_score": 85,
  "created_at": "2026-04-19T01:00:00Z",
  "content": "# Page Title\n\nPage content..."
}
```

### Remove Document

Remove a document from a job.

**Endpoint**

```
DELETE /api/v1/jobs/{id}/documents/{doc_id}
```

**Response (204 No Content)**

---

## Audit

### Trigger Audit

Trigger the audit workflow for a job.

**Endpoint**

```
POST /api/v1/jobs/{id}/audit
```

**Response (202 Accepted)**

```json
{
  "message": "Audit workflow started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### List Audit Reports

List all audit reports for a job.

**Endpoint**

```
GET /api/v1/jobs/{id}/audit-reports
```

**Response (200 OK)**

```json
{
  "reports": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "round_number": 1,
      "total_issues": 5,
      "summary": "Found 5 issues in 3 documents",
      "status": "issues_found",
      "created_at": "2026-04-19T01:00:00Z"
    }
  ]
}
```

### Get Audit Report

Get the full audit report JSON.

**Endpoint**

```
GET /api/v1/jobs/{id}/audit-reports/{report_id}
```

**Response (200 OK)**

```json
{
  "id": "uuid",
  "job_id": "uuid",
  "round_number": 1,
  "total_issues": 5,
  "issues_json": [
    {
      "document_url": "https://example.com/docs/page1",
      "rule": "title_length",
      "severity": "warning",
      "message": "Title is too short (8 < 10)",
      "suggestion": "Expand title to at least 10 characters"
    }
  ],
  "summary": "Found 5 issues in 3 documents",
  "status": "issues_found",
  "agent_notes": "See issues_json for details"
}
```

---

## A2A Loop

### Start A2A Loop

Start the A2A audit-correction loop.

**Endpoint**

```
POST /api/v1/jobs/{id}/start-loop
```

**Response (202 Accepted)**

```json
{
  "message": "A2A loop started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "max_rounds": 5
}
```

### Stop Loop

Force-stop the A2A loop.

**Endpoint**

```
POST /api/v1/jobs/{id}/stop-loop
```

**Response (200 OK)**

```json
{
  "message": "A2A loop stopped",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Get Loop Status

Get the current status of the A2A loop.

**Endpoint**

```
GET /api/v1/jobs/{id}/loop-status
```

**Response (200 OK)**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "round": 2,
  "max_rounds": 5,
  "last_audit_report_id": "uuid",
  "last_correction_round": 1
}
```

---

## Ingestion

### Trigger Chunking

Trigger the chunking pipeline for a job.

**Endpoint**

```
POST /api/v1/ingest/jobs/{id}/chunk
```

**Response (202 Accepted)**

```json
{
  "message": "Chunking pipeline started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### List Chunks

List all chunks for a job.

**Endpoint**

```
GET /api/v1/ingest/jobs/{id}/chunks?page=1&limit=25
```

**Response (200 OK)**

```json
{
  "chunks": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "job_id": "uuid",
      "chunk_index": 0,
      "content": "Chunk content...",
      "token_count": 256,
      "metadata": {
        "heading_path": ["Section 1", "Subsection 1"],
        "start_line": 1,
        "end_line": 50
      },
      "embedding_status": "pending",
      "created_at": "2026-04-19T01:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 25,
    "total": 100,
    "total_pages": 4
  }
}
```

### Get Chunk Details

Get the full details of a specific chunk.

**Endpoint**

```
GET /api/v1/ingest/jobs/{id}/chunks/{chunk_id}
```

**Response (200 OK)**

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "job_id": "uuid",
  "chunk_index": 0,
  "content": "Chunk content...",
  "token_count": 256,
  "metadata": {
    "heading_path": ["Section 1", "Subsection 1"],
    "start_line": 1,
    "end_line": 50
  },
  "embedding_status": "pending",
  "embedding_error": null,
  "created_at": "2026-04-19T01:00:00Z"
}
```

### Get Chunk Statistics

Get statistics about chunks for a job.

**Endpoint**

```
GET /api/v1/ingest/jobs/{id}/chunk-stats
```

**Response (200 OK)**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_chunks": 100,
  "total_tokens": 25600,
  "embedding_status_counts": {
    "pending": 50,
    "processing": 20,
    "completed": 25,
    "failed": 5
  },
  "token_distribution": {
    "0-512": 60,
    "512-1024": 30,
    "1024+": 10
  }
}
```

### Start Embedding

Start the embedding pipeline to Qdrant.

**Endpoint**

```
POST /api/v1/ingest/jobs/{id}/embed
```

**Request**

```json
{
  "collection_name": "my-docs"
}
```

**Response (202 Accepted)**

```json
{
  "message": "Embedding pipeline started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "collection_name": "my-docs"
}
```

### List Collections

List all Qdrant collections.

**Endpoint**

```
GET /api/v1/ingest/collections
```

**Response (200 OK)**

```json
{
  "collections": [
    {
      "id": "uuid",
      "job_id": "uuid",
      "collection_name": "my-docs",
      "vector_dimensions": 384,
      "vector_count": 1000,
      "document_count": 50,
      "status": "ready",
      "created_at": "2026-04-19T01:00:00Z"
    }
  ]
}
```

### Get Collection Statistics

Get statistics for a specific collection.

**Endpoint**

```
GET /api/v1/ingest/collections/{name}/stats
```

**Response (200 OK)**

```json
{
  "collection_name": "my-docs",
  "vector_dimensions": 384,
  "vector_count": 1000,
  "document_count": 50,
  "status": "ready",
  "vectors_per_document": {
    "min": 5,
    "max": 50,
    "avg": 20.0
  }
}
```

### Search Knowledge Base

Search the Qdrant collection using similarity search.

**Endpoint**

```
POST /api/v1/ingest/collections/{name}/search
```

**Request**

```json
{
  "query": "how to configure authentication",
  "top_k": 5
}
```

**Response (200 OK)**

```json
{
  "query": "how to configure authentication",
  "collection_name": "my-docs",
  "top_k": 5,
  "results": [
    {
      "chunk_id": "uuid",
      "content": "Authentication is configured...",
      "metadata": {
        "heading_path": ["Authentication", "Setup"],
        "source_url": "https://example.com/docs/auth"
      },
      "score": 0.89
    }
  ]
}
```

---

## MCP

### MCP Endpoint

The MCP server uses the Streamable HTTP transport.

**Endpoint**

```
POST /mcp
```

**Request (List Tools)**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Response**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "ingest_url",
        "description": "Create an ingestion job from a URL",
        "inputSchema": {
          "type": "object",
          "properties": {
            "url": { "type": "string" }
          }
        }
      }
    ]
  }
}
```

### Available MCP Tools

| Tool Name | Description |
|-----------|-------------|
| `ingest_url` | Create ingestion job from URL |
| `get_job_status` | Get job status and progress |
| `list_documents` | List documents for a job |
| `get_audit_report` | Get audit report JSON |
| `search_knowledge_base` | Query Qdrant vector store |
| `approve_job` | Trigger human approval workflow |
| `get_collection_stats` | Get Qdrant collection statistics |

---

## Health

### Liveness Check

Basic health check for load balancer probes.

**Endpoint**

```
GET /api/v1/health
```

**Response (200 OK)**

```json
{
  "status": "ok"
}
```

### Readiness Check

Check if the service is ready to accept traffic (includes dependency checks).

**Endpoint**

```
GET /api/v1/health/ready
```

**Response (200 OK)**

```json
{
  "status": "ready",
  "checks": {
    "postgres": "ok",
    "redis": "ok",
    "qdrant": "ok"
  }
}
```

**Response (503 Service Unavailable)**

```json
{
  "status": "degraded",
  "checks": {
    "postgres": "ok",
    "redis": "error: Connection refused",
    "qdrant": "ok"
  }
}
```

---

## WebSocket Events

### Job Progress Streaming

Real-time progress updates via WebSocket.

**Endpoint**

```
ws://localhost:8000/api/v1/ws/jobs/{id}/stream
```

**Connection Headers**

```
Authorization: Bearer <token>
```

**Events**

| Event | Description |
|-------|-------------|
| `job_status` | Job status update |
| `document_processed` | Document processing completed |
| `audit_complete` | Audit workflow completed |
| `embedding_complete` | Embedding pipeline completed |
| `error` | Error occurred |

**Example Message**

```json
{
  "event": "job_status",
  "timestamp": "2026-04-19T01:00:00Z",
  "payload": {
    "job_id": "uuid",
    "status": "processing",
    "progress": 50,
    "message": "Processing 2 of 4 documents"
  }
}
```

---

*Last updated: 2026-04-23*
