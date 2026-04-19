

| AI Knowledge Base RAG Ingestion Pipeline Multi-Phase Implementation Plan ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ System Agentic RAG Workflow with Human-in-the-Loop Architecture Mono-repo · Python API · NextJS Frontend AI Framework LangGraph \+ LangChain · Multi-Agent Pipeline Vector Store Qdrant · Postgres / Supabase Protocols MCP (Model Context Protocol) · A2A (Agent-to-Agent) Total Phases 7 Phases · 28–38 Weeks Estimated  |
| ----- |

# **Executive Summary**

This document defines the complete multi-phase implementation plan for a production-grade AI Knowledge Base RAG (Retrieval-Augmented Generation) Ingestion Pipeline. The system enables teams to harvest web documentation, process and audit it through autonomous AI agents, and ingest structured knowledge into a vector database — closing knowledge gaps that exist in LLM training data.

The workflow follows a human-in-the-loop design philosophy: AI agents handle the heavy lifting of content discovery, markdown conversion, schema validation, and correction, while human operators retain final approval authority at critical checkpoints before knowledge is committed to the vector store.

## **Core Workflow at a Glance**

| URL Ingestion | User submits a URL; system fetches HTML and converts to Markdown via Python markitdown |
| :---- | :---- |
| **Doc Discovery** | AI agent crawls nav links to discover and download all related documentation pages |
| **Audit Agent** | LangGraph agent validates all Markdown files against a content schema and produces a structured report |
| **Correction Agent** | Second LangGraph agent receives the audit report and corrects legitimate issues autonomously |
| **Iterative Loop** | Audit → Correct cycle repeats until the Audit Agent finds zero issues |
| **Human Review** | Final Markdown files and summary report presented for human sign-off via dashboard |
| **JSON Generation** | Approved Markdown files chunked and serialized to vector-ready JSON |
| **Vector Ingestion** | JSON embedded and upserted to Qdrant; metadata indexed in Postgres/Supabase |

# **Recommended Technology Stack**

The following table consolidates your specified stack with additional recommended tools that complement the workflow, annotated by role and priority.

