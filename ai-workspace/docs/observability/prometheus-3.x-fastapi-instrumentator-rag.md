# Prometheus 3.x + prometheus-fastapi-instrumentator 7.x — RAG Reference Document

<!-- RAG_METADATA
topic: metrics, monitoring, prometheus
library: prometheus-client, prometheus-fastapi-instrumentator
version: prometheus 3.4 (Docker), prometheus-fastapi-instrumentator 7.1.0
python_min: 3.9
tags: metrics, counters, histograms, gauges, fastapi, scraping, qdrant
use_case: phase-7-observability-stack
-->

## Overview

**Prometheus** is an open-source monitoring system that scrapes metrics from HTTP endpoints. **prometheus-fastapi-instrumentator** (v7.1.0) auto-instruments FastAPI with HTTP metrics and exposes a `/metrics` endpoint.

**Install**:
```bash
pip install prometheus-fastapi-instrumentator  # includes prometheus-client
```

**Docker image**: `prom/prometheus:v3.4.0`

---

## prometheus-fastapi-instrumentator — Quick Setup

```python
from prometheus_fastapi_instrumentator import Instrumentator

# Minimal (one-liner)
Instrumentator().instrument(app).expose(app)

# Production configuration
instrumentator = Instrumentator(
    should_group_status_codes=True,       # Group 2xx, 3xx, 4xx, 5xx
    should_ignore_untemplated=True,       # Ignore routes without path templates
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/metrics", "/mcp"],
    inprogress_name="rag_http_requests_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app)
instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
```

**Important**: Call `instrument(app)` and `expose(app)` AFTER `app = FastAPI(...)` and AFTER adding all middleware.

---

## Default Metrics Provided

| Metric | Type | Labels | Description |
|---|---|---|---|
| `http_requests_total` | Counter | `handler`, `status`, `method` | Total HTTP requests |
| `http_request_size_bytes` | Summary | `handler` | Request body sizes |
| `http_response_size_bytes` | Summary | `handler` | Response body sizes |
| `http_request_duration_seconds` | Histogram | `handler`, `method` | Request latency (few buckets) |
| `http_request_duration_highr_seconds` | Histogram | none | Request latency (high-resolution, 20+ buckets) |

---

## Custom Metrics with prometheus-client

```python
from prometheus_client import Counter, Histogram, Info

# Counter — monotonically increasing value
JOBS_CREATED = Counter(
    "rag_jobs_created_total",
    "Total ingestion jobs created",
    ["source_type"],          # label names
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

# Histogram — distribution of values
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

# Info — static build/version metadata
BUILD_INFO = Info("rag_pipeline_build", "Build information")
BUILD_INFO.info({
    "version": "1.0.0",
    "embedding_model": "BAAI/bge-small-en-v1.5",
})
```

---

## Using Custom Metrics in Application Code

```python
import time
from src.metrics import JOBS_CREATED, JOBS_FAILED, EMBED_LATENCY, CHUNKS_EMBEDDED

# Counter increment with labels
JOBS_CREATED.labels(source_type="url").inc()

# Counter increment without labels
JOBS_COMPLETED.inc()

# Counter with failure reason
JOBS_FAILED.labels(failure_reason="embedding_timeout").inc()

# Histogram — observe a value
AGENT_ROUNDS.observe(3)

# Histogram — measure latency with context manager
with EMBED_LATENCY.labels(model_name="bge-small-en-v1.5").time():
    embeddings = embed_batch(chunks)

# Manual timing
start = time.perf_counter()
result = qdrant_client.upsert(...)
QDRANT_UPSERT_LATENCY.observe(time.perf_counter() - start)

# Counter with collection label
CHUNKS_EMBEDDED.labels(collection_name="docs_v1").inc(len(chunks))
```

---

## Prometheus Configuration File (`prometheus.yml`)

