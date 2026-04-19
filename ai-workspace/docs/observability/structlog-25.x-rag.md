# structlog 25.x — RAG Reference Document

<!-- RAG_METADATA
topic: structured-logging
library: structlog
version: 25.5.0
python_min: 3.9
tags: logging, structured-logging, json-logging, fastapi, celery, asyncio, stdlib-integration
use_case: phase-7-observability-stack
-->

## Overview

**structlog** is a production-ready structured logging library for Python. Version 25.5.0 is the latest stable release (as of 2026-04-19). It outputs JSON in production and pretty-printed colored output in development. It integrates with Python's standard `logging` module via `ProcessorFormatter`.

**Install**: `pip install structlog`

---

## Core Concepts

### Processor Chain
structlog processes log entries through a **pipeline of processors** — functions that take `(logger, method_name, event_dict)` and return a modified `event_dict`. The final processor renders the output.

### Bound Logger
A `BoundLogger` carries context (key-value pairs) that is automatically included in every log entry emitted from that logger instance.

### Context Variables (`contextvars`)
`structlog.contextvars` provides async-safe context propagation. Use `merge_contextvars` processor to inject request-scoped context (e.g., `request_id`, `user_id`) into all log entries within an async request handler.

---

## Standard Library Integration (ProcessorFormatter Pattern)

This is the **recommended pattern** for FastAPI/Celery applications — structlog handles formatting, stdlib `logging` handles output routing.

```python
import logging
import os
import sys
import structlog

def configure_logging() -> None:
    log_format = os.getenv("LOG_FORMAT", "console")  # "json" | "console"
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

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

**Key rule**: When using `ProcessorFormatter`, the structlog processor chain MUST end with `ProcessorFormatter.wrap_for_formatter`. Do NOT use `render_to_log_kwargs` in this pattern.

---

## Environment Variables

| Variable | Values | Default | Effect |
|---|---|---|---|
| `LOG_FORMAT` | `json`, `console` | `console` | Output format |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` | Minimum log level |

---

## Key Processors Reference

| Processor | Module | Purpose |
|---|---|---|
| `merge_contextvars` | `structlog.contextvars` | Inject async context vars into event dict |
| `add_logger_name` | `structlog.stdlib` | Add `logger` key with logger name |
| `add_log_level` | `structlog.stdlib` | Add `level` key |
| `PositionalArgumentsFormatter()` | `structlog.stdlib` | Handle `%s`-style format strings |
| `TimeStamper(fmt="iso")` | `structlog.processors` | Add ISO 8601 `timestamp` key |
| `StackInfoRenderer()` | `structlog.processors` | Render stack info if present |
| `UnicodeDecoder()` | `structlog.processors` | Decode bytes to str |
| `JSONRenderer()` | `structlog.processors` | Render as JSON string (production) |
| `ConsoleRenderer()` | `structlog.dev` | Colored human-readable output (dev) |
| `ProcessorFormatter.wrap_for_formatter` | `structlog.stdlib` | Bridge to stdlib ProcessorFormatter |
| `ProcessorFormatter.remove_processors_meta` | `structlog.stdlib` | Remove `_record` and `_from_structlog` noise |
| `ExtraAdder()` | `structlog.stdlib` | Add `logging.LogRecord.extra` fields to event dict |
| `CallsiteParameterAdder(...)` | `structlog.processors` | Add filename, func_name, lineno |

---

## Usage in Application Code

```python
import structlog

log = structlog.get_logger(__name__)

# Basic usage
log.info("job_started", job_id="abc123", source_type="url")

# Bind context for a request scope
log = log.bind(request_id="req-456", user_id="user-789")
log.info("processing")
log.warning("retry_attempt", attempt=2)

# Async context variables (FastAPI middleware pattern)
from structlog.contextvars import bind_contextvars, clear_contextvars

async def request_middleware(request, call_next):
    clear_contextvars()
    bind_contextvars(request_id=str(uuid4()), path=request.url.path)
    response = await call_next(request)
    return response
```

---

## asyncio Support

structlog supports async logging natively. Use `await logger.ainfo(...)` for non-blocking async log calls (added in 23.1.0). Regular sync methods also work in async contexts.

---

## Integration with OpenTelemetry

structlog can inject OpenTelemetry trace/span IDs into log entries using a custom processor:

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

Add `add_otel_context` to `shared_processors` before the renderer.

---

## Production JSON Output Example

```json
{
  "timestamp": "2026-04-19T00:00:00.000000Z",
  "level": "info",
  "logger": "src.workers.embed",
  "event": "chunks_embedded",
  "job_id": "abc123",
  "chunk_count": 42,
  "collection": "docs_v1",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

---

## Common Pitfalls

1. **`cache_logger_on_first_use=True`** — Must call `configure_logging()` BEFORE any `get_logger()` call. If called after, the cached logger uses the old config.
2. **`ProcessorFormatter` + `render_to_log_kwargs`** — These are mutually exclusive. Using both causes puzzling stdlib errors.
3. **Multiple handlers** — Call `root.handlers.clear()` before adding the structlog handler to avoid duplicate output.
4. **Thread safety** — `contextvars` is async-safe. For thread-based workers (Celery), use `bind_contextvars` at task start and `clear_contextvars` at task end.

---

## Sources
- https://www.structlog.org/en/stable/ (structlog 25.5.0 official docs)
- https://www.structlog.org/en/stable/standard-library.html
- https://www.structlog.org/en/stable/contextvars.html
- https://www.structlog.org/en/stable/frameworks.html