| ⚙️  Backend & API |  |  |
| :---- | :---- | :---: |
| **Python 3.12+** | Core backend runtime | **Required** |
| **FastAPI** | Async REST API framework with OpenAPI/WebSocket support | **Required** |
| **Uvicorn \+ Gunicorn** | ASGI server for FastAPI production deployment | **Required** |
| **Celery \+ Redis** | Task queue for long-running agent jobs and async crawling | **Recommended** |
| **APScheduler** | Lightweight in-process job scheduling for periodic re-ingestion | **Optional** |
| **🤖  AI Agents & Orchestration** |  |  |
| **LangGraph** | Stateful multi-agent graph orchestration (Audit ↔ Correct loop) | **Required** |
| **LangChain** | LLM chains, document loaders, text splitters | **Required** |
| **Claude claude-sonnet-4-20250514 / GPT-4o** | Primary LLM for Audit and Correction agents | **Required** |
| **LangSmith** | Agent tracing, debugging, and eval for LangGraph workflows | **Recommended** |
| **Pydantic AI** | Structured output validation from LLM responses (schema compliance) | **Recommended** |
| **📄  Content Processing** |  |  |
| **markitdown (Python)** | HTML → Markdown conversion (core pipeline tool) | **Required** |
| **Playwright / Crawlee** | Headless browser for JS-rendered documentation sites | **Recommended** |
| **trafilatura** | Fallback HTML text extraction for complex pages | **Recommended** |
| **BeautifulSoup4** | Nav link extraction for document discovery | **Required** |
| **tiktoken** | Token-aware chunking before JSON serialization | **Recommended** |
| **spaCy** | NLP preprocessing for metadata extraction (titles, keywords) | **Optional** |
| **🗄️  Data & Storage** |  |  |
| **Qdrant** | Primary vector database for knowledge embeddings | **Required** |
| **Postgres / Supabase** | Relational store for jobs, audit reports, user state | **Required** |
| **Redis** | Celery broker \+ caching layer for crawl deduplication | **Recommended** |
| **SQLAlchemy 2.0** | Async ORM for Postgres interactions | **Required** |
| **Alembic** | Database migration management | **Required** |
| **🔢  Embeddings** |  |  |
| **OpenAI text-embedding-3-large** | High-quality dense embeddings (1536/3072 dims) | **Recommended** |
| **Cohere embed-v3** | Alternative embedding model with strong retrieval performance | **Optional** |
| **sentence-transformers** | Local embedding fallback (no API cost) | **Optional** |
| **FastEmbed (Qdrant)** | Qdrant-native fast local embeddings | **Recommended** |
| **🔌  Protocols & Integration** |  |  |
| **MCP Server (Python SDK)** | Expose pipeline tools as MCP-callable functions | **Required** |
| **MCP Client** | Frontend or agent consumption of MCP tool endpoints | **Required** |
| **A2A Protocol** | Structured Audit ↔ Correction agent message passing | **Required** |
| **WebSockets** | Real-time agent progress streaming to UI dashboard | **Required** |
| **Server-Sent Events (SSE)** | Lightweight alternative to WS for one-way streaming | **Optional** |
| **🖥️  Frontend** |  |  |
| **NextJS 15 (App Router)** | React framework with SSR/RSC for dashboard | **Required** |
| **ReactJS 19** | UI component library | **Required** |
| **Redux Toolkit \+ RTK Query** | Global state \+ data fetching/cache layer | **Required** |
| **TailwindCSS v4** | Utility-first styling | **Required** |
| **shadcn/ui** | Accessible component primitives (Radix UI based) | **Recommended** |
| **TanStack Table v8** | Headless data table for document/JSON review | **Recommended** |
| **Monaco Editor** | In-browser Markdown and JSON editing with syntax highlight | **Recommended** |
| **Zustand** | Lightweight local UI state (modals, panel state) | **Optional** |
| **React Flow** | Visualize the agent pipeline graph in the dashboard | **Optional** |
| **🏗️  Infrastructure & DevOps** |  |  |
| **Docker \+ Docker Compose** | Container orchestration for all services | **Required** |
| **Nx or Turborepo** | Mono-repo build system with task caching | **Recommended** |
| **GitHub Actions** | CI/CD pipeline (lint, test, build, deploy) | **Recommended** |
| **Traefik** | Reverse proxy and service routing within Docker Compose | **Recommended** |
| **Prometheus \+ Grafana** | Metrics and observability for agent job monitoring | **Optional** |
| **OpenTelemetry** | Distributed tracing across API \+ agent services | **Optional** |
| **🧪  Testing & Quality** |  |  |
| **pytest \+ pytest-asyncio** | Backend unit and integration testing | **Required** |
| **Vitest \+ React Testing Library** | Frontend component testing | **Recommended** |
| **Playwright (E2E)** | End-to-end UI workflow testing | **Recommended** |
| **Hypothesis** | Property-based testing for document schema validation | **Optional** |

# **Mono-Repo Structure**

The repository is organized to keep backend and frontend runtimes, databases, and agent services isolated with clear boundaries. Each top-level package can be developed, tested, and deployed independently.

| rag-pipeline/                          \# mono-repo root ├── apps/ │   ├── api/                           \# FastAPI backend │   │   ├── src/ │   │   │   ├── agents/                \# LangGraph agent definitions │   │   │   │   ├── audit\_agent.py │   │   │   │   ├── correction\_agent.py │   │   │   │   └── graph.py           \# LangGraph workflow DAG │   │   │   ├── crawlers/              \# URL \+ doc discovery │   │   │   ├── converters/            \# markitdown HTML→MD │   │   │   ├── embeddings/            \# embedding model wrappers │   │   │   ├── ingest/                \# Qdrant upsert logic │   │   │   ├── mcp/                   \# MCP server tools │   │   │   ├── routers/               \# FastAPI route modules │   │   │   ├── models/                \# SQLAlchemy models │   │   │   ├── schemas/               \# Pydantic schemas │   │   │   ├── workers/               \# Celery task definitions │   │   │   └── main.py │   │   ├── tests/ │   │   └── Dockerfile │   │ │   └── web/                           \# NextJS frontend │       ├── src/ │       │   ├── app/                   \# App Router pages │       │   ├── components/            \# Shared UI components │       │   ├── features/              \# Feature modules │       │   │   ├── ingestion/         \# URL input, crawl UI │       │   │   ├── staging/           \# MD file review │       │   │   ├── audit/             \# Audit report viewer │       │   │   └── vector/            \# JSON \+ Qdrant UI │       │   ├── store/                 \# Redux store \+ RTK Query │       │   └── lib/                   \# Shared utilities │       └── Dockerfile │ ├── packages/ │   ├── shared-types/                  \# Shared TS/Python schemas │   ├── ui-kit/                        \# Shared React components │   └── config/                        \# Shared ESLint/TS configs │ ├── infra/ │   ├── docker-compose.yml             \# All services │   ├── docker-compose.dev.yml │   ├── nginx/ or traefik/ │   └── postgres/                      \# Init SQL, migrations │ ├── scripts/                           \# Dev utilities ├── .github/workflows/ ├── turbo.json or nx.json └── README.md |
| :---- |

