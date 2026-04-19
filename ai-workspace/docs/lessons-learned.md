# Lessons Learned - RAG Pipeline Project

**Document:** Best Practices & Anti-Patterns for AI-Assisted Development
**Last Updated:** 2026-04-19
**Purpose:** A reference guide for AI assistants and developers to avoid common mistakes and quickly identify solutions when issues arise.

---

## Table of Contents

1. [Development Workflow](#development-workflow)
2. [Docker & Containerization](#docker--containerization)
3. [Monorepo & Package Management](#monorepo--package-management)
4. [Database & Migrations](#database--migrations)
5. [Backend Development (FastAPI/Python)](#backend-development-fastapipython)
6. [Frontend Development (Next.js/TypeScript)](#frontend-development-nextjstypescript)
7. [API Integration](#api-integration)
8. [Testing](#testing)
9. [Build & Deployment](#build--deployment)
10. [AI Agent Development](#ai-agent-development)

---

## Development Workflow

### Use Docker for Consistent Validation

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Environment isolation issues | Validation script ran on host with different dependencies | Refactored to use `docker compose exec` for all checks | High: Eliminated false positives |

> **Anti-Pattern:** Running validation scripts directly on the host machine  
> **Best Practice:** Always run validation inside containers using `docker compose exec <service> <command>` to ensure consistent behavior across all developer machines.

---

## Docker & Containerization

### Dockerfile Best Practices

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Node_modules directory conflict | pnpm creates node_modules but Docker copied files over it | Created `.dockerignore` to exclude node_modules | Blocking: Docker build failed |
| pnpm not installed | pnpm was not available in the environment | Installed globally using `npm install -g pnpm` | Blocking: Had to install pnpm before monorepo setup |
| pnpm-lock.yaml missing | Lock file was not generated | Used `npm install` instead of pnpm in Dockerfile | Blocking: Build failed initially |

> **Anti-Pattern:** Not using `.dockerignore` to exclude `node_modules`  
> **Best Practice:** Always include `.dockerignore` with `node_modules/` to prevent local node_modules from being copied into the container.

> **Anti-Pattern:** Using `:latest` tag for Docker images  
> **Best Practice:** Use exact version tags (e.g., `traefik:v3.6.13`) for reproducible builds.

---

## Monorepo & Package Management

### pnpm Workspaces Setup

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| pnpm not installed | pnpm was not available in the environment | Installed globally using `npm install -g pnpm` | Blocking: Had to install pnpm before monorepo setup |

> **Anti-Pattern:** Assuming pnpm is pre-installed  
> **Best Practice:** Include pnpm installation in setup scripts or documentation: `npm install -g pnpm`

### Package.json Configuration

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| pnpm-lock.yaml missing | Lock file was not generated | Used `npm install` instead of pnpm in Dockerfile | Blocking: Build failed initially |

> **Anti-Pattern:** Using `npm install` when working with pnpm workspaces  
> **Best Practice:** Use `pnpm install` in Dockerfile for pnpm workspaces. If issues persist, ensure `pnpm-lock.yaml` is committed to the repository.

---

## Database & Migrations

### Alembic Migration Issues

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Database connection in Alembic | Container not running during migration | Started postgres service first, created migration file manually | High: Ensured reproducible migrations |
| Missing aiosqlite Module | Initial SQLite approach failed due to missing `aiosqlite` module | Switched to `AsyncMock` for database dependency mocking | High: Tests now work without database |

> **Anti-Pattern:** Running Alembic commands without the database service running  
> **Best Practice:** Always start the database service first: `docker compose up -d postgres` before running migrations.

> **Anti-Pattern:** Using actual database for testing (slow, requires setup)  
> **Best Practice:** Use `AsyncMock` to simulate SQLAlchemy `AsyncSession` interface for testing. This allows:
> - Tests to run without database dependencies
> - Precise control over return values for testing various scenarios
> - Faster test execution

### Database Schema Verification

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Schema import failures | Missing model exports in `__init__.py` | Added proper exports in `src/models/__init__.py` | High: Schema imports failed |

> **Anti-Pattern:** Not exporting models from `__init__.py`  
> **Best Practice:** Always export models from `src/models/__init__.py`:
> ```python
> from .review import ReviewDecision, ReviewComment
> from .ingestion_job import IngestionJob
> from .document import Document
> from .audit_report import AuditReport
> from .vector_collection import VectorCollection
> ```

---

## Backend Development (FastAPI/Python)

### SQLAlchemy & Async ORM

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Import path resolution error | Absolute imports failed in package structure | Changed to relative imports (`.module`) | Blocking: Module not found |

> **Anti-Pattern:** Using absolute imports like `from src.models.review import ReviewDecision`  
> **Best Practice:** Use relative imports in Python packages:
> ```python
> from .review import ReviewDecision
> from ..config import settings
> ```

### Pydantic & API Schema

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| A2A SDK API incompatibility | Used outdated API conventions (camelCase, old enum values) | Updated to snake_case field names, new enum values | High: Required widespread code changes |

> **Anti-Pattern:** Using camelCase field names in Pydantic models  
> **Best Practice:** Use snake_case field names for all Pydantic models when working with A2A protocol v1.0:
> ```python
> class ReviewDecisionCreate(BaseModel):
>     decision: ReviewDecisionType  # snake_case
>     reviewer_notes: str = ""      # snake_case
> ```

### FastAPI Router Registration

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Router not registered | Missing import in `src/routers/__init__.py` | Added `from .review import review_router` | High: API endpoints not found |

> **Anti-Pattern:** Not exporting routers from `__init__.py`  
> **Best Practice:** Always export routers from `src/routers/__init__.py`:
> ```python
> from .health import health_router
> from .review import review_router
> ```

---

## Frontend Development (Next.js/TypeScript)

### Next.js v16 Specific Patterns

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Next.js Link component compliance | Initial implementation used `<a>` tags instead of Next.js `Link` | Added `Link` import and replaced `<a>` tags with `<Link>` | High: Client-side navigation now works properly |
| TypeScript implicit any type | Monaco Editor `onChange` callback parameter had implicit `any` type | Added explicit type annotation `value: string | undefined` | Medium: Code quality improved, type safety ensured |
| Directory creation with special characters | Shell wildcard expansion failed with `mkdir -p "review/[jobId]"` | Quoted the path argument | Medium: Directory creation failed |

> **Anti-Pattern:** Using `<a>` tags for navigation in Next.js  
> **Best Practice:** Always use `Link` from `next/link` for client-side navigation:
> ```tsx
> import Link from "next/link";
> 
> <Link href={`/review/${jobId}`}>View Review</Link>
> ```

> **Anti-Pattern:** Not awaiting `params` in Next.js v16  
> **Best Practice:** In Next.js v16, `params` and `searchParams` are Promises:
> ```tsx
> import { use } from "react";
> 
> export default function Page({ params }: { params: Promise<{ id: string }> }) {
>   const { id } = use(params);
>   // ...
> }
> ```

> **Anti-Pattern:** Using server-side rendering for Monaco Editor  
> **Best Practice:** Dynamically import Monaco with `ssr: false`:
> ```tsx
> import dynamic from "next/dynamic";
> 
> const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });
> ```

### Client Component Directive

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Client Component directive missing | Component uses hooks but not marked as client component | Added `'use client'` directive | High: Runtime errors with React hooks |

> **Anti-Pattern:** Using React hooks without `'use client'` directive  
> **Best Practice:** Always add `'use client'` at the top of files that use:
> - React hooks (`useState`, `useCallback`, `useMemo`)
> - RTK Query hooks
> - Browser APIs (Monaco editor, localStorage)

### File Path Navigation

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Directory creation with special characters | Shell wildcard expansion failed with `mkdir -p "review/[jobId]"` | Quoted the path argument | Medium: Directory creation failed |

> **Anti-Pattern:** Using unquoted paths with special characters in shell  
> **Best Practice:** Always quote paths containing `[`, `]`, or other glob characters:
> ```bash
> mkdir -p "rag-pipeline/apps/web/src/app/review/[jobId]"
> ```

---

## API Integration

### RTK Query Integration

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| API endpoints not found | Missing tag invalidation causing stale data | Used `["Documents"]` tag for automatic refetching | Medium: Data refresh issues |

> **Anti-Pattern:** Not using RTK Query tags for cache invalidation  
> **Best Practice:** Use tags to enable automatic refetching when related data changes:
> ```typescript
> export const reviewApi = apiSlice.injectEndpoints({
>   endpoints: (builder) => ({
>     getReviewSummary: builder.query<ReviewSummary, string>({
>       query: (jobId) => `/jobs/${jobId}/review/summary`,
>       providesTags: ["Documents"],
>     }),
>     finalizeReview: builder.mutation<void, string>({
>       query: (jobId) => ({
>         url: `/jobs/${jobId}/review/finalize`,
>         method: "POST",
>       }),
>       invalidatesTags: ["Documents", "Jobs"],
>     }),
>   }),
> });
> ```

### API Endpoint Consistency

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| A2A SDK API incompatibility | Used outdated API conventions (camelCase, old enum values) | Updated to snake_case field names, new enum values | High: Required widespread code changes |

> **Anti-Pattern:** Using different naming conventions across the API  
> **Best Practice:** Standardize on snake_case for all API endpoints and Pydantic model fields when working with A2A protocol v1.0.

---

## Testing

### Pytest Testing Best Practices

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Database mocking complexity | Need for database without actual connection | Used `AsyncMock` for database dependency mocking | High: Tests now run without database |

> **Anti-Pattern:** Using actual database for testing (slow, requires setup)  
> **Best Practice:** Use `AsyncMock` to simulate SQLAlchemy `AsyncSession` interface. Implement a dynamic `execute_mock` function that tracks call count and returns appropriately configured mock results for each query type.

### Test Coverage Strategy

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Incomplete test coverage | Missing edge case testing | Added tests for invalid job IDs, unreviewed documents, job not found | High: Test suite validates all scenarios |

> **Anti-Pattern:** Only testing happy paths  
> **Best Practice:** Test all scenarios including:
> - Invalid inputs (missing job IDs, invalid status)
> - Error conditions (job not found, not all documents reviewed)
> - Edge cases (empty lists, null values)

---

## Build & Deployment

### Web Application Build

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Frontend compilation failed | Missing dependencies | Added `diff`, `react-diff-viewer-continued` to package.json | High: Build failed |

> **Anti-Pattern:** Not installing dependencies before build  
> **Best Practice:** Always run `pnpm install` before building:
> ```bash
> pnpm install
> pnpm build
> ```

---

## AI Agent Development

### A2A Protocol Compliance

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| A2A SDK API incompatibility | Used outdated API conventions (camelCase, old enum values) | Updated to snake_case field names, new enum values | High: Required widespread code changes |
| AgentCard validation | Missing required fields `default_input_modes` and `default_output_modes` | Added required fields to AgentCard builders | High: Agent card validation failed |
| Role and TaskState naming | `Role.ROLE_USER` → `Role.user`, `TaskState.TASK_STATE_COMPLETED` → `TaskState.completed` | Updated all references to match a2a-sdk v0.3.26 | High: A2A protocol messages failed |

> **Anti-Pattern:** Using outdated A2A SDK API conventions  
> **Best Practice:** Always check the A2A SDK version and update all references:
> - Field names: Use `snake_case` (e.g., `default_input_modes`, `default_output_modes`)
> - Enum values: Use lowercase (e.g., `Role.user`, `TaskState.completed`)
> - Data structure: Use `Part.root.data` for payload structure

### LangGraph State Management

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| LangGraph state schema constraints | Strict type annotations required for StateGraph | Defined `AuditGraphState` TypedDict with explicit types | Blocking: Graph compilation failed |

> **Anti-Pattern:** Using regular dicts for LangGraph state  
> **Best Practice:** Define state schemas using TypedDict with explicit types:
> ```python
> from typing import TypedDict
> 
> class AuditGraphState(TypedDict):
>     job_id: str
>     url: str
>     content: str
>     audit_report: Optional[AuditReport]
>     correction_attempts: int
> ```

---

## General Observations

### Development Environment

1. **Docker-Centric Development**: Running validation inside containers eliminates environment isolation issues and ensures consistent behavior across all developer machines.

2. **Progressive Fallback Strategy**: The URL fetching service implements automatic fallback from static to browser mode (content < 500 chars) and LLM fallback for link discovery when CSS selectors find fewer than 3 links.

3. **Rule-Based vs LLM Separation**: Schema validation uses deterministic rules while quality assessment uses Claude LLM. This separates objective checks from subjective evaluation.

4. **OpenAI-Compatible Endpoint**: All LLM operations use an OpenAI-compatible endpoint, eliminating provider-specific dependencies and simplifying configuration.

5. **Relative Imports in Python Packages**: Absolute imports often fail in complex package structures. Using relative imports (`.module`) provides more reliable module resolution.

6. **A2A Protocol Version**: The A2A protocol v1.0 uses Pydantic models with snake_case field names. Staying current with SDK changes is essential for compatibility.

---

## Embedding Pipeline & Vector Search

### FastEmbed Singleton Pattern

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| First embedding call slow | Model loads on first request | Use singleton pattern with lazy model loading | Medium: Initial request slower, subsequent calls fast |

> **Best Practice:** Use a lazy-load singleton for FastEmbedService to ensure the model is loaded once and reused across requests:
> ```python
> class FastEmbedService:
>     _instance: Optional["FastEmbedService"] = None
>
>     @classmethod
>     def get_instance(cls) -> "FastEmbedService":
>         if cls._instance is None:
>             cls._instance = cls()
>         return cls._instance
> ```

### Async/Celery Integration

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Async function calls fail in sync Celery | Celery is synchronous but database operations are async | Use `asyncio.run(_run())` to wrap async operations | High: Enables Celery integration with async database |

> **Best Practice:** When using async database operations in Celery tasks, wrap them with `asyncio.run()`:
> ```python
> @celery.task
> def embed_job_task(job_id: str, collection_name: str):
>     async def _run():
>         async with async_session_factory() as session:
>             # ... async operations
>     asyncio.run(_run())
> ```

### Qdrant URL Configuration

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Qdrant connection fails | Using localhost instead of Docker service name | Use service name inside Docker network: `http://qdrant:6333` | High: Enables container-to-container communication |

> **Best Practice:** Configure Qdrant URL to use the Docker service name for inter-container communication:
> ```yaml
> # docker-compose.yml
> environment:
>   - QDRANT_URL=http://qdrant:6333
> ```

### RTK Query API Separation

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| Duplicate reducerPath conflict | Trying to extend existing API with new endpoints | Use `createApi` with unique `reducerPath` for separate API slices | High: Clean API organization |

> **Best Practice:** Create separate API slices with unique `reducerPath` for different concerns:
> ```typescript
> export const ingestApi = createApi({
>   reducerPath: "ingestApi",
>   baseQuery: fetchBaseQuery({ baseUrl: apiBaseUrl }),
>   endpoints: (builder) => ({
>     // ... endpoints
>   }),
> });
> ```

---

## Quick Reference: Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| Docker build fails with node_modules error | `node_modules` being copied into container | Add `node_modules/` to `.dockerignore` |
| API endpoint returns 404 | Endpoint not registered | Export router from `src/routers/__init__.py` |
| Schema import fails | `ModuleNotFoundError` for models | Export models from `src/models/__init__.py` |
| Relative imports fail | `ImportError` for `.module` | Check package structure, ensure `__init__.py` exists |
| Monaco editor SSR error | Server-side rendering fails for Monaco | Use `dynamic(() => import("@monaco-editor/react"), { ssr: false })` |
| Next.js navigation not working | `<a>` tag causes full page reload | Replace with `Link` from `next/link` |
| Next.js v16 params error | `params` is a Promise | Use `const { param } = use(params)` |
| Tests fail due to database | Database not available | Use `AsyncMock` for `AsyncSession` |
| A2A protocol messages fail | Wrong enum values or field names | Update to snake_case and lowercase enum values |
| FastEmbed model loading slow | First embedding call takes time | Use singleton pattern with lazy model loading |
| Celery task async compatibility | `async` function calls fail in sync Celery | Use `asyncio.run(_run())` to wrap async operations |
| Qdrant connection fails | Wrong URL configuration in Docker | Use service name: `http://qdrant:6333` in docker-compose.yml |
| RTK Query reducer conflict | Duplicate `reducerPath` error | Use `createApi` with unique `reducerPath` instead of `injectEndpoints` |

---

## Phase 7 — MCP Server, Observability, & Production Hardening

| Issue | Root Cause | Solution | Impact |
|-------|------------|----------|--------|
| FastMCP API incompatibility | Subtask plan used low-level `mcp.Server` but SDK v1.27.0 prefers `FastMCP` | Switched to `FastMCP` framework with `@mcp.tool()` decorators | High: Simplified implementation and fixed transport issues |
| Streamable HTTP transport issues | Incorrect pattern for `StreamableHTTPServerTransport` with FastAPI | Used `FastMCP.streamable_http_app()` for proper transport handling | High: MCP endpoint now functional |
| Missing observability infrastructure directories | `infra/` directory didn't exist with subdirectories | Created `prometheus/`, `tempo/`, `grafana/provisioning/datasources/`, `grafana/dashboards/` | High: Observability stack config properly provisioned |
| JWT auth testing without database | JWT tests require crypto operations | Used `AsyncMock` for database dependency mocking with precise control | High: JWT tests run without database |
| SSRF prevention testing | IP validation requires network calls | Used `AsyncMock` to simulate `socket.getaddrinfo()` return values | High: SSRF tests reliable and fast |
| Health endpoint path mismatch | Tests used `/health` but API registers at `/api/v1/health` | Updated tests to use correct path prefix | Medium: Tests now pass |

> **Anti-Pattern:** Using low-level `mcp.Server` with manual transport handling
> **Best Practice:** Use `FastMCP` framework from `mcp>=1.27.0`:
> - Automatically handles Streamable HTTP transport via `streamable_http_app()`
> - Manages `StreamableHTTPSessionManager` lifecycle internally
> - Produces identical wire-level behavior (same JSON-RPC protocol)
> - Less boilerplate and more maintainable

> **Anti-Pattern:** Not setting `stateless_http=True` for horizontally-scaled deployments
> **Best Practice:** Set `stateless_http=True` on `FastMCP` instance for production deployments where session state should not be held server-side between requests.

> **Anti-Pattern:** Missing infrastructure directories for observability configs
> **Best Practice:** Create required directory structure before writing config files:
> ```bash
> mkdir -p rag-pipeline/infra/prometheus/
> mkdir -p rag-pipeline/infra/tempo/
> mkdir -p rag-pipeline/infra/grafana/provisioning/datasources/
> mkdir -p rag-pipeline/infra/grafana/dashboards/
> ```

> **Anti-Pattern:** Testing JWT with actual database or crypto operations
> **Best Practice:** Use `AsyncMock` to simulate database session and crypto operations for fast, isolated tests.

> **Anti-Pattern:** Using localhost IP for SSRF testing without mocking
> **Best Practice:** Use `AsyncMock` to simulate `socket.getaddrinfo()` return values for testing IP blocking logic.

> **Anti-Pattern:** Testing health endpoints with incorrect path prefix
> **Best Practice:** Verify endpoint paths registered in `main.py` before writing tests. FastAPI routers use prefix path defined during registration.

> **Anti-Pattern:** Not documenting FastMCP vs Server API differences
> **Best Practice:** Always verify SDK API patterns against current documentation. The high-level `FastMCP` framework is recommended for most use cases, while the low-level `Server` API is for advanced custom transport implementations.

---

## Quick Reference: Common Issues & Solutions

*This document is auto-generated from project lessons learned and should be updated as new issues are discovered.*
