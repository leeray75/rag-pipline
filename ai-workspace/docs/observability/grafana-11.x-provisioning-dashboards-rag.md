# Grafana 11.x — Provisioning & Dashboards RAG Reference Document

<!-- RAG_METADATA
topic: grafana, dashboards, provisioning, visualization, observability
library: grafana
version: 11.6 (Docker image grafana/grafana:11.6), latest stable 12.4
tags: grafana, provisioning, datasources, dashboards, json-model, grafana-as-code
use_case: phase-7-observability-stack
-->

## Overview

**Grafana** is an open-source analytics and visualization platform. In this stack:
- **Version**: 11.6 (Docker image `grafana/grafana:11.6`)
- **Provisioning**: Data sources and dashboards are defined as YAML/JSON files (GitOps-friendly)
- **Data sources**: Prometheus (metrics), Tempo (traces), Loki (logs)
- **Port**: 3000 (default), mapped to 3001 in Docker Compose to avoid conflicts

---

## Provisioning Directory Structure

```
infra/grafana/
├── provisioning/
│   ├── datasources/
│   │   └── datasources.yml       # Data source definitions
│   ├── dashboards/
│   │   └── dashboards.yml        # Dashboard provider config
│   └── alerting/
│       └── rules.yml             # Alert rules (optional)
└── dashboards/
    └── pipeline-throughput.json  # Dashboard JSON models
```

---

## Data Source Provisioning (`datasources.yml`)

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      httpMethod: POST
      prometheusVersion: "3.4.0"
      prometheusType: Prometheus
      timeInterval: "15s"         # Match prometheus scrape_interval
    editable: false

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      httpMethod: GET
      serviceMap:
        datasourceUid: prometheus
      nodeGraph:
        enabled: true
      tracesToLogs:
        datasourceUid: loki
        tags: ["job", "instance"]
        mappedTags:
          - key: "service.name"
            value: "app"
        filterByTraceID: true
        filterBySpanID: false
      tracesToMetrics:
        datasourceUid: prometheus
        tags:
          - key: "service.name"
            value: "app"
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    jsonData:
      maxLines: 1000
      derivedFields:
        - datasourceUid: tempo
          matcherRegex: '"trace_id":"(\w+)"'
          name: TraceID
          url: "$${__value.raw}"
          urlDisplayLabel: "View Trace"
    editable: false
```

**Key fields**:
- `access: proxy` — Grafana server proxies requests to the data source (required for Docker networking)
- `isDefault: true` — Only one data source per type can be default
- `editable: false` — Prevents UI edits from overwriting provisioned config
- `uid` — Optional stable UID for cross-referencing between data sources

---

## Dashboard Provider Configuration (`dashboards.yml`)

```yaml
apiVersion: 1

providers:
  - name: "default"
    orgId: 1
    folder: "RAG Pipeline"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30     # Reload dashboards every 30s
    allowUiUpdates: false         # Prevent UI edits from persisting
    options:
      path: /var/lib/grafana/dashboards   # Mount point in container
      foldersFromFilesStructure: true     # Use subdirectory names as folder names