# **Implementation Phases**

The project is broken into 7 sequential phases. Each phase builds on the previous and delivers independently testable, demonstrable functionality. Estimated durations assume a small team of 2–3 developers.

| Phase 1 | Foundation — Mono-Repo, Infrastructure & Core APIs Weeks 1–4 · Deliverable: Running skeleton with Docker Compose, CI/CD, and empty API routes |
| :---: | :---- |

### **Objectives**

* Bootstrap the mono-repo with Turborepo/Nx workspace configuration

* Scaffold the FastAPI backend with health endpoints, CORS, and async database connection

* Scaffold the NextJS frontend with App Router, TailwindCSS, shadcn/ui, and Redux store

* Stand up Docker Compose with all services: api, web, postgres, redis, qdrant, celery-worker

* Establish CI/CD with GitHub Actions: lint, type-check, test, build gates

* Configure Traefik as the reverse proxy routing traffic to api and web containers

* Set up Alembic and create initial Postgres schemas for jobs, documents, audit reports

### **Database Schema — Phase 1 Tables**

| ingestion\_jobs | id, url, status (pending/crawling/converting/auditing/done/failed), created\_at, updated\_at |
| :---- | :---- |
| **documents** | id, job\_id, url, raw\_html (S3/local path), markdown (path), status, created\_at |
| **audit\_reports** | id, job\_id, round (int), issues\_json, summary, status, agent\_notes, created\_at |
| **vector\_collections** | id, job\_id, qdrant\_collection\_name, document\_count, embedded\_at |

### **Tasks**

1. Initialize repo: pnpm workspaces \+ turbo.json or nx.json

2. Create apps/api with FastAPI, SQLAlchemy 2.0 async engine, Alembic

3. Create apps/web with NextJS 15, Tailwind v4, shadcn/ui init, Redux Toolkit setup

4. Write docker-compose.yml: api, web, postgres:16, redis:7, qdrant:latest, celery-worker

5. Add Traefik service with routing rules for /api/\* → api container, /\* → web container

6. GitHub Actions: install, lint (ruff \+ eslint), type-check (mypy \+ tsc), test (pytest \+ vitest), docker build

7. Define shared Pydantic \+ Zod schemas for API contracts in packages/shared-types

| ✅ Phase 1 Done When... |
| :---- |
| • docker compose up \--build starts all services with no errors |
| • GET /api/health returns 200 with service status |
| • NextJS dashboard loads at http://localhost:3000 |
| • Postgres migrations run cleanly via alembic upgrade head |
| • CI pipeline passes on every PR to main |

| Phase 2 | URL Ingestion, Crawling & HTML→Markdown Conversion Weeks 5–8 · Deliverable: Full crawl-to-markdown pipeline with staging file browser |
| :---: | :---- |

### **Objectives**

* Build the URL intake API endpoint that creates an ingestion job

* Implement the HTML fetcher supporting both static (httpx) and JS-rendered (Playwright) pages

* Build the document link discovery service using BeautifulSoup4 to parse nav/sidebar links

* Implement AI-assisted link extraction: pass rendered HTML to Claude to extract structured doc links when CSS selectors fail

* Integrate markitdown for HTML → Markdown conversion with custom pre/post processors

* Build Celery task chain: fetch → discover links (if toggle on) → convert all → save to staging

* Build the staging file browser UI: list discovered docs, view raw HTML, view converted Markdown

