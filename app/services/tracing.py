from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings

_tracer_provider: TracerProvider | None = None
_httpx_instrumentor: HTTPXClientInstrumentor | None = None


def configure_tracing(app: FastAPI) -> None:
    global _tracer_provider, _httpx_instrumentor
    if _tracer_provider is not None or not settings.OTEL_ENABLED:
        return

    resource = Resource.create(
        {
            "service.name": settings.PROJECT_NAME,
            "service.namespace": "greengate",
            "service.version": "0.3.0",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )
    exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        headers=settings.otel_headers(),
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    _httpx_instrumentor = HTTPXClientInstrumentor()
    _httpx_instrumentor.instrument()
    _tracer_provider = provider


def shutdown_tracing() -> None:
    global _tracer_provider, _httpx_instrumentor
    if _tracer_provider is None:
        return
    if _httpx_instrumentor is not None:
        _httpx_instrumentor.uninstrument()
        _httpx_instrumentor = None
    _tracer_provider.shutdown()
    _tracer_provider = None