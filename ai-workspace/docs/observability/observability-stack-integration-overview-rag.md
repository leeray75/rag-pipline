# Observability Stack Integration Overview — RAG Reference Document

<!-- RAG_METADATA
topic: observability, integration, architecture
stack: structlog + opentelemetry + prometheus + grafana-tempo + grafana-loki + grafana
version: phase-7-subtask-2
tags: observability, tracing, metrics, logging, fastapi, celery, docker-compose, integration
use_case: phase-7-observability-stack
-->

## Overview

This document describes how the full observability stack integrates in the RAG Pipeline project. The stack implements the **three pillars of observability**:

| Pillar | Tool | Purpose |
|---|---|---|
| **Logs** | structlog → Loki | Structured JSON logs, searchable in Grafana |
| **Traces** | OpenTelemetry → Tempo | Distributed request tracing across FastAPI + Celery |
| **Metrics** | Prometheus + prometheus-fastapi-instrumentator | RED metrics, custom counters/histograms |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG Pipeline API (FastAPI)                    │
│                                                                  │
│  structlog (JSON logs)                                           │
│  ├── LOG_FORMAT=json → stdout                                    │
│  └── trace_id/span_id injected from OTel context                │
│                                                                  │
│  OpenTelemetry SDK                                               │
│  ├── FastAPIInstrumentor → auto-spans for HTTP routes            │
│  ├── CeleryInstrumentor → auto-spans for Celery tasks            │
│  ├── HTTPXClientInstrumentor → auto-spans for httpx calls        │
│  └── BatchSpanProcessor → OTLPSpanExporter → Tempo:4317         │
│                                                                  │
│  prometheus-fastapi-instrumentator                               │
│  ├── http_request_duration_seconds (histogram)                   │
│  ├── http_requests_total (counter)                               │
│  └── /metrics endpoint → scraped by Prometheus                  │
│                                                                  │
│  Custom Metrics (prometheus-client)                              │
│  ├── rag_jobs_created_total                                      │
│  ├── rag_jobs_completed_total                                    │
│  ├── rag_jobs_failed_total                                       │
│  ├── rag_agent_rounds_per_job                                    │
│  ├── rag_embed_latency_seconds                                   │
│  ├── rag_chunks_embedded_total                                   │
│  └── rag_qdrant_upsert_latency_seconds                          │
└──────────────────────────────────────────────────────────────────┘
         │ OTLP gRPC          │ /metrics scrape    │ stdout logs
         ▼                    ▼                    ▼
    ┌─────────┐         ┌──────────┐         ┌──────────┐
    │  Tempo  │         │Prometheus│         │  Loki    │
    │  :4317  │         │  :9090   │         │  :3100   │
    │  :3200  │         │          │         │          │
    └────┬────┘         └────┬─────┘         └────┬─────┘
         │                   │                    │
         └───────────────────┴────────────────────┘
                             │
                        ┌────▼─────┐
                        │ Grafana  │
                        │  :3001   │
                        │          │
                        │ Dashboards│
                        │ Explore  │
                        └──────────┘
```

---

## FastAPI `main.py` Integration Order

The order of initialization in `src/main.py` is critical:

```python
# 1. Configure logging FIRST (before any imports that log)
from src.logging_config import configure_logging
configure_logging()

import structlog
log = structlog.get_logger(__name__)

# 2. Create FastAPI app
from fastapi import FastAPI
app = FastAPI(
    title="RAG Pipeline API",
    version="1.0.0",
)

# 3. Add middleware (BEFORE instrumentation)
# ... add CORS, auth middleware here ...

# 4. Configure OpenTelemetry (instruments the app)
from src.telemetry import configure_telemetry
configure_telemetry(app)

# 5. Configure Prometheus metrics (exposes /metrics)
from src.metrics import configure_metrics
configure_metrics(app)

# 6. Include routers
from src.routers import jobs, chunks, health
app.include_router(health.router)
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(chunks.router, prefix="/api/v1")

log.info("application_started", version="1.0.0")
```

---

## Environment Variables Reference

| Variable | Default | Component | Description |
|---|---|---|---|
| `LOG_FORMAT` | `console` | structlog | `json` for production, `console` for dev |
| `LOG_LEVEL` | `INFO` | structlog | Minimum log level |
| `OTEL_ENABLED` | `true` | OpenTelemetry | Toggle tracing on/off |
| `OTEL_SERVICE_NAME` | `rag-pipeline-api` | OpenTelemetry | Service name in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://tempo:4317` | OpenTelemetry | Tempo gRPC endpoint |
| `ENVIRONMENT` | `development` | OpenTelemetry | Deployment environment label |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Metrics | Model name in BUILD_INFO |

---

## Docker Compose Full Stack

