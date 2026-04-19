# OpenTelemetry Python SDK 1.33.x — RAG Reference Document

<!-- RAG_METADATA
topic: distributed-tracing, metrics, observability
library: opentelemetry-python
version: 1.33.0 (api+sdk), 0.54b0 (instrumentation packages)
python_min: 3.9
tags: tracing, spans, otlp, fastapi, celery, httpx, grpc, tempo, prometheus
use_case: phase-7-observability-stack
-->

## Overview

OpenTelemetry Python provides APIs and SDKs for **traces**, **metrics**, and **logs** (logs in development status). The stack used in this project:

| Package | Version | Purpose |
|---|---|---|
| `opentelemetry-api` | 1.33.0 | Core API (tracer, meter, context) |
| `opentelemetry-sdk` | 1.33.0 | SDK implementation (TracerProvider, MeterProvider) |
| `opentelemetry-exporter-otlp` | 1.33.0 | OTLP gRPC/HTTP exporter → Grafana Tempo |
| `opentelemetry-instrumentation-fastapi` | 0.54b0 | Auto-instrument FastAPI routes |
| `opentelemetry-instrumentation-celery` | 0.54b0 | Auto-instrument Celery tasks |
| `opentelemetry-instrumentation-httpx` | 0.54b0 | Auto-instrument httpx HTTP client |
| `opentelemetry-semantic-conventions` | latest | Standard attribute names |

**Install**:
```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-celery \
  opentelemetry-instrumentation-httpx
```

---

## Tracing Setup — TracerProvider + OTLP Exporter

```python
"""OpenTelemetry configuration — traces exported to Grafana Tempo via OTLP gRPC."""
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
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

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI (must be called after app creation)
    if app:
        FastAPIInstrumentor.instrument_app(app)

    # Instrument Celery (instruments all tasks globally)
    CeleryInstrumentor().instrument()

    # Instrument httpx (instruments all AsyncClient / Client instances)
    HTTPXClientInstrumentor().instrument()
```

---

## Resource Attributes

`Resource.create()` accepts a dict of semantic convention attributes. Key attributes:

| Attribute | Semantic Convention | Example |
|---|---|---|
| `service.name` | `ResourceAttributes.SERVICE_NAME` | `"rag-pipeline-api"` |
| `service.version` | `ResourceAttributes.SERVICE_VERSION` | `"1.0.0"` |
| `deployment.environment` | `ResourceAttributes.DEPLOYMENT_ENVIRONMENT` | `"production"` |
| `service.instance.id` | `ResourceAttributes.SERVICE_INSTANCE_ID` | hostname |

---

## Manual Span Creation

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

# Context manager (auto-closes span)
def embed_chunks(chunks: list, model: str) -> list:
    with tracer.start_as_current_span("embed_chunks") as span:
        span.set_attribute("embedding.model", model)
        span.set_attribute("embedding.chunk_count", len(chunks))
        # ... do work ...
        return embeddings

# Decorator pattern
@tracer.start_as_current_span("process_job")
def process_job(job_id: str):
    pass

# Nested spans
with tracer.start_as_current_span("parent_operation") as parent:
    parent.set_attribute("job.id", job_id)
    with tracer.start_as_current_span("child_operation") as child:
        child.set_attribute("step", "embedding")
```

---

## Span Status and Exception Recording

```python
from opentelemetry.trace import Status, StatusCode

with tracer.start_as_current_span("risky_operation") as span:
    try:
        result = do_something()
        span.set_status(Status(StatusCode.OK))
    except Exception as ex:
        span.set_status(Status(StatusCode.ERROR, str(ex)))
        span.record_exception(ex)
        raise
```

---

## Span Events (Structured Log Points)

```python
current_span = trace.get_current_span()
current_span.add_event("chunk_batch_ready", {"batch_size": 32, "model": "bge-small"})
current_span.add_event("qdrant_upsert_complete", {"upserted": 32})
```

---

## Span Links (Cross-Request Causality)

```python
# Link a background task span to the originating request span
ctx = trace.get_current_span().get_span_context()
link = trace.Link(ctx)