* WebSocket endpoint to stream crawl progress to the frontend in real time

### **API Endpoints — Phase 2**

| POST /api/jobs | Create ingestion job { url, crawl\_all\_docs: bool } |
| :---- | :---- |
| **GET /api/jobs/:id** | Poll job status and progress metrics |
| **GET /api/jobs/:id/documents** | List all discovered documents with status |
| **GET /api/jobs/:id/documents/:doc\_id** | Get raw HTML and converted Markdown for one document |
| **WS /api/jobs/:id/stream** | WebSocket stream of real-time crawl events |
| **DELETE /api/jobs/:id/documents/:doc\_id** | Remove a document from staging before audit |

### **Link Discovery Logic**

When "Download All Documents" is toggled:

8. Fetch the seed URL HTML via Playwright (handles JS-rendered nav menus)

9. Pass the nav/sidebar HTML fragment to Claude Sonnet with a prompt: "Extract all documentation page links from this HTML. Return a JSON array of { href, title } objects. Only include links that are part of the same documentation site."

10. Deduplicate and filter links to same origin \+ /docs/\* path prefix

11. Enqueue each link as a Celery sub-task with rate limiting (1 req/sec to avoid bans)

12. Each sub-task fetches, converts, and saves its document; updates progress counter

### **Frontend — Staging Dashboard**

* URL input field with "Crawl All Docs" toggle switch

* Real-time progress bar fed by WebSocket events (X of Y documents fetched)

* Document tree panel (mirrors site nav structure) with status badges

* Split-pane viewer: raw HTML (syntax highlighted) | converted Markdown (rendered preview)

* Monaco Editor for manual Markdown edits before sending to audit

* Bulk actions: Select All, Exclude Selected, Re-convert Selected

| ✅ Phase 2 Done When... |
| :---- |
| • Submitting https://modelcontextprotocol.io/docs/getting-started/intro fetches and converts that page |
| • With "crawl all" toggled, all 20+ MCP doc pages are discovered, fetched, and converted |
| • Real-time progress counter updates in the browser during crawl |
| • Staging file browser shows all Markdown files, each viewable and editable |
| • Playwright fallback handles JS-rendered nav menus successfully |

| Phase 3 | Audit Agent — Schema Validation & Report Generation Weeks 9–13 · Deliverable: LangGraph Audit Agent producing structured issue reports |
| :---: | :---- |

### **Objectives**

* Define the canonical Markdown document schema with required metadata, structure rules, and content quality criteria

* Build the LangGraph Audit Agent as a multi-step graph: load docs → validate schema → assess quality → generate report

* Implement parallel document processing: audit N documents concurrently using LangGraph map-reduce pattern

* Produce a structured JSON audit report per round with per-document issue lists and a global summary

* Store audit reports in Postgres; expose report API endpoints

* Build the Audit Report viewer in the dashboard with issue categorization and severity levels

### **Document Schema Definition**

Every Markdown document must conform to the following schema before it can be ingested:

| Frontmatter — title | Required. Non-empty string, max 120 chars |
| :---- | :---- |
| **Frontmatter — description** | Required. 50–300 char summary for embedding metadata |
| **Frontmatter — source\_url** | Required. Original URL the document was fetched from |
| **Frontmatter — fetched\_at** | Required. ISO 8601 timestamp |
| **Frontmatter — tags** | Optional. Array of lowercase keyword strings |
| **Heading Hierarchy** | H1 must appear exactly once; no skipped heading levels (H1→H3) |
| **Code Blocks** | Must specify language identifier (\`\`\`python not just \`\`\`) |
| **Link Integrity** | No bare URLs; all links must have descriptive anchor text |
| **Content Length** | Minimum 200 words; maximum 8,000 words per document |
| **No Boilerplate** | No cookie banners, nav menus, footer content in body |
| **No Duplicate Content** | Cosine similarity \< 0.92 against other docs in same job |

### **LangGraph Audit Agent — Graph Design**

| Node: load\_documents | Read all Markdown files from staging area for this job\_id |
| :---- | :---- |
| **Node: validate\_schema** | Rule-based checks: frontmatter keys, heading levels, code block langs |
| **Node: assess\_quality (LLM)** | Claude evaluates content quality: boilerplate, clarity, AI-readability |
| **Node: check\_duplicates** | Embed docs, compute pairwise cosine similarity, flag near-duplicates |
| **Node: compile\_report** | Aggregate all issues into structured JSON report, compute severity |
| **Node: save\_report** | Persist AuditReport to Postgres, emit WebSocket event to UI |
| **Edge: conditional** | If issues\_count \== 0 → mark job "approved"; else → send to Correction Agent |

### **Audit Report JSON Schema**

| {   "job\_id": "uuid",   "round": 1,   "audited\_at": "2025-01-01T00:00:00Z",   "summary": "Found 12 issues across 4 documents",   "total\_issues": 12,   "documents": \[     {       "doc\_id": "uuid",       "url": "https://...",       "issues": \[         {           "id": "issue-uuid",           "type": "missing\_frontmatter",           "severity": "critical",   // critical | warning | info           "field": "description",           "message": "Frontmatter key description is missing",           "line": null,           "suggestion": "Add: description: Brief summary of..."         }       \],       "quality\_score": 72,  // 0-100, LLM-assessed       "status": "issues\_found"     }   \],   "agent\_notes": null,   // populated by Correction Agent   "status": "issues\_found"  // issues\_found | approved } |
| :---- |

| ✅ Phase 3 Done When... |
| :---- |
| • Audit Agent processes all documents from a Phase 2 crawl and produces a valid report JSON |
| • Schema violations (missing frontmatter, broken heading hierarchy) are reliably detected |
| • LLM quality assessment correctly flags boilerplate and low-quality content |
| • Audit Report viewer in dashboard displays issues grouped by document and severity |
| • Audit round number increments correctly on subsequent runs |

| Phase 4 | Correction Agent & Iterative Audit Loop (A2A) Weeks 14–19 · Deliverable: Full autonomous Audit ↔ Correct loop with A2A messaging |
| :---: | :---- |

### **Objectives**

* Build the LangGraph Correction Agent that receives the audit report and processes each document issue

* Implement A2A (Agent-to-Agent) protocol for structured message passing between Audit and Correction agents

* Correction Agent classifies each issue: LEGITIMATE (fix it) | FALSE\_POSITIVE (document and skip)

* Agent applies corrections to Markdown files and records its reasoning and changes in the report

* After correction completes, automatically trigger a new Audit Agent round

* Implement loop termination: max\_rounds guard (default: 10\) to prevent infinite loops

* Build loop monitoring UI: show each round audit/correct cycle with issue counts trending to zero

### **A2A Message Protocol**

Messages are structured JSON payloads exchanged between agents via an internal FastAPI event bus. Each message includes a sender, recipient, action type, and payload:

| AUDIT\_COMPLETE | Audit Agent → Correction Agent. Payload: { report\_id, issues\_count, documents\[\] } |
| :---- | :---- |
| **CORRECTION\_STARTED** | Correction Agent → Audit Agent (notify). Payload: { report\_id, round } |
| **ISSUE\_CLASSIFIED** | Correction Agent internal event. Payload: { issue\_id, classification, reasoning } |
| **DOCUMENT\_CORRECTED** | Correction Agent → system. Payload: { doc\_id, changes\_made\[\], new\_markdown\_path } |
| **CORRECTION\_COMPLETE** | Correction Agent → Audit Agent. Payload: { report\_id, docs\_corrected, false\_positives } |
| **RE\_AUDIT\_REQUESTED** | Audit Agent triggers new round. Payload: { job\_id, round: n+1 } |
| **LOOP\_APPROVED** | Audit Agent → system. Payload: { job\_id, final\_round, all docs clean } |

### **Correction Agent — Graph Design**

| Node: receive\_report | Parse incoming A2A AUDIT\_COMPLETE message, load report from Postgres |
| :---- | :---- |
| **Node: classify\_issues (LLM)** | For each issue: Claude reasons whether it is a real problem or a false positive given document context |
| **Node: plan\_corrections** | Generate a correction plan: what to add, change, or remove per document |
| **Node: apply\_corrections** | Write corrected Markdown back to staging area; version previous file |
| **Node: update\_report** | Annotate audit report with agent\_notes: what was fixed vs. marked false positive |
| **Node: emit\_complete** | Send CORRECTION\_COMPLETE A2A message to trigger next audit round |
| **Guard: max\_rounds** | If round \> max\_rounds: escalate to human review regardless of issue count |

### **Correction Agent — Issue Classification Prompt Pattern**

| SYSTEM: You are a document correction agent. Given an issue reported by an audit agent and the full document context, determine: 1\. Is this a LEGITIMATE issue that must be fixed? 2\. Is this a FALSE\_POSITIVE that should be dismissed? Respond with a JSON object: {   "classification": "LEGITIMATE" | "FALSE\_POSITIVE",   "reasoning": "...",   "correction": "..."   // if LEGITIMATE: exact corrected text or instruction } ISSUE: {{ issue\_json }} DOCUMENT EXCERPT: {{ document\_excerpt }} |
| :---- |

### **Loop Control & UI**

* Dashboard shows a visual timeline of rounds: Round 1 Audit (12 issues) → Round 1 Correct → Round 2 Audit (4 issues) → Round 2 Correct → Round 3 Audit (0 issues) ✓

* Each round card is expandable to show issue diff (issues resolved vs. new issues found)

* Manual override: human can force-terminate the loop and proceed to review at any round

* Agent reasoning logs are stored and viewable per round for full transparency

| ✅ Phase 4 Done When... |
| :---- |
| • Audit Agent finding issues automatically triggers Correction Agent via A2A message |
| • Correction Agent correctly classifies at least 90% of audit issues (LEGITIMATE vs FALSE\_POSITIVE) |
| • Loop runs unattended until issue count reaches 0 |
| • max\_rounds guard triggers human escalation if loop does not converge |
| • Dashboard displays round-by-round progress with issue count trend chart |

| Phase 5 | Human Review Interface & Approval Workflow Weeks 20–23 · Deliverable: Full human-in-the-loop review dashboard with approval gate |
| :---: | :---- |

### **Objectives**

* Build the Human Review Dashboard: final Markdown file browser, audit report viewer, approval controls

* Allow human reviewers to edit individual Markdown files directly in the browser (Monaco Editor)

* Allow human to override issue classifications from the Correction Agent

* Implement the approval gate: "Approve All & Proceed to JSON" action requires explicit user confirmation

* Add reviewer annotations: humans can leave notes on documents or issues

* Email/notification hook when a job reaches human review state

* Implement role-based access: admin can approve; viewer can read-only

### **Human Review UI Components**

| Job Summary Card | URL, total docs, rounds completed, final issue count (should be 0), time elapsed |
| :---- | :---- |
| **Final Audit Report Panel** | Read-only structured view of last audit round, with agent correction notes inline |
| **Document Browser** | File tree with search; click any file to open in editor panel |
| **Markdown Editor Panel** | Monaco Editor with live rendered preview side-by-side; save button persists edits |
| **Issue Override Controls** | For any issue marked FALSE\_POSITIVE, reviewer can reclassify to LEGITIMATE (triggers re-loop) |
| **Approval Action Bar** | Sticky bottom bar: "Approve All (N docs) & Generate JSON" with confirmation modal |
| **Rejection Action** | "Send Back for Re-audit" button with required comment field |

### **Approval Gate API**

| POST /api/jobs/:id/approve | Marks job as human-approved; triggers Phase 6 JSON generation pipeline |
| :---- | :---- |
| **POST /api/jobs/:id/reject** | Returns job to audit loop with reviewer notes injected as additional context |
| **PATCH /api/jobs/:id/documents/:doc\_id** | Save human edits to a Markdown file (creates new version) |
| **POST /api/jobs/:id/documents/:doc\_id/annotate** | Add reviewer annotation to a document or specific issue |

| ✅ Phase 5 Done When... |
| :---- |
| • Human Review Dashboard loads with all final Markdown files browsable and editable |
| • Reviewer can edit a Markdown file and save changes that persist to staging area |
| • "Approve & Proceed" action is gated behind a confirmation dialog |
| • Rejected jobs correctly re-enter the audit loop with reviewer notes as additional context |
| • Email notification fires when job enters human review state |

| Phase 6 | JSON Generation, Chunking & Vector Ingestion Weeks 24–29 · Deliverable: Approved docs embedded in Qdrant and indexed in Postgres |
| :---: | :---- |

### **Objectives**

* Build the Markdown → JSON serialization pipeline with intelligent chunking

* Implement token-aware chunking using tiktoken (target: 512–1024 tokens per chunk with overlap)

* Generate structured JSON documents with all required metadata for vector retrieval

* Build the JSON review UI: browse generated chunks, inspect metadata, preview embeddings

* Implement the embedding pipeline: call embedding model API per chunk, handle rate limits and retries

* Upsert embedded chunks into Qdrant with payload metadata for filtered retrieval

* Index collection metadata in Postgres for dashboard querying

* Build the final approval gate: "Embed to Qdrant" button with collection naming

### **JSON Document Schema (per chunk)**

| {   "id": "chunk-uuid",   "document\_id": "doc-uuid",   "job\_id": "job-uuid",   "chunk\_index": 0,   "total\_chunks": 8,   "content": "The full text of this chunk...",   "token\_count": 487,   "metadata": {     "source\_url": "https://...",     "title": "Getting Started with MCP",     "description": "Introduction to the Model Context Protocol",     "tags": \["mcp", "protocol", "getting-started"\],     "heading\_path": "Introduction \> What is MCP \> Core Concepts",     "fetched\_at": "2025-01-01T00:00:00Z",     "approved\_at": "2025-01-02T00:00:00Z",     "audit\_rounds": 2,     "quality\_score": 94   } } |
| :---- |

### **Embedding & Qdrant Ingestion Pipeline**

13. Load all approved JSON chunks for job\_id from staging

14. Batch chunks into groups of 100; call embedding model API (OpenAI or Cohere)

15. Retry failed batches with exponential backoff (max 3 retries)

16. Create or get Qdrant collection with correct vector dimensions and distance metric (Cosine)

17. Upsert vectors with full payload (chunk JSON) in batches of 100

18. Record successful upsert in vector\_collections Postgres table

19. Emit job completion event; update job status to "ingested"

### **JSON Review UI**

* Chunk browser: paginated table of all chunks with token count and metadata preview

* Chunk inspector: click a chunk to see full content, metadata, heading path, and similarity neighbors

* Chunking statistics: total chunks, avg token count, distribution histogram

* "Embed to Qdrant" button: input for collection name, dimension preview, confirm modal

* Post-ingestion: Qdrant collection stats (vector count, index size, query latency)

| ✅ Phase 6 Done When... |
| :---- |
| • Approved Markdown files are chunked into valid JSON with all required metadata fields |
| • JSON files are saved to staging area and browsable in the UI |
| • Embedding pipeline processes all chunks and upserts to Qdrant without errors |
| • Qdrant collection is queryable via dashboard similarity search test |
| • Postgres vector\_collections table reflects the new collection with accurate doc counts |

| Phase 7 | MCP Server, Observability, Polish & Production Hardening Weeks 30–38 · Deliverable: Production-ready system with MCP tools, monitoring & docs |
| :---: | :---- |

### **Objectives**

* Expose the full pipeline as MCP (Model Context Protocol) tools consumable by AI assistants

* Add OpenTelemetry distributed tracing across FastAPI \+ LangGraph \+ Celery

* Set up Prometheus metrics endpoint \+ Grafana dashboard for agent job monitoring

* Add LangSmith integration for agent run tracing and evaluation

* Implement re-ingestion: detect updated documentation and trigger delta update pipeline

* Add API authentication: JWT-based auth for the dashboard and API

* Production Docker Compose hardening: resource limits, health checks, restart policies

* Write comprehensive README, API docs (auto-generated from FastAPI), and runbook

### **MCP Server — Exposed Tools**

| ingest\_url | Args: url, crawl\_all. Creates an ingestion job and returns job\_id |
| :---- | :---- |
| **get\_job\_status** | Args: job\_id. Returns current status, progress, and round count |
| **list\_documents** | Args: job\_id. Returns all documents with their current status |
| **get\_audit\_report** | Args: job\_id, round. Returns structured audit report JSON |
| **search\_knowledge\_base** | Args: query, collection\_name, top\_k. Queries Qdrant and returns ranked chunks |
| **approve\_job** | Args: job\_id. Human approval trigger; starts JSON generation |
| **get\_collection\_stats** | Args: collection\_name. Returns Qdrant collection metadata |

### **Observability Stack**

| LangSmith | Trace every Audit and Correction agent run; view token usage, latency, and intermediate steps |
| :---- | :---- |
| **OpenTelemetry** | Instrument FastAPI \+ Celery \+ httpx; export traces to Grafana Tempo |
| **Prometheus** | Scrape custom metrics: jobs\_per\_hour, agent\_rounds\_avg, embed\_latency\_p95 |
| **Grafana** | Pre-built dashboards: Pipeline Throughput, Agent Loop Health, Qdrant Collection Growth |
| **Sentry** | Error tracking for both FastAPI backend and NextJS frontend |
| **Structured Logging** | structlog \+ JSON log format; ship to Loki or CloudWatch for searchability |

### **Production Hardening Checklist**

* All secrets in .env files excluded from git; use Docker secrets or Vault in production

* Postgres connection pooling via pgBouncer or SQLAlchemy pool\_size tuning

* Celery worker concurrency tuned for I/O bound crawl tasks (high concurrency)

* Qdrant collection snapshots scheduled daily for backup

* Rate limiting on all public API endpoints via slowapi

* Input sanitization on URL field (SSRF prevention: block private IP ranges)

* API versioning: all routes under /api/v1/

* Docker Compose resource limits: cpu and memory caps per service

| ✅ Phase 7 Done When... |
| :---- |
| • MCP server exposes all tools and an AI assistant (e.g. Claude Desktop) can trigger ingestion via MCP |
| • Grafana dashboard shows live agent job metrics |
| • LangSmith traces show complete Audit and Correction agent runs with token costs |
| • System passes load test: 5 concurrent ingestion jobs with 50 docs each |
| • All secrets managed via environment; no credentials in code or git history |
| • Full runbook written covering startup, common failures, and manual override procedures |

# **Master Timeline & Milestones**

| Phase / Milestone | Duration | Dependencies | Key Deliverable |
| :---- | :---- | :---- | :---- |
| Phase 1: Foundation | Weeks 1–4 | None | Running Docker Compose skeleton |
| Phase 2: Crawl & Convert | Weeks 5–8 | Phase 1 | Staging file browser with Markdown |
| Phase 3: Audit Agent | Weeks 9–13 | Phase 2 | Structured audit report JSON |
| Phase 4: Correction Loop | Weeks 14–19 | Phase 3 | Autonomous Audit↔Correct loop |
| Phase 5: Human Review | Weeks 20–23 | Phase 4 | Approval gate dashboard |
| Phase 6: JSON & Vector | Weeks 24–29 | Phase 5 | Qdrant collection populated |
| Phase 7: MCP & Hardening | Weeks 30–38 | Phase 6 | Production-ready \+ MCP tools |
| Total | \~38 weeks | — | Full production system |

## **Suggested Team Composition**

| Full-Stack Lead | Owns mono-repo structure, NextJS dashboard, FastAPI routing, CI/CD |
| :---- | :---- |
| **AI/ML Engineer** | Owns LangGraph agent design, A2A protocol, embeddings, Qdrant integration |
| **Backend Engineer** | Owns Celery tasks, crawling pipeline, Postgres schema, MCP server |
| **DevOps (part-time)** | Docker Compose, Traefik, GitHub Actions, observability stack |

## **Risk Register**

| Agent loop non-convergence | Mitigation: max\_rounds guard \+ human escalation; tune correction prompts with LangSmith evals |
| :---- | :---- |
| **JS-rendered sites (Playwright)** | Mitigation: Playwright with wait\_for\_selector; AI fallback for link extraction |
| **LLM API cost overrun** | Mitigation: token budgets per job; cache LLM responses for identical inputs; use smaller models for classification |
| **Qdrant scalability** | Mitigation: Qdrant supports horizontal sharding; design collection naming with pagination in mind |
| **Markdown quality variance** | Mitigation: markitdown pre/post processors; custom CSS selector hints per domain |
| **SSRF on URL input** | Mitigation: allowlist domains or block RFC1918 ranges before fetching |

*AI Knowledge Base RAG Ingestion Pipeline — Implementation Plan v1.0*

*This document is a living plan. Update phase estimates after each phase retrospective.*