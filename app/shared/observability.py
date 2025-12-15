# app\shared\observability.py
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.shared.config import settings

def setup_observability(app: FastAPI):
    """
    Configures OpenTelemetry for the application.
    
    1. Sets the Global Tracer Provider.
    2. Configures an Exporter (Console for Dev, can be swapped for OTLP/Jaeger).
    3. Auto-instruments the FastAPI application to trace all HTTP requests.
    """
    
    # 1. Define Resource (Service Name identity)
    resource = Resource.create(attributes={
        "service.name": settings.APP_NAME,
        "service.environment": settings.APP_ENV.value,
    })

    # 2. Initialize the Tracer Provider
    provider = TracerProvider(resource=resource)
    
    # 3. Configure the Exporter
    # In a full production setup with Jaeger/Grafana Tempo, you would use:
    # from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    # processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="..."))
    
    # For this setup (Console/Logs), we use ConsoleSpanExporter to print traces to stdout
    # or just a No-Op if we only care about generating Trace IDs for logs.
    if settings.DEBUG:
        # Prints trace details to console (noisy but good for debugging)
        # processor = BatchSpanProcessor(ConsoleSpanExporter())
        # provider.add_span_processor(processor)
        pass
    
    # Set the global provider
    trace.set_tracer_provider(provider)

    # 4. Instrument FastAPI
    # This hook automatically captures HTTP methods, paths, and status codes.
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

def get_tracer(name: str):
    """
    Utility to get a tracer for manual instrumentation in Use Cases.
    Usage:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my_custom_logic"):
            ...
    """
    return trace.get_tracer(name)