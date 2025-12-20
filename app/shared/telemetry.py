# app\shared\telemetry.py
# app/shared/telemetry.py
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.shared.config import settings

logger = logging.getLogger(__name__)

def setup_telemetry(app_name: str = settings.OTEL_SERVICE_NAME):
    """
    Initializes the OpenTelemetry SDK with OTLP export.
    Should be called once at process startup (api or worker).
    """
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        logger.info("Telemetry disabled: No OTEL_EXPORTER_OTLP_ENDPOINT configured.")
        return

    logger.info(f"Initializing Telemetry for service: {app_name}")

    # 1. Define Resource (Service Identity)
    resource = Resource.create(attributes={
        "service.name": app_name,
        "deployment.environment": settings.APP_ENV.value,
        "service.version": "1.0.0"
    })

    # 2. Configure Tracer Provider
    trace_provider = TracerProvider(resource=resource)

    # 3. Configure Exporter (Send data to Jaeger/Tempo)
    otlp_exporter = OTLPSpanExporter(endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces")
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace_provider.add_span_processor(span_processor)

    # 4. Optional: Console Exporter for local Debugging
    if settings.DEBUG:
        trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # 5. Set Global Provider
    trace.set_tracer_provider(trace_provider)

def instrument_fastapi(app):
    """
    Auto-instruments the FastAPI application to trace incoming HTTP requests.
    """
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        FastAPIInstrumentor.instrument_app(app)

def get_tracer(name: str):
    """
    Utility to get a tracer for manual instrumentation in specific modules.
    """
    return trace.get_tracer(name)