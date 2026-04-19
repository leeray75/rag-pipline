# Production Hardening — RAG Context Documents

> **Phase**: Phase 7, Subtasks 4 & 5 — Production Hardening + Tests & Validation  
> **Created**: 2026-04-19  
> **Purpose**: RAG context documents for LLM knowledge gaps when implementing production hardening

> **Open-source only**: All tools are free and self-hosted. No paid SaaS services (LangSmith, Sentry, Datadog, etc.) are used. Agent observability is provided by OpenTelemetry → Grafana Tempo. Error tracking is provided by structlog JSON logs → Grafana Loki + Prometheus error counters.

These documents are optimized for use as RAG (Retrieval-Augmented Generation) context. Each document covers a specific technology with exact API signatures, working code examples, and common pitfalls.

---

## Document Index

| Document | Technology | Version | Key Topics |
|---|---|---|---|
| [`docker-compose-v2-production-rag.md`](./docker-compose-v2-production-rag.md) | Docker Compose V2 | V2 (Compose spec) | Production overlay, healthcheck, deploy.resources, restart policy |
| [`sqlalchemy-2.0-async-alembic-rag.md`](./sqlalchemy-2.0-async-alembic-rag.md) | SQLAlchemy 2.0 + Alembic | 2.0.49 / 1.18.4 | Async ORM, Mapped columns, content_hash, migrations |
| [`fastapi-health-checks-rag.md`](./fastapi-health-checks-rag.md) | FastAPI Health Checks | 0.135.3 | Liveness, readiness, Docker integration, 503 responses |
| [`pytest-asyncio-fastapi-testing-rag.md`](./pytest-asyncio-fastapi-testing-rag.md) | pytest-asyncio + httpx | 0.24+ / 0.27+ | Async tests, FastAPI client, MCP tests, JWT tests, re-ingestion tests |
| [`production-hardening-integration-overview-rag.md`](./production-hardening-integration-overview-rag.md) | Full Stack | All | main.py order, env vars, file inventory, done-when checklist |

---

## Technology Versions

| Component | Package | Version |
|---|---|---|
| SQLAlchemy | `sqlalchemy[asyncio]` | 2.0.49 |
| Alembic | `alembic` | 1.18.4 |
| FastAPI | `fastapi` | 0.135.3 |
| pytest-asyncio | `pytest-asyncio` | 0.24+ |
| httpx | `httpx` | 0.27+ |
| Docker Compose | `docker compose` | V2 |

---

## Subtask Coverage

### Subtask 4 — Production Hardening
- [`docker-compose-v2-production-rag.md`](./docker-compose-v2-production-rag.md) — Production overlay pattern, resource limits, healthchecks
- [`sqlalchemy-2.0-async-alembic-rag.md`](./sqlalchemy-2.0-async-alembic-rag.md) — `content_hash` column, delta detection, migrations
- [`fastapi-health-checks-rag.md`](./fastapi-health-checks-rag.md) — `/health` and `/health/ready` endpoints

### Subtask 5 — Tests & Validation
- [`pytest-asyncio-fastapi-testing-rag.md`](./pytest-asyncio-fastapi-testing-rag.md) — MCP, auth, SSRF, health, re-ingestion tests

---

## Observability (Open-Source Only)

Error tracking and agent observability are handled entirely by the open-source stack configured in Subtask 2:

| Need | Solution |
|---|---|
| Agent run traces | OpenTelemetry → Grafana Tempo |
| Error logs | structlog JSON → Grafana Loki |
| Error rate metrics | `rag_jobs_failed_total` counter → Prometheus → Grafana |
| Distributed tracing | OTel spans across FastAPI + Celery + httpx |

---

## RAG Usage Notes

- Each document has a `RAG_METADATA` comment block at the top with `topic`, `library`, `version`, and `tags` for retrieval filtering
- The integration overview is the best starting point for understanding the complete `main.py` initialization order
- Documents are self-contained — each can be used independently as context
- Code examples match the exact API versions listed above

---

## Related Files

- **Subtask 4 plan**: [`../plans/phase-7/subtasks/phase-7-subtask-4-production-hardening.md`](../plans/phase-7/subtasks/phase-7-subtask-4-production-hardening.md)
- **Subtask 5 plan**: [`../plans/phase-7/subtasks/phase-7-subtask-5-langsmith-sentry-tests-validation.md`](../plans/phase-7/subtasks/phase-7-subtask-5-langsmith-sentry-tests-validation.md)
- **Observability docs**: [`../observability/README.md`](../observability/README.md)
