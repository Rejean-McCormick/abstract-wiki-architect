# app\shared\logging_config.py
import sys
import logging
import structlog
from opentelemetry import trace
from app.shared.config import settings

def add_open_telemetry_spans(_, __, event_dict):
    """
    Processor to inject the current TraceID and SpanID into the log entry.
    This links the log to the distributed trace in tools like Jaeger.
    """
    span = trace.get_current_span()
    if not span.is_recording():
        event_dict["trace_id"] = None
        event_dict["span_id"] = None
        return event_dict

    ctx = span.get_span_context()
    event_dict["trace_id"] = format(ctx.trace_id, "032x")
    event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

def configure_logging():
    """
    Configures structlog and the standard logging library to emit
    structured JSON logs (Production) or colored text logs (Development).
    """
    
    # 1. Define the chain of processors (Middleware for logs)
    processors = [
        structlog.contextvars.merge_contextvars, # Merge context from thread local
        add_open_telemetry_spans,                # Inject Trace IDs
        structlog.processors.add_log_level,      # Add "level": "info"
        structlog.processors.TimeStamper(fmt="iso"), # Add "timestamp": "2023-..."
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,    # Format exceptions niceley
    ]

    # 2. Determine the Output Format
    if settings.LOG_FORMAT == "json":
        # Production: Machine-readable JSON
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Human-readable colored console output
        processors.append(structlog.dev.ConsoleRenderer())

    # 3. Configure Structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 4. Intercept Standard Library Logging (e.g., from Uvicorn/FastAPI)
    # This ensures logs from 3rd party libs also get formatted correctly.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL.upper(),
    )
    
    # Redirect standard logging to structlog
    # (Note: In a full prod setup, you might use structlog.stdlib.LoggerFactory)