```yaml
version: "3.9"

networks:
  observability:
    driver: bridge

volumes:
  prometheus-data:
  tempo-data:
  loki-data:
  grafana-data:

services:
  api:
    build: ./apps/api
    ports:
      - "8000:8000"
    environment:
      - LOG_FORMAT=json
      - LOG_LEVEL=INFO
      - OTEL_ENABLED=true
      - OTEL_SERVICE_NAME=rag-pipeline-api
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
      - ENVIRONMENT=development
    networks:
      - observability
    depends_on:
      - tempo
      - prometheus
      - loki

  prometheus:
    image: prom/prometheus:v3.4.0
    ports:
      - "9090:9090"
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--web.enable-lifecycle"
    networks:
      - observability

  tempo:
    image: grafana/tempo:2.7
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./infra/tempo/tempo.yaml:/etc/tempo.yaml:ro
      - tempo-data:/var/tempo
    ports:
      - "3200:3200"
      - "4317:4317"
      - "4318:4318"
    networks:
      - observability

  loki:
    image: grafana/loki:3.5
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - ./infra/loki/loki-config.yaml:/etc/loki/local-config.yaml:ro
      - loki-data:/var/loki
    networks:
      - observability

  grafana:
    image: grafana/grafana:11.6
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_FEATURE_TOGGLES_ENABLE=traceqlEditor
    volumes:
      - ./infra/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana-data:/var/lib/grafana
    networks:
      - observability
    depends_on:
      - prometheus
      - tempo
      - loki
```

---

## Trace → Log Correlation

When a request arrives at FastAPI:

1. `FastAPIInstrumentor` creates a span with `trace_id` and `span_id`
2. structlog's `add_otel_context` processor injects `trace_id` and `span_id` into every log entry
3. Logs are shipped to Loki with `trace_id` in the JSON body
4. In Grafana Explore → Loki, clicking a log entry with `trace_id` opens the trace in Tempo

```python
# Processor to add OTel context to structlog
from opentelemetry import trace

def add_otel_context(logger, method, event_dict):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

---

## Metric → Trace Correlation (Exemplars)

Prometheus exemplars link metric data points to specific traces:

```python
from prometheus_client import Histogram
from opentelemetry import trace

EMBED_LATENCY = Histogram("rag_embed_latency_seconds", "...", ["model_name"])

def embed_with_exemplar(chunks, model):
    span = trace.get_current_span()
    ctx = span.get_span_context()
    trace_id = format(ctx.trace_id, "032x") if span.is_recording() else ""
    
    with EMBED_LATENCY.labels(model_name=model).time():
        # prometheus-client automatically records exemplar if trace_id is set
        result = embed_batch(chunks)
    return result
```

---

## Verification Checklist

| Check | Command | Expected |
|---|---|---|
| Structured JSON logs | `LOG_FORMAT=json uvicorn src.main:app` | JSON output to stdout |
| Prometheus metrics | `curl localhost:8000/metrics \| grep rag_` | `rag_*` metrics present |
| Tempo receiving traces | Submit job → Grafana Explore → Tempo | Trace visible |
| Loki receiving logs | Grafana Explore → Loki → `{job="rag-pipeline-api"}` | Logs visible |
| Grafana data sources | Grafana → Connections → Data Sources | Prometheus, Tempo, Loki all green |
| Dashboard loads | Grafana → Dashboards → RAG Pipeline | Pipeline Throughput dashboard |

---

## File Inventory for Phase 7 Subtask 2

| File | Purpose |
|---|---|
| `apps/api/src/logging_config.py` | structlog configuration |
| `apps/api/src/telemetry.py` | OpenTelemetry TracerProvider + instrumentation |
| `apps/api/src/metrics.py` | Prometheus custom metrics + Instrumentator |
| `apps/api/src/main.py` | Integration point (configure_logging, configure_telemetry, configure_metrics) |
| `infra/prometheus/prometheus.yml` | Prometheus scrape config |
| `infra/tempo/tempo.yaml` | Tempo OTLP receiver + storage config |
| `infra/loki/loki-config.yaml` | Loki ingestion + storage config |
| `infra/grafana/provisioning/datasources/datasources.yml` | Grafana data source provisioning |
| `infra/grafana/provisioning/dashboards/dashboards.yml` | Grafana dashboard provider config |
| `infra/grafana/dashboards/pipeline-throughput.json` | Pipeline throughput dashboard |

---

## Common Integration Pitfalls

1. **Initialization order** — `configure_logging()` must be called before any `structlog.get_logger()` call. `configure_telemetry(app)` must be called after `app = FastAPI(...)`.
2. **`insecure=True` for Tempo** — Required for local Docker deployments without TLS.
3. **Docker network** — All services must be on the same Docker network to resolve hostnames (`tempo`, `prometheus`, `loki`).
4. **Port 3000 conflict** — Grafana default port 3000 may conflict with other services. Map to 3001 in Docker Compose.
5. **Prometheus scrape target** — Use Docker service name (`api:8000`), not `localhost:8000`.
6. **`/mcp` exclusion from metrics** — The MCP Streamable HTTP endpoint generates high-cardinality spans. Exclude it from prometheus-fastapi-instrumentator.
7. **Loki log ordering** — Ensure system clocks are synchronized. Loki rejects out-of-order logs per stream.

---

## Sources
- https://www.structlog.org/en/stable/ (structlog 25.5.0)
- https://opentelemetry.io/docs/languages/python/ (OTel Python, updated 2026-01-27)
- https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- https://github.com/trallnag/prometheus-fastapi-instrumentator (v7.1.0)
- https://grafana.com/docs/tempo/latest/ (Tempo 2.10.x)
- https://grafana.com/docs/loki/latest/ (Loki 3.7.x)
- https://grafana.com/docs/grafana/latest/administration/provisioning/ (Grafana 12.4)