```yaml
global:
  scrape_interval: 15s        # Default scrape frequency
  evaluation_interval: 15s    # Rule evaluation frequency

scrape_configs:
  - job_name: "rag-pipeline-api"
    static_configs:
      - targets: ["api:8000"]   # Docker service name:port
    metrics_path: /metrics
    scrape_interval: 10s        # Override for this job

  - job_name: "qdrant"
    static_configs:
      - targets: ["qdrant:6333"]
    metrics_path: /metrics
    scrape_interval: 30s
```

**Key config fields**:
- `scrape_interval`: How often Prometheus scrapes targets (default: 1m, override per job)
- `evaluation_interval`: How often recording/alerting rules are evaluated
- `metrics_path`: Path to scrape (default: `/metrics`)
- `targets`: `host:port` list — use Docker service names in Docker Compose

---

## Prometheus Query Language (PromQL) — Key Patterns

```promql
# Rate of job creation over 5 minutes (per second)
rate(rag_jobs_created_total[5m])

# Rate by label
rate(rag_jobs_created_total{source_type="url"}[5m])

# P95 embed latency
histogram_quantile(0.95, rate(rag_embed_latency_seconds_bucket[5m]))

# P95 by model
histogram_quantile(0.95, rate(rag_embed_latency_seconds_bucket{model_name="bge-small-en-v1.5"}[5m]))

# Total chunks embedded
sum(rag_chunks_embedded_total)

# HTTP error rate
rate(http_requests_total{status=~"5.."}[5m])

# HTTP request duration P99
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# In-progress requests
rag_http_requests_inprogress
```

---

## Metric Naming Conventions

| Convention | Example | Rule |
|---|---|---|
| Namespace prefix | `rag_` | Identifies the application |
| Unit suffix | `_seconds`, `_bytes`, `_total` | Always include unit |
| Counter suffix | `_total` | All counters end in `_total` |
| Histogram base | `_bucket`, `_count`, `_sum` | Auto-generated by prometheus-client |
| Snake_case | `rag_embed_latency_seconds` | No camelCase |

---

## Instrumentator Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `should_group_status_codes` | bool | `True` | Group 2xx/3xx/4xx/5xx |
| `should_ignore_untemplated` | bool | `False` | Skip routes without path params |
| `should_respect_env_var` | bool | `False` | Enable via env var |
| `should_instrument_requests_inprogress` | bool | `False` | Track in-flight requests |
| `excluded_handlers` | list[str] | `[]` | Regex patterns to exclude |
| `env_var_name` | str | `"ENABLE_METRICS"` | Env var name when `should_respect_env_var=True` |
| `inprogress_name` | str | `"http_requests_inprogress"` | In-progress metric name |
| `inprogress_labels` | bool | `False` | Add handler/method labels to in-progress |

---

## Expose Method Parameters

```python
instrumentator.expose(
    app,
    endpoint="/metrics",          # URL path (default: /metrics)
    include_in_schema=False,      # Hide from OpenAPI docs
    should_gzip=False,            # Compress response (Prometheus supports gzip)
    tags=["monitoring"],          # OpenAPI tags
)
```

---

## Docker Compose Integration

```yaml
services:
  prometheus:
    image: prom/prometheus:v3.4.0
    ports:
      - "9090:9090"
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--web.enable-lifecycle"   # Enable /-/reload endpoint
    networks:
      - observability
```

---

## Common Pitfalls

1. **Duplicate metric registration** — `Counter("name", ...)` called twice raises `ValueError`. Define metrics at module level (not inside functions).
2. **High cardinality labels** — Never use user IDs, URLs, or unbounded values as label values. Use bounded categories only.
3. **`excluded_handlers` regex** — Patterns are matched against the full path. Use `"/health"` not `"health"`.
4. **`/mcp` exclusion** — The MCP Streamable HTTP endpoint at `POST /mcp` should be excluded to avoid high-cardinality span tracking.
5. **`include_in_schema=False`** — Always hide `/metrics` from OpenAPI docs to avoid exposing internal metrics to API consumers.

---

## Sources
- https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- https://github.com/trallnag/prometheus-fastapi-instrumentator (v7.1.0)
- https://prometheus.io/docs/concepts/metric_types/
- https://prometheus.io/docs/practices/naming/
