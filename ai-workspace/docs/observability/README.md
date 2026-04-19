# Observability Stack — RAG Context Documents

> **Phase**: Phase 7, Subtask 2 — Observability Stack  
> **Created**: 2026-04-19  
> **Purpose**: RAG context documents for LLM knowledge gaps when implementing the observability stack

These documents are optimized for use as RAG (Retrieval-Augmented Generation) context. Each document covers a specific technology in the observability stack with:
- Exact API signatures and configuration schemas
- Working code examples
- Common pitfalls and gotchas
- Version-specific details

---

## Document Index

| Document | Technology | Version | Key Topics |
|---|---|---|---|
| [`structlog-25.x-rag.md`](./structlog-25.x-rag.md) | structlog | 25.5.0 | ProcessorFormatter, contextvars, JSON/console output, stdlib integration |
| [`opentelemetry-python-1.33.x-rag.md`](./opentelemetry-python-1.33.x-rag.md) | OpenTelemetry Python | 1.33.0 / 0.54b0 | TracerProvider, OTLP exporter, FastAPI/Celery/httpx instrumentation, spans |
| [`prometheus-3.x-fastapi-instrumentator-rag.md`](./prometheus-3.x-fastapi-instrumentator-rag.md) | Prometheus + instrumentator | 3.4 / 7.1.0 | Custom metrics, Counter/Histogram, prometheus.yml, PromQL |
| [`grafana-tempo-2.x-rag.md`](./grafana-tempo-2.x-rag.md) | Grafana Tempo | 2.7 | OTLP receiver, tempo.yaml, TraceQL, storage backends |
| [`grafana-loki-3.x-rag.md`](./grafana-loki-3.x-rag.md) | Grafana Loki | 3.5 | Log ingestion, LogQL, Promtail, label extraction, JSON parsing |
| [`grafana-11.x-provisioning-dashboards-rag.md`](./grafana-11.x-provisioning-dashboards-rag.md) | Grafana | 11.6 | Provisioning YAML, dashboard JSON model, panel types, grid layout |
| [`observability-stack-integration-overview-rag.md`](./observability-stack-integration-overview-rag.md) | Full Stack | All | Architecture, initialization order, Docker Compose, trace-log correlation |

---

## Technology Versions

| Component | Docker Image | Python Package |
|---|---|---|
| structlog | — | `structlog==25.5.0` |
| OpenTelemetry API | — | `opentelemetry-api==1.33.0` |
| OpenTelemetry SDK | — | `opentelemetry-sdk==1.33.0` |
| OTel FastAPI | — | `opentelemetry-instrumentation-fastapi==0.54b0` |
| OTel Celery | — | `opentelemetry-instrumentation-celery==0.54b0` |
| OTel httpx | — | `opentelemetry-instrumentation-httpx==0.54b0` |
| OTel OTLP Exporter | — | `opentelemetry-exporter-otlp==1.33.0` |
| prometheus-fastapi-instrumentator | — | `prometheus-fastapi-instrumentator==7.1.0` |
| Grafana | `grafana/grafana:11.6` | — |
| Grafana Tempo | `grafana/tempo:2.7` | — |
| Prometheus | `prom/prometheus:v3.4.0` | — |
| Grafana Loki | `grafana/loki:3.5` | — |

---

## RAG Usage Notes

- Each document has a `RAG_METADATA` comment block at the top with `topic`, `library`, `version`, and `tags` for retrieval filtering
- Documents are self-contained — each can be used independently as context
- The integration overview document is the best starting point for understanding how all components connect
- Code examples are production-ready and match the exact API versions listed above

---

## Related Files

- **Subtask plan**: [`../plans/phase-7/subtasks/phase-7-subtask-2-observability-stack.md`](../plans/phase-7/subtasks/phase-7-subtask-2-observability-stack.md)
- **Implementation files**:
  - `rag-pipeline/apps/api/src/logging_config.py`
  - `rag-pipeline/apps/api/src/telemetry.py`
  - `rag-pipeline/apps/api/src/metrics.py`
  - `rag-pipeline/infra/prometheus/prometheus.yml`
  - `rag-pipeline/infra/tempo/tempo.yaml`
  - `rag-pipeline/infra/grafana/provisioning/datasources/datasources.yml`
  - `rag-pipeline/infra/grafana/dashboards/pipeline-throughput.json`
