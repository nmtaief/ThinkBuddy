"""OpenTelemetry tracing hooks (stubbed and production-ready)."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def setup_telemetry(
    service_name: str,
    enabled: bool = False,
    endpoint: str = "http://localhost:4317",
) -> None:
    """Initialize OpenTelemetry tracer provider if enabled, otherwise configure graceful no-op."""
    if not enabled:
        logger.info(
            "OpenTelemetry is disabled (OTEL_ENABLED=false). Running in no-op tracing mode."
        )
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(
            "OpenTelemetry initialized for service %s at %s",
            service_name,
            endpoint,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to initialize OpenTelemetry exporter: %s. Continuing with no-op.",
            exc,
        )


def get_tracer(name: str) -> Any:
    """Return an OpenTelemetry tracer or no-op tracer."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:

        class NoOpTracer:
            def start_as_current_span(self, name: str, *args: Any, **kwargs: Any) -> Any:
                from contextlib import nullcontext

                return nullcontext()

        return NoOpTracer()
