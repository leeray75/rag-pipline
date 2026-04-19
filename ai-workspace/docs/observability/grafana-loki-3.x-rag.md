# Grafana Loki 3.x — RAG Reference Document

<!-- RAG_METADATA
topic: log-aggregation, log-storage, observability
library: grafana-loki
version: 3.5 (Docker image grafana/loki:3.5), latest stable 3.7.x
tags: logging, loki, logql, log-aggregation, json-logs, structlog, grafana
use_case: phase-7-observability-stack
-->

## Overview

**Grafana Loki** is a horizontally scalable, highly available, multi-tenant log aggregation system. Unlike Elasticsearch, Loki:
- **Only indexes metadata (labels)** — not the full log content
- **Stores compressed log chunks** in object storage (S3, GCS, local)
- Uses **LogQL** for querying (inspired by PromQL)
- Integrates natively with Grafana and links to Tempo traces

**Docker image**: `grafana/loki:3.5` (project uses 3.5; latest is 3.7.x)

---

## Architecture

```
Application (structlog JSON) 
    → Log Shipper (Promtail / Alloy / Docker log driver)
    → Loki Distributor (port 3100)
    → Loki Ingester (in-memory)
    → Object Storage (local / S3 / GCS)
    ← Grafana queries via LogQL
```

---

## Minimal Configuration (`loki-config.yaml`)

```yaml
auth_enabled: false    # Disable multi-tenancy for single-tenant deployments

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /var/loki
  storage:
    filesystem:
      chunks_directory: /var/loki/chunks
      rules_directory: /var/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h    # 7 days
  ingestion_rate_mb: 16
  ingestion_burst_size_mb: 32
```

---

## Docker Compose Integration

```yaml
services:
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

volumes:
  loki-data:
```

---

## Sending Logs to Loki

### Option 1: Promtail (sidecar log shipper)

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'logstream'
```

### Option 2: Docker Logging Driver (Loki Plugin)

```yaml
# docker-compose.yml service logging config
services:
  api:
    logging:
      driver: loki
      options:
        loki-url: "http://loki:3100/loki/api/v1/push"
        loki-external-labels: "job=rag-pipeline-api,env=development"
        loki-pipeline-stages: |
          - json:
              expressions:
                level: level
                trace_id: trace_id
          - labels:
              level:
              trace_id:
```

### Option 3: Alloy (OpenTelemetry Collector)

```hcl
// alloy-config.alloy
loki.source.docker "default" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.docker.containers.targets
  forward_to = [loki.write.default.receiver]
}

loki.write "default" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

---

## LogQL — Query Language

### Log Stream Selectors (required)

```logql
# Select all logs from a job
{job="rag-pipeline-api"}

# Select by container name
{container="api"}

# Multiple labels
{job="rag-pipeline-api", level="error"}
```

### Log Pipeline Filters

```logql
# Filter by text
{job="rag-pipeline-api"} |= "embed_chunks"

# Filter out text
{job="rag-pipeline-api"} != "health"

# Regex filter
{job="rag-pipeline-api"} |~ "job_id=.*"

# JSON parsing + field filter
{job="rag-pipeline-api"} | json | level="error"

# JSON parsing + field comparison
{job="rag-pipeline-api"} | json | chunk_count > 100

# Extract trace_id from JSON logs
{job="rag-pipeline-api"} | json | trace_id != ""
```

### Metric Queries (LogQL → Prometheus-style)

```logql
# Error rate over 5 minutes
rate({job="rag-pipeline-api"} | json | level="error" [5m])

# Count of log lines per minute
count_over_time({job="rag-pipeline-api"}[1m])

# Bytes ingested per minute
bytes_over_time({job="rag-pipeline-api"}[1m])
```

---

## Grafana Data Source Configuration

In Grafana provisioning (`datasources.yml`):

```yaml
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    jsonData:
      maxLines: 1000
      derivedFields:
        # Create clickable link from trace_id in logs to Tempo
        - datasourceUid: tempo
          matcherRegex: '"trace_id":"(\w+)"'
          name: TraceID
          url: "$${__value.raw}"
          urlDisplayLabel: "View Trace in Tempo"
```

**Derived Fields** enable one-click navigation from a log entry containing a `trace_id` to the corresponding trace in Tempo.

---

## Structlog JSON → Loki Label Extraction

When structlog outputs JSON logs, Loki can parse and index fields as labels:

```json
{
  "timestamp": "2026-04-19T00:00:00Z",
  "level": "info",
  "logger": "src.workers.embed",
  "event": "chunks_embedded",
  "job_id": "abc123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

Promtail pipeline stage to extract labels:

```yaml
pipeline_stages:
  - json:
      expressions:
        level: level
        trace_id: trace_id
        logger: logger
  - labels:
      level:
      logger:
  - timestamp:
      source: timestamp
      format: RFC3339Nano
```

**Best practice**: Only index low-cardinality fields as labels (`level`, `logger`, `job`, `env`). Never index `trace_id`, `job_id`, or other high-cardinality values as labels — use them as log content instead.

---

## Loki API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/loki/api/v1/push` | POST | Push log entries |
| `/loki/api/v1/query` | GET | Instant query |
| `/loki/api/v1/query_range` | GET | Range query |
| `/loki/api/v1/labels` | GET | List label names |
| `/loki/api/v1/label/{name}/values` | GET | List label values |
| `/ready` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

---

## Retention Configuration

```yaml
limits_config:
  retention_period: 168h    # 7 days (Loki 3.x)

compactor:
  working_directory: /var/loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150
```

---

## Common Pitfalls

1. **Label cardinality** — High-cardinality labels (trace_id, user_id) cause performance issues. Use them as log content, not labels.
2. **`auth_enabled: false`** — Required for single-tenant deployments. Multi-tenant requires `X-Scope-OrgID` header.
3. **Schema version** — Use `schema: v13` (Loki 3.x default). Older schemas (`v11`, `v12`) are deprecated.
4. **`reject_old_samples`** — Loki rejects logs older than `reject_old_samples_max_age`. Ensure system clocks are synchronized.
5. **Log ordering** — Loki requires logs to be pushed in timestamp order per stream. Out-of-order logs are rejected unless `unordered_writes: true`.

---

## Sources
- https://grafana.com/docs/loki/latest/ (Loki 3.7.x, latest stable)
- https://grafana.com/docs/loki/latest/query/
- https://grafana.com/docs/loki/latest/configure/
- https://grafana.com/docs/loki/latest/send-data/
