# Phase 7, Subtask 2 — Observability Stack

> **Phase**: Phase 7 — MCP Server, Observability & Production Hardening
> **Prerequisites**: Phase 6 complete; Phase 7 Subtask 1 complete (dependencies installed, MCP server working via Streamable HTTP at `POST /mcp`)
> **Scope**: Structured logging with structlog, OpenTelemetry distributed tracing, Prometheus metrics, and infrastructure config files for Tempo, Prometheus, Loki, and Grafana

---

## Relevant Technology Stack

| Package / Component | Version | Install |
|---|---|---|
| structlog | 25.4.0 | `pip install structlog` |
| opentelemetry-api | 1.33.0 | `pip install opentelemetry-api` |
| opentelemetry-sdk | 1.33.0 | `pip install opentelemetry-sdk` |
| opentelemetry-instrumentation-fastapi | 0.54b0 | `pip install opentelemetry-instrumentation-fastapi` |
| opentelemetry-instrumentation-celery | 0.54b0 | `pip install opentelemetry-instrumentation-celery` |
| opentelemetry-instrumentation-httpx | 0.54b0 | `pip install opentelemetry-instrumentation-httpx` |
| opentelemetry-exporter-otlp | 1.33.0 | `pip install opentelemetry-exporter-otlp` |
| prometheus-fastapi-instrumentator | 7.1.0 | `pip install prometheus-fastapi-instrumentator` |
| Grafana | 11.6 | Docker image `grafana/grafana:11.6` |
| Grafana Tempo | 2.7 | Docker image `grafana/tempo:2.7` |
| Prometheus | 3.4 | Docker image `prom/prometheus:3.4` |
| Grafana Loki | 3.5 | Docker image `grafana/loki:3.5` |

> All Python packages were added to `pyproject.toml` in Subtask 1. This subtask creates the application code and infrastructure config files.

---

## Files to Create/Modify

| Action | File Path |
|---|---|
| Create | `rag-pipeline/apps/api/src/logging_config.py` |
| Create | `rag-pipeline/apps/api/src/telemetry.py` |
| Create | `rag-pipeline/apps/api/src/metrics.py` |
| Create | `rag-pipeline/infra/prometheus/prometheus.yml` |
| Create | `rag-pipeline/infra/tempo/tempo.yaml` |
| Create | `rag-pipeline/infra/grafana/provisioning/datasources/datasources.yml` |
| Create | `rag-pipeline/infra/grafana/dashboards/pipeline-throughput.json` |
| Modify | `rag-pipeline/apps/api/src/main.py` (add logging, telemetry, metrics init) |

---

## Step 1: Configure Structured Logging

**Working directory**: `rag-pipeline/apps/api/`

### 1.1 Create `src/logging_config.py`

```python
"""Structured logging configuration using structlog.

Outputs JSON in production, pretty-printed in development.
"""

import logging
import os
import sys

import structlog


def configure_logging() -> None:
    """Configure structlog for the application.

    Set LOG_FORMAT=json for production (JSON lines).
    Set LOG_FORMAT=console for development (colored output).
    """
    log_format = os.getenv("LOG_FORMAT", "console")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        # Production: JSON output for Loki / CloudWatch
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level))
```

### 1.2 Initialize in `src/main.py`

Add at the **top** of the file, before `app` creation:

```python
from src.logging_config import configure_logging
configure_logging()
```

---

## Step 2: Add OpenTelemetry Distributed Tracing

### 2.1 Create `src/telemetry.py`

```python
"""OpenTelemetry configuration — traces exported to Grafana Tempo via OTLP."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_telemetry(app=None) -> None:
    """Set up OpenTelemetry tracing.

    Instruments FastAPI, Celery, and httpx.
    Exports traces to OTLP endpoint (Grafana Tempo).
    """
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
    service_name = os.getenv("OTEL_SERVICE_NAME", "rag-pipeline-api")

    if os.getenv("OTEL_ENABLED", "true").lower() != "true":
        return

    # Resource identifies this service in traces
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # Set up the tracer provider
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    if app:
        FastAPIInstrumentor.instrument_app(app)

    # Instrument Celery
    CeleryInstrumentor().instrument()

    # Instrument httpx (used by crawlers)
    HTTPXClientInstrumentor().instrument()
```

### 2.2 Initialize in `src/main.py` — after app creation

```python
from src.telemetry import configure_telemetry

# After: app = FastAPI(...)
configure_telemetry(app)
```

---

## Step 3: Add Prometheus Metrics

### 3.1 Create `src/metrics.py`

