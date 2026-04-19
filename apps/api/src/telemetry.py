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