with tracer.start_as_current_span("background_task", links=[link]):
    pass
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint (Tempo) |
| `OTEL_SERVICE_NAME` | app name | Service name in traces |
| `OTEL_ENABLED` | `true` | Toggle tracing on/off |
| `OTEL_PROPAGATORS` | `tracecontext,baggage` | Propagation formats |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` | Sampling strategy |
| `OTEL_TRACES_SAMPLER_ARG` | `1.0` | Sampling rate (0.0–1.0) |

---

## FastAPI Auto-Instrumentation

`FastAPIInstrumentor.instrument_app(app)` automatically:
- Creates a span for every HTTP request
- Sets `http.method`, `http.url`, `http.status_code` attributes
- Propagates W3C TraceContext headers from incoming requests
- Links server spans to client spans via `traceparent` header

**Important**: Call `instrument_app(app)` AFTER `app = FastAPI(...)` and AFTER adding all middleware.

---

## Celery Auto-Instrumentation

`CeleryInstrumentor().instrument()` automatically:
- Creates spans for task publish (`celery.apply`) and task execution (`celery.run`)
- Propagates trace context through Celery message headers
- Records task failures as span errors

**Important**: Call `CeleryInstrumentor().instrument()` before the Celery app processes tasks (at module import time or in `configure_telemetry()`).

---

## httpx Auto-Instrumentation

`HTTPXClientInstrumentor().instrument()` automatically:
- Creates spans for all `httpx.Client` and `httpx.AsyncClient` requests
- Injects `traceparent` header into outgoing requests
- Records HTTP status codes and URLs

---

## OTLP Exporter — gRPC vs HTTP

| Mode | Package | Endpoint | Port |
|---|---|---|---|
| gRPC (recommended) | `opentelemetry-exporter-otlp-proto-grpc` | `http://tempo:4317` | 4317 |
| HTTP/protobuf | `opentelemetry-exporter-otlp-proto-http` | `http://tempo:4318` | 4318 |

```python
# gRPC (default, lower overhead)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
exporter = OTLPSpanExporter(endpoint="http://tempo:4317", insecure=True)

# HTTP/protobuf (firewall-friendly)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
exporter = OTLPSpanExporter(endpoint="http://tempo:4318/v1/traces")
```

---

## BatchSpanProcessor Configuration

```python
from opentelemetry.sdk.trace.export import BatchSpanProcessor

processor = BatchSpanProcessor(
    exporter,
    max_queue_size=2048,          # Max spans buffered before dropping
    schedule_delay_millis=5000,   # Export interval (ms)
    max_export_batch_size=512,    # Spans per export batch
    export_timeout_millis=30000,  # Export timeout (ms)
)
```

---

## Semantic Conventions (Key Attributes)

```python
from opentelemetry.semconv.trace import SpanAttributes

# HTTP
span.set_attribute(SpanAttributes.HTTP_METHOD, "POST")
span.set_attribute(SpanAttributes.HTTP_URL, "https://api.example.com/embed")
span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 200)

# Database
span.set_attribute(SpanAttributes.DB_SYSTEM, "qdrant")
span.set_attribute(SpanAttributes.DB_OPERATION, "upsert")
span.set_attribute(SpanAttributes.DB_NAME, "docs_v1")

# Messaging (Celery)
span.set_attribute(SpanAttributes.MESSAGING_SYSTEM, "celery")
span.set_attribute(SpanAttributes.MESSAGING_DESTINATION, "embed_queue")
```

---

## Context Propagation

OpenTelemetry uses W3C TraceContext (`traceparent`, `tracestate`) by default. For cross-service propagation:

```python
from opentelemetry.propagate import inject, extract

# Inject into outgoing HTTP headers
headers = {}
inject(headers)
# headers now contains: {"traceparent": "00-<trace_id>-<span_id>-01"}

# Extract from incoming HTTP headers
context = extract(request.headers)
with tracer.start_as_current_span("handler", context=context):
    pass
```

---

## Common Pitfalls

1. **`insecure=True`** — Required for local/Docker Tempo without TLS. Remove in production with proper TLS.
2. **`instrument_app()` order** — Must be called after all middleware is added to FastAPI.
3. **`CeleryInstrumentor` double-instrument** — Calling `.instrument()` twice raises an error. Guard with `if not CeleryInstrumentor().is_instrumented_by_opentelemetry`.
4. **`OTEL_ENABLED` guard** — Always provide a kill-switch env var to disable tracing in test environments.
5. **Resource detection** — `Resource.create()` auto-detects process/host attributes. Pass explicit dict to override.

---

## Sources
- https://opentelemetry.io/docs/languages/python/ (official Python docs, updated 2026-01-27)
- https://opentelemetry.io/docs/languages/python/instrumentation/
- https://opentelemetry.io/docs/languages/python/exporters/
- https://opentelemetry-python-contrib.readthedocs.io/en/latest/