```

---

## Dashboard JSON Model Structure

Grafana dashboards are defined as JSON. Key top-level fields:

```json
{
  "dashboard": {
    "id": null,
    "uid": "rag-throughput",          // Stable unique ID (used in URLs)
    "title": "RAG Pipeline — Throughput",
    "description": "Pipeline job metrics",
    "tags": ["rag", "pipeline"],
    "timezone": "browser",
    "schemaVersion": 39,              // Grafana 11.x schema version
    "version": 1,
    "refresh": "30s",                 // Auto-refresh interval
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "panels": [],                     // Array of panel objects
    "templating": {
      "list": []                      // Template variables
    },
    "annotations": {
      "list": []
    }
  },
  "overwrite": true,                  // Overwrite existing dashboard with same uid
  "folderId": 0
}
```

---

## Panel Types and Configuration

### Time Series Panel

```json
{
  "id": 1,
  "title": "Jobs Created (rate)",
  "type": "timeseries",
  "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
  "datasource": { "type": "prometheus", "uid": "prometheus" },
  "targets": [
    {
      "expr": "rate(rag_jobs_created_total[5m])",
      "legendFormat": "{{source_type}}",
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "reqps",
      "color": { "mode": "palette-classic" }
    }
  },
  "options": {
    "legend": { "displayMode": "list", "placement": "bottom" }
  }
}
```

### Stat Panel

```json
{
  "id": 2,
  "title": "Embed Latency P95",
  "type": "stat",
  "gridPos": { "h": 4, "w": 6, "x": 0, "y": 8 },
  "datasource": { "type": "prometheus", "uid": "prometheus" },
  "targets": [
    {
      "expr": "histogram_quantile(0.95, rate(rag_embed_latency_seconds_bucket[5m]))",
      "legendFormat": "p95",
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "s",
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "green", "value": null },
          { "color": "yellow", "value": 1 },
          { "color": "red", "value": 5 }
        ]
      }
    }
  },
  "options": {
    "reduceOptions": { "calcs": ["lastNotNull"] },
    "colorMode": "background"
  }
}
```

### Histogram Panel

```json
{
  "id": 3,
  "title": "Agent Rounds Distribution",
  "type": "histogram",
  "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
  "datasource": { "type": "prometheus", "uid": "prometheus" },
  "targets": [
    {
      "expr": "rag_agent_rounds_per_job_bucket",
      "legendFormat": "{{le}} rounds",
      "refId": "A"
    }
  ]
}
```

### Logs Panel (Loki)

```json
{
  "id": 4,
  "title": "Application Logs",
  "type": "logs",
  "gridPos": { "h": 8, "w": 24, "x": 0, "y": 16 },
  "datasource": { "type": "loki", "uid": "loki" },
  "targets": [
    {
      "expr": "{job=\"rag-pipeline-api\"} | json | level=\"error\"",
      "refId": "A"
    }
  ],
  "options": {
    "showTime": true,
    "showLabels": false,
    "wrapLogMessage": true,
    "sortOrder": "Descending"
  }
}
```

---

## Grid Layout System

Grafana uses a 24-column grid. `gridPos` defines panel position:

| Field | Description |
|---|---|
| `x` | Column start (0–23) |
| `y` | Row start (0+) |
| `w` | Width in columns (1–24) |
| `h` | Height in rows (1+) |

Common layouts:
- Full width: `{ "w": 24, "x": 0 }`
- Half width: `{ "w": 12, "x": 0 }` and `{ "w": 12, "x": 12 }`
- Quarter width: `{ "w": 6, "x": 0 }`, `{ "w": 6, "x": 6 }`, etc.

---

## Template Variables

```json
{
  "templating": {
    "list": [
      {
        "name": "collection",
        "type": "query",
        "datasource": { "type": "prometheus", "uid": "prometheus" },
        "query": "label_values(rag_chunks_embedded_total, collection_name)",
        "refresh": 2,
        "includeAll": true,
        "multi": false,
        "label": "Collection"
      }
    ]
  }
}
```

Use variables in panel queries: `rag_chunks_embedded_total{collection_name="$collection"}`

---

## Docker Compose Integration

```yaml
services:
  grafana:
    image: grafana/grafana:11.6
    ports:
      - "3001:3000"    # Map to 3001 to avoid conflicts
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

volumes:
  grafana-data:
```

**Key environment variables**:
- `GF_SECURITY_ADMIN_PASSWORD` — Admin password (change in production)
- `GF_USERS_ALLOW_SIGN_UP=false` — Disable self-registration
- `GF_FEATURE_TOGGLES_ENABLE=traceqlEditor` — Enable TraceQL editor in Explore

---

## Provisioning File Locations in Container

| Host Path | Container Path | Purpose |
|---|---|---|
| `./infra/grafana/provisioning/` | `/etc/grafana/provisioning/` | Provisioning config |
| `./infra/grafana/dashboards/` | `/var/lib/grafana/dashboards/` | Dashboard JSON files |

---

## Common Pitfalls

1. **`uid` conflicts** — Dashboard UIDs must be unique across all provisioned dashboards. Use descriptive, stable UIDs like `"rag-throughput"`.
2. **`access: proxy` vs `direct`** — Always use `proxy` in Docker Compose. `direct` (browser) requires the browser to reach the data source directly.
3. **`editable: false`** — Prevents UI changes from persisting. Set `allowUiUpdates: true` in the dashboard provider if you want to save UI edits.
4. **`schemaVersion`** — Grafana 11.x uses schema version 39. Older dashboards may need migration.
5. **Volume mount order** — Provisioning files must be mounted before Grafana starts. Use `:ro` (read-only) for config files.
6. **`overwrite: true`** — Required in dashboard JSON to update existing dashboards with the same UID.

---

## Sources
- https://grafana.com/docs/grafana/latest/administration/provisioning/ (Grafana 12.4, latest)
- https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/
- https://grafana.com/docs/grafana/latest/panels-visualizations/
- https://grafana.com/docs/grafana/latest/datasources/
