# app/core/use_cases/build_language.py
import structlog
from opentelemetry.propagate import inject

from app.core.domain.events import SystemEvent, EventType, BuildRequestedPayload
from app.core.domain.exceptions import DomainError
from app.core.ports.task_queue import ITaskQueue
from app.shared.observability import get_tracer

logger = structlog.get_logger()
tracer = get_tracer(__name__)


class BuildLanguage:
    """
    Use Case: Initiates the build process for a specific language.

    This is an Asynchronous Command. It does not wait for the build to finish.

    Responsibilities:
    1. Validate the build request parameters (strategy, lang_code).
    2. Construct a domain correlation envelope (SystemEvent).
    3. Enqueue a background job via the TaskQueue port (ARQ adapter).
    """

    def __init__(self, task_queue: ITaskQueue):
        # Inject the TaskQueue Port (job queue, not pub/sub)
        self.task_queue = task_queue

    async def execute(self, lang_code: str, strategy: str = "fast") -> str:
        """
        Triggers a language build.

        Args:
            lang_code: Language code (as used by the build system).
            strategy: 'fast' or 'full'.

        Returns:
            str: Correlation ID for tracking the request.
        """
        with tracer.start_as_current_span("use_case.build_language") as span:
            span.set_attribute("app.lang_code", lang_code)
            span.set_attribute("app.build_strategy", strategy)

            logger.info("build_request_received", lang=lang_code, strategy=strategy)

            try:
                # 1. Validate Strategy
                if strategy not in ("fast", "full"):
                    raise DomainError(
                        f"Invalid build strategy '{strategy}'. Use 'fast' or 'full'."
                    )

                # 2. Create Payload (Pydantic model ensures correct serialization)
                payload = BuildRequestedPayload(lang_code=lang_code, strategy=strategy)

                # 3. Create Correlation Envelope (domain-level)
                trace_id_hex = format(span.get_span_context().trace_id, "032x")
                event = SystemEvent(
                    type=EventType.BUILD_REQUESTED,
                    payload=payload.model_dump(),
                    trace_id=trace_id_hex,
                )

                # 4. Inject distributed trace context for the worker job
                trace_context: dict[str, str] = {}
                inject(trace_context)

                # 5. Enqueue background job (adapter maps correlation/event -> ARQ job)
                job_id = await self.task_queue.enqueue_language_build(
                    lang_code=lang_code,
                    strategy=strategy,
                    correlation_id=event.id,
                    trace_context=trace_context,
                )

                logger.info(
                    "build_job_enqueued",
                    correlation_id=event.id,
                    job_id=job_id,
                    lang=lang_code,
                    strategy=strategy,
                )

                # Return correlation ID so clients can track status elsewhere
                return event.id

            except DomainError:
                raise
            except Exception as e:
                logger.error("build_request_failed", error=str(e), exc_info=True)
                raise DomainError(f"Failed to queue build request: {str(e)}") from e
