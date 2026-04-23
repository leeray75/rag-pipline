# RAG Pipeline — AI Knowledge Base Ingestion System

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-purple.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.2+-black.svg)](https://nextjs.org/)

A production-grade document ingestion pipeline that crawls documentation websites, converts HTML to structured Markdown, validates quality via AI agents, and ingests into a Qdrant vector database for RAG (Retrieval-Augmented Generation) retrieval.

## Overview

The RAG Pipeline automates the entire process of building an AI knowledge base from documentation websites:

```
URL → Fetch → Convert → Audit Agent → Correction Agent → Human Review → Chunk → Embed → Qdrant
```

### Key Features

- **Automated Content Discovery**: Crawl documentation sites and discover linked pages using static and browser rendering modes
- **AI-Powered Quality Control**: Schema validation and quality assessment using LangGraph agents with OpenAI-compatible LLM (qwen3-coder-next)
- **Human-in-the-Loop Review**: Interactive review dashboard with Monaco editor, diff viewer, and approval workflow
- **Vector Embeddings**: Local ONNX embeddings with FastEmbed (BAAI/bge-small-en-v1.5)
- **Vector Search**: Qdrant integration for semantic search and RAG retrieval
- **Production Hardening**: JWT authentication, rate limiting, SSRF prevention, observability stack

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 22+
- pnpm 9+
- Python 3.13+

### Development Setup

```bash
# Clone and install
git clone <repo-url>
cd rag-pipeline
pnpm install

# Install API dependencies
cd apps/api && pip install -e ".[dev]"
playwright install chromium
cd ../..

# Start infrastructure services
cd infra && docker compose up -d

# Run database migrations
cd ../apps/api && alembic upgrade head

# Start development servers
cd ../..
pnpm dev  # starts both API and web
```

### Docker Compose Commands

```bash
# Build all services
docker compose -f ./infra/docker-compose.yml build

# Start all services
docker compose -f ./infra/docker-compose.yml up -d

# Stop all services
docker compose -f ./infra/docker-compose.yml down

# View service status
docker compose ps

# View logs
docker compose logs -f
```

### Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost/ (Traefik) |
| API | http://localhost/api/v1 (Traefik) |
| API Docs | http://localhost/api/docs (Traefik) |
| Traefik Dashboard | http://localhost:8080 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Qdrant | http://localhost:6333 |
| Qdrant gRPC | localhost:6334 |

### First Ingestion

```bash
# Create an ingestion job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/docs",
    "crawl_all_docs": true
  }'

# Trigger the audit workflow
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/audit

# Trigger chunking and embedding
curl -X POST http://localhost:8000/api/v1/ingest/jobs/{job_id}/chunk
curl -X POST http://localhost:8000/api/v1/ingest/jobs/{job_id}/embed \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "my-docs"}'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Ingestion Pipeline Flow                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Input                                                           │
│     └── URL (documentation site or page)                           │
│                                                                      │
│  2. Crawl                                                           │
│     ├── Fetcher (httpx + Playwright)                               │
│     ├── Link Discovery (CSS selectors + LLM fallback)              │
│     └── Staging (local files)                                      │
│                                                                      │
│  3. Convert                                                         │
│     └── markitdown (HTML → Markdown with frontmatter)             │
│                                                                      │
│  4. Audit                                                           │
│     └── LangGraph 6-node workflow:                                 │
│         ├── validate_schema (deterministic rules)                  │
│         ├── assess_quality (OpenAI-compatible LLM)                │
│         ├── check_duplicates (content hashing)                     │
│         └── compile_report                                         │
│                                                                      │
│  5. Correction                                                      │
│     └── A2A Protocol Loop:                                         │
│         ├── Audit Agent → Error Report                            │
│         ├── Correction Agent → Fixed Content                      │
│         └── Loop until approved or max rounds reached              │
│                                                                      │
│  6. Human Review                                                    │
│     └── Monaco editor + diff viewer with approval workflow         │
│                                                                      │
│  7. Ingest                                                          │
│     ├── Chunking (tiktoken-aware, heading-path tracking)           │
│     ├── Embedding (FastEmbed ONNX)                                │
│     └── Qdrant upsert (vector storage)                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## API Documentation

FastAPI auto-generates OpenAPI docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme"}'

# Use token
curl http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer <token>"
```

### Environment Variables

See [`apps/api/.env.example`](apps/api/.env.example) for all configuration options.

## MCP Integration

The pipeline exposes its tools via the Model Context Protocol (MCP) **Streamable HTTP transport** (MCP spec 2025-03-26). A single endpoint handles all clients:

```
POST http://localhost/mcp
```

Note: Traefik routes `/mcp` to the API service on port 8000.

### Available Tools

| Tool Name | Description |
|-----------|-------------|
| `ingest_url` | Create ingestion job from URL |
| `get_job_status` | Get job status and progress |
| `list_documents` | List documents for a job |
| `get_audit_report` | Get audit report JSON |
| `search_knowledge_base` | Query Qdrant vector store |
| `approve_job` | Trigger human approval workflow |
| `get_collection_stats` | Get Qdrant collection statistics |

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-pipeline": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Quick Test

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Observability (Open-Source Stack)

The pipeline includes a complete observability stack:

| Component | URL | Purpose |
|-----------|-----|---------|
| Grafana | http://localhost:3001 | Dashboards and exploration |
| Prometheus | http://localhost:9090 | Metrics scraping |
| Tempo | http://localhost:3200 | Distributed tracing |
| Loki | http://localhost:3100 | Log aggregation |

### Viewing Traces

1. Go to Grafana → Explore → Tempo
2. Filter by `service.name=rag-pipeline-api`
3. Click on spans to view agent runs

### Viewing Logs

1. Go to Grafana → Explore → Loki
2. Query: `{job="rag-pipeline-api"} | json | level="error"`

## Production Deployment

```bash
# Validate merged configuration
docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml config

# Start production stack
docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml up -d

# Run migrations
docker compose exec api alembic upgrade head

# Check service status
docker compose ps
```

### Common Docker Compose Commands

```bash
# Build all services
docker compose -f ./infra/docker-compose.yml build

# Start services (development)
docker compose -f ./infra/docker-compose.yml up -d

# Start services (production with prod overrides)
docker compose -f ./infra/docker-compose.yml -f ./infra/docker-compose.prod.yml up -d

# Stop services
docker compose -f ./infra/docker-compose.yml down

# Stop and remove volumes
docker compose -f ./infra/docker-compose.yml down -v

# View service status
docker compose ps

# View logs for all services
docker compose logs -f

# View logs for specific service
docker compose logs -f api
docker compose logs -f web
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f qdrant

# Validate configuration
docker compose config
```

### Production Environment Variables

```env
ENVIRONMENT=production
LOG_FORMAT=json
OTEL_ENABLED=true
JWT_SECRET=<generate-with-secrets>
RATE_LIMIT=1000/minute
```

## Project Structure

```
rag-pipeline/
├── apps/
│   ├── api/              # FastAPI backend (Python)
│   │   ├── src/
│   │   │   ├── agents/   # LangGraph agents
│   │   │   ├── auth/     # Authentication
│   │   │   ├── crawlers/ # URL fetching
│   │   │   ├── converters/ # HTML to Markdown
│   │   │   ├── embeddings/ # FastEmbed models
│   │   │   ├── ingest/   # Chunking & embedding
│   │   │   ├── mcp/      # MCP server
│   │   │   ├── models/   # SQLAlchemy models
│   │   │   ├── routers/  # API routes
│   │   │   ├── schemas/  # Pydantic schemas
│   │   │   ├── security/ # SSRF prevention
│   │   │   ├── workers/  # Celery tasks
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── web/              # Next.js frontend
│       ├── src/
│       │   ├── app/      # App Router pages
│       │   ├── components/ # UI components
│       │   ├── features/   # Feature modules
│       │   ├── store/      # Redux store
│       │   └── lib/        # Utilities
│       ├── Dockerfile
│       └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml
│   └── traefik-config.yml
├── docs/                 # This documentation
├── ai-workspace/         # Planning & reports
├── package.json
├── pnpm-workspace.yaml
└── turbo.json
```

## Project Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Mono-repo, Infrastructure, FastAPI, Next.js, CI/CD |
| Phase 2 | ✅ Complete | URL Crawler, HTML Fetcher, Markdown Converter |
| Phase 3 | ✅ Complete | Audit Agent with LangGraph |
| Phase 4 | ✅ Complete | Correction Agent with A2A Protocol |
| Phase 5 | ✅ Complete | Human Review Interface |
| Phase 6 | ✅ Complete | Chunking, Embedding, Qdrant Integration |
| Phase 7 | ✅ Complete | MCP Server, Observability, Auth, Production Hardening |

## Technology Stack

### Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Web Framework | FastAPI | 0.135.3 |
| ORM | SQLAlchemy | 2.0.49 |
| Migrations | Alembic | 1.18.4 |
| Task Queue | Celery | 5.6.3 |
| Workflow Orchestrator | LangGraph | 1.1.6 |
| A2A Protocol | a2a-sdk | 0.3.26 |
| MCP Server | mcp | 1.27.0 |
| LLM Integration | langchain-openai | >=0.3.0 |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Next.js | 16.2.3 |
| State Management | Redux Toolkit | 2.11.2 |
| API Client | RTK Query | - |
| UI Library | shadcn/ui | 4.x |
| Markdown Editor | Monaco Editor | 4.7.0 |

### Infrastructure

| Component | Technology | Version |
|-----------|------------|---------|
| Container Runtime | Docker | 27.x |
| Database | PostgreSQL | 17 |
| Cache | Redis | 7.x |
| Vector DB | Qdrant | 1.13+ |
| Reverse Proxy | Traefik | 3.6.13 |

### Observability

| Component | Technology | Version |
|-----------|------------|---------|
| Metrics | Prometheus | 3.4 |
| Tracing | Grafana Tempo | 2.7 |
| Logging | Grafana Loki | 3.5 |
| Dashboards | Grafana | 11.6 |

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Step-by-step setup guide |
| [Architecture](docs/architecture.md) | System architecture and data flow |
| [API Reference](docs/api-reference.md) | Complete API documentation |
| [Operations Runbook](docs/runbook.md) | Common issues and solutions |
| [Lessons Learned](ai-workspace/docs/lessons-learned.md) | Anti-patterns and best practices |

## Contributing

1. Follow the phase plan structure in `ai-workspace/plans/`
2. Each phase has subtasks with specific validation criteria
3. Run validation scripts after implementing each phase
4. Update documentation as you add features

## License

MIT License - See [LICENSE](LICENSE) for details.

## Support

For issues and questions:

- Check the [Operations Runbook](docs/runbook.md) for common issues
- Review [Lessons Learned](ai-workspace/docs/lessons-learned.md) for anti-patterns
- Consult the [Architecture](docs/architecture.md) for system design details

---

*Last updated: 2026-04-23*
