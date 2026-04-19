# Grafana Tempo 2.x — RAG Reference Document

<!-- RAG_METADATA
topic: distributed-tracing, trace-storage, observability
library: grafana-tempo
version: 2.7 (Docker image grafana/tempo:2.7), latest stable 2.10.x
tags: tracing, otlp, jaeger, zipkin, tempo, grpc, storage, grafana
use_case: phase-7-observability-stack
-->

## Overview

**Grafana Tempo** is an open-source, high-scale distributed tracing backend. It:
- Accepts traces via **OTLP** (gRPC port 4317, HTTP port 4318), Jaeger, Zipkin
- Stores traces in **object storage** (S3, GCS, Azure) or **local filesystem**
- Integrates natively with Grafana as a data source
- Supports **TraceQL** — a query language for selecting traces
- Links traces to Loki logs and Prometheus metrics via exemplars

**Docker image**: `grafana/tempo:2.7` (project uses 2.7; latest is 2.10.x)

---

## Minimal Configuration (`tempo.yaml`)

```yaml
server:
  http_listen_port: 3200      # Tempo HTTP API port

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"   # OTLP gRPC receiver
        http:
          endpoint: "0.0.0.0:4318"   # OTLP HTTP receiver

storage:
  trace:
    backend: local              # Use "s3" or "gcs" in production
    local:
      path: /var/tempo/traces   # Trace storage directory
    wal:
      path: /var/tempo/wal      # Write-ahead log directory
```

---

## Production Configuration with Retention

```yaml
server:
  http_listen_port: 3200
  log_level: info

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"
        http:
          endpoint: "0.0.0.0:4318"
    jaeger:
      protocols:
        thrift_http:
          endpoint: "0.0.0.0:14268"
    zipkin:
      endpoint: "0.0.0.0:9411"

ingester:
  max_block_duration: 5m        # Flush traces to storage every 5 minutes

compactor:
  compaction:
    block_retention: 48h        # Keep traces for 48 hours

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
    pool:
      max_workers: 100
      queue_depth: 10000

# Enable metrics-generator (span metrics → Prometheus)
metrics_generator:
  registry:
    external_labels:
      source: tempo
      cluster: docker-compose
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
        send_exemplars: true

overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs, span-metrics]
```

---

## Ports Reference

| Port | Protocol | Purpose |
|---|---|---|
| 3200 | HTTP | Tempo API, health check, query |
| 4317 | gRPC | OTLP gRPC receiver |
| 4318 | HTTP | OTLP HTTP receiver |
| 14268 | HTTP | Jaeger Thrift HTTP receiver |
| 9411 | HTTP | Zipkin receiver |

---

## Docker Compose Integration

```yaml
services:
  tempo:
    image: grafana/tempo:2.7
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./infra/tempo/tempo.yaml:/etc/tempo.yaml:ro
      - tempo-data:/var/tempo
    ports:
      - "3200:3200"    # Tempo API
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    networks:
      - observability

volumes:
  tempo-data:
```

---

## Grafana Data Source Configuration

In Grafana provisioning (`datasources.yml`):

```yaml
datasources:
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      httpMethod: GET
      serviceMap:
        datasourceUid: prometheus   # Link to Prometheus for service graph
      nodeGraph:
        enabled: true
      tracesToLogs:
        datasourceUid: loki         # Link traces to Loki logs
        tags: ["job", "instance", "pod", "namespace"]
        mappedTags: [{ key: "service.name", value: "app" }]
        mapTagNamesEnabled: false
        spanStartTimeShift: "1h"
        spanEndTimeShift: "-1h"
        filterByTraceID: true
        filterBySpanID: false
      tracesToMetrics:
        datasourceUid: prometheus   # Link traces to Prometheus metrics
        tags: [{ key: "service.name", value: "app" }]
```

---

## TraceQL — Query Language

TraceQL selects spans from Tempo. Inspired by PromQL and LogQL.

```
# Select all spans from a service
{ resource.service.name = "rag-pipeline-api" }

# Select spans with errors
{ status = error }

# Select slow spans (> 1 second)
{ duration > 1s }

# Select spans by operation name
{ name = "embed_chunks" }

# Combine conditions
{ resource.service.name = "rag-pipeline-api" && duration > 500ms }

# Select spans with specific attribute
{ span.embedding.model = "bge-small-en-v1.5" }

# Structural query — find parent spans with slow children
{ .http.method = "POST" } >> { duration > 2s }
```

---

## Health Check

```bash
# Check Tempo is ready
curl http://localhost:3200/ready

# Check Tempo metrics
curl http://localhost:3200/metrics

# Query traces via API
curl "http://localhost:3200/api/traces/{traceID}"

# Search traces
curl "http://localhost:3200/api/search?service.name=rag-pipeline-api&limit=20"
```

---

## Storage Backends

| Backend | Config Key | Use Case |
|---|---|---|
| Local filesystem | `backend: local` | Development, single-node |
| AWS S3 | `backend: s3` | Production, scalable |
| Google Cloud Storage | `backend: gcs` | Production, GCP |
| Azure Blob Storage | `backend: azure` | Production, Azure |

**Local storage** is appropriate for development and single-node deployments. For production, use object storage with `block_retention` set.

---

## Metrics Generator (Span Metrics → Prometheus)

Tempo can generate RED metrics (Rate, Error, Duration) from spans and push them to Prometheus:

```yaml
metrics_generator:
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
  
overrides:
  defaults:
    metrics_generator:
      processors:
        - service-graphs    # Service dependency graph metrics
        - span-metrics      # RED metrics per span name
```

Generated metrics:
- `traces_spanmetrics_calls_total` — call rate per operation
- `traces_spanmetrics_duration_seconds` — latency histogram per operation
- `traces_service_graph_request_total` — service-to-service call counts

---

## Integration with structlog (Trace ID Injection)

To correlate logs with traces, inject trace/span IDs into structlog:

```python
from opentelemetry import trace

def add_otel_context(logger, method, event_dict):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

In Grafana, configure the Loki data source with **Derived Fields** to create clickable links from `trace_id` in logs to Tempo traces.

---

## Common Pitfalls

1. **`insecure=True` in OTLPSpanExporter** — Required when Tempo has no TLS. The gRPC endpoint `http://tempo:4317` must use `insecure=True`.
2. **Volume permissions** — Tempo writes to `/var/tempo`. Ensure the Docker volume is writable.
3. **WAL path** — Always configure a separate WAL path from the trace storage path.
4. **`block_retention`** — Default is 336h (14 days). Set explicitly for your use case.
5. **Port conflicts** — Port 4317 (OTLP gRPC) may conflict with other services. Map carefully in Docker Compose.

---

## Sources
- https://grafana.com/docs/tempo/latest/ (Tempo 2.10.x, latest stable)
- https://grafana.com/docs/tempo/latest/configuration/
- https://grafana.com/docs/tempo/latest/traceql/
- https://grafana.com/docs/tempo/latest/metrics-generator/