```python
"""Prometheus metrics — custom counters and histograms for pipeline monitoring."""

import os

from prometheus_client import Counter, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator

# ---- Custom metrics ----

JOBS_CREATED = Counter(
    "rag_jobs_created_total",
    "Total ingestion jobs created",
    ["source_type"],
)

JOBS_COMPLETED = Counter(
    "rag_jobs_completed_total",
    "Total ingestion jobs completed successfully",
)

JOBS_FAILED = Counter(
    "rag_jobs_failed_total",
    "Total ingestion jobs that failed",
    ["failure_reason"],
)

AGENT_ROUNDS = Histogram(
    "rag_agent_rounds_per_job",
    "Number of audit-correction rounds per job",
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
)

EMBED_LATENCY = Histogram(
    "rag_embed_latency_seconds",
    "Time to embed a batch of chunks",
    ["model_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

CHUNKS_EMBEDDED = Counter(
    "rag_chunks_embedded_total",
    "Total chunks embedded and upserted to Qdrant",
    ["collection_name"],
)

QDRANT_UPSERT_LATENCY = Histogram(
    "rag_qdrant_upsert_latency_seconds",
    "Time to upsert a batch to Qdrant",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

BUILD_INFO = Info(
    "rag_pipeline_build",
    "Build information for the RAG pipeline",
)
BUILD_INFO.info(
    {
        "version": "1.0.0",
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
    }
)


def configure_metrics(app) -> Instrumentator:
    """Instrument FastAPI and expose /metrics endpoint.

    Returns the instrumentator for further customization.
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
        # NOTE: /mcp (not /mcp/sse) — the MCP endpoint is Streamable HTTP at POST /mcp
        excluded_handlers=["/health", "/metrics", "/mcp"],
        inprogress_name="rag_http_requests_inprogress",
        inprogress_labels=True,
    )

    instrumentator.instrument(app)
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    return instrumentator
```

### 3.2 Initialize in `src/main.py` — after app creation

```python
from src.metrics import configure_metrics

# After: app = FastAPI(...)
configure_metrics(app)
```

---

## Step 4: Create Observability Infrastructure Config Files

**Working directory**: `rag-pipeline/infra/`

### 4.1 Create `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "rag-pipeline-api"
    static_configs:
      - targets: ["api:8000"]
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: "qdrant"
    static_configs:
      - targets: ["qdrant:6333"]
    metrics_path: /metrics
    scrape_interval: 30s
```

### 4.2 Create `tempo/tempo.yaml`

```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"
        http:
          endpoint: "0.0.0.0:4318"

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
```

### 4.3 Create `grafana/provisioning/datasources/datasources.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

### 4.4 Create `grafana/dashboards/pipeline-throughput.json`

```json
{
  "dashboard": {
    "title": "RAG Pipeline — Throughput",
    "uid": "rag-throughput",
    "panels": [
      {
        "title": "Jobs Created (rate)",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(rag_jobs_created_total[5m])",
            "legendFormat": "{{source_type}}"
          }
        ],
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 }
      },
      {
        "title": "Agent Rounds Distribution",
        "type": "histogram",
        "targets": [
          {
            "expr": "rag_agent_rounds_per_job_bucket",
            "legendFormat": "{{le}} rounds"
          }
        ],
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 }
      },
      {
        "title": "Embed Latency P95",
        "type": "stat",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(rag_embed_latency_seconds_bucket[5m]))",
            "legendFormat": "p95"
          }
        ],
        "gridPos": { "h": 4, "w": 6, "x": 0, "y": 8 }
      },
      {
        "title": "Chunks Embedded Total",
        "type": "stat",
        "targets": [
          {
            "expr": "rag_chunks_embedded_total",
            "legendFormat": "{{collection_name}}"
          }
        ],
        "gridPos": { "h": 4, "w": 6, "x": 6, "y": 8 }
      },
      {
        "title": "Qdrant Upsert Latency",
        "type": "timeseries",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(rag_qdrant_upsert_latency_seconds_bucket[5m]))",
            "legendFormat": "p95"
          }
        ],
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 }
      }
    ]
  }
}
```

---

## Step 5: Summary of `src/main.py` Changes

After completing this subtask, `src/main.py` should have these additions (in order):

```python
# At the top, before app creation:
from src.logging_config import configure_logging
configure_logging()

# ... app = FastAPI(...) ...

# After app creation:
from src.telemetry import configure_telemetry
configure_telemetry(app)

from src.metrics import configure_metrics
configure_metrics(app)
```

---

## Done-When Checklist

| # | Criterion | Verify |
|---|-----------|--------|
| 1 | Structured logging outputs JSON in production | `LOG_FORMAT=json python -m uvicorn src.main:app` → JSON output |
| 2 | OpenTelemetry traces appear in Grafana Tempo | Submit a job → view trace in Grafana Explore → Tempo |
| 3 | Prometheus metrics at `/metrics` include `rag_*` counters | `curl localhost:8000/metrics \| grep rag_` |
| 4 | Grafana dashboard shows pipeline throughput | Open http://localhost:3001 → Pipeline Throughput dashboard |
| 5 | Grafana starts with pre-provisioned Prometheus, Tempo, and Loki data sources | Check Grafana → Configuration → Data Sources |

---

## Summary Report

Upon completion of this subtask, create a summary report at:
`rag-pipeline/ai-workspace/summary-reports/phase-7-subtask-2-observability-stack-summary.md`

The summary report must include:
- **Subtask**: Phase 7, Subtask 2 — Observability Stack
- **Status**: Complete / Partial / Blocked
- **Date**: {ISO 8601 date}
- **Files Created/Modified**: List every file path
- **Key Decisions**: Any deviations from the plan and why
- **Issues Encountered**: Problems and resolutions
- **Dependencies for Next Subtask**: What the next subtask needs to know
- **Verification Results**: Output of Done-When checklist